"""
Portfolio backtest: for each trading day in the date range, automatically
runs the screening engine (without saving to DB), then simulates buying
full-match stocks at close and selling N trading days later.

Uses a background thread + in-memory task store so the client can poll
for progress instead of waiting on a single long request.
"""
import threading
import uuid
import pandas as pd
from datetime import date, timedelta
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..database import get_db, get_stockdb, SessionLocal, StockDBSession
from ..models import Scheme
from ..schemas.portfolio_backtest import (
    PortfolioBacktestRequest,
    PortfolioBacktestResult,
    PortfolioSummary,
    BatchResult,
    StockTradeResult,
)
from ..engine.evaluators.fundamental import FundamentalEvaluator
from ..engine.evaluators.price import PriceEvaluator
from ..engine.evaluators.flow import FlowEvaluator
from ..engine.evaluators.technical import TechnicalEvaluator
from ..engine.evaluators.sector import SectorEvaluator
from ..engine.scoring import compute_scored_results

router = APIRouter(prefix="/api/portfolio-backtest", tags=["portfolio-backtest"])

# A-share round-trip transaction costs
ROUND_TRIP_COST = 0.00152  # buy 0.025% + sell 0.025%+0.1%+0.002%

# ── In-memory task store ──────────────────────────────────────────────────────
_tasks: dict[str, dict] = {}
_tasks_lock = threading.Lock()


def _set_task(tid: str, **kw):
    with _tasks_lock:
        _tasks[tid].update(kw)


# ── Lightweight scheme/rule wrappers (safe across threads) ───────────────────

class _Rule:
    __slots__ = ("id", "name", "metric", "operator", "value",
                 "data_source", "lookback_days", "params", "enabled")
    def __init__(self, d: dict):
        for k in self.__slots__:
            setattr(self, k, d.get(k))


class _Scheme:
    __slots__ = ("id", "name", "match_mode", "min_match", "rules")
    def __init__(self, d: dict):
        self.id = d["id"]
        self.name = d["name"]
        self.match_mode = d["match_mode"]
        self.min_match = d["min_match"]
        self.rules = [_Rule(r) for r in d["rules"]]


def _scheme_to_dict(scheme: Scheme) -> dict:
    return {
        "id": scheme.id,
        "name": scheme.name,
        "match_mode": scheme.match_mode,
        "min_match": scheme.min_match,
        "rules": [
            {
                "id": r.id, "name": r.name, "metric": r.metric,
                "operator": r.operator, "value": r.value or {},
                "data_source": r.data_source,
                "lookback_days": r.lookback_days or 0,
                "params": r.params, "enabled": r.enabled,
            }
            for r in scheme.rules
        ],
    }


# ── Core per-day evaluation (no DB write) ────────────────────────────────────

def _full_matches_on_date(scheme: _Scheme, trade_date: date, stockdb_conn,
                          preloaded: dict | None = None) -> list[dict]:
    """Return [{ts_code, close}] for all matching stocks on trade_date."""
    rows = stockdb_conn.execute(
        text("""
            SELECT dp.ts_code, dp.close
            FROM daily_price dp
            JOIN stock_basic sb ON sb.ts_code = dp.ts_code
            WHERE dp.trade_date = :d AND sb.list_status = 'L'
            ORDER BY dp.ts_code
        """),
        {"d": trade_date},
    ).fetchall()
    if not rows:
        return []

    universe = [r[0] for r in rows]
    close_map = {r[0]: float(r[1]) if r[1] is not None else None for r in rows}
    enabled = [r for r in scheme.rules if r.enabled]
    total = len(enabled)
    if total == 0:
        return []

    p = preloaded or {}
    evaluators = [
        (FundamentalEvaluator(), {"preloaded_fund_df": p.get("fund"), "preloaded_sb_df": p.get("sb")}),
        (PriceEvaluator(),       {"preloaded_df": p.get("price")}),
        (FlowEvaluator(),        {"preloaded_df": p.get("flow")}),
        (TechnicalEvaluator(),   {"preloaded_df": p.get("price")}),
        (SectorEvaluator(),      {"preloaded_df": p.get("price"), "preloaded_sb_df": p.get("sb")}),
    ]
    merged: dict[str, dict] = {ts: {} for ts in universe}
    for ev, kwargs in evaluators:
        partial = ev.evaluate(enabled, trade_date, universe, stockdb_conn, **kwargs)
        for ts, rule_map in partial.items():
            merged[ts].update(rule_map)

    if scheme.match_mode == "scored":
        top_n = scheme.min_match or 30
        scored = compute_scored_results(merged, enabled, top_n)
        return [{"ts_code": ts, "close": close_map.get(ts), "stock_name": None}
                for ts, _score in scored]

    threshold = total if scheme.match_mode == "all" else (scheme.min_match or total)
    results = []
    for ts in universe:
        matched = sum(1 for v in merged[ts].values() if v)
        if matched >= threshold:
            results.append({"ts_code": ts, "close": close_map.get(ts), "stock_name": None})
    return results


# ── Background task ───────────────────────────────────────────────────────────

def _run_backtest_task(task_id: str, scheme_dict: dict, start: date, end: date, hold_days: int,
                       enabled_rule_ids: list[int] | None = None):
    db = SessionLocal()
    stockdb = StockDBSession()
    try:
        stockdb_conn = stockdb.connection()
        # Filter rules to only those checked by the user
        if enabled_rule_ids is not None:
            id_set = set(enabled_rule_ids)
            scheme_dict = {**scheme_dict,
                           "rules": [r for r in scheme_dict["rules"] if r["id"] in id_set]}
        scheme = _Scheme(scheme_dict)

        # 1. Get all trading days in range
        cal_rows = stockdb_conn.execute(
            text("""
                SELECT cal_date FROM trade_calendar
                WHERE is_open = 1 AND cal_date BETWEEN :s AND :e
                ORDER BY cal_date
            """),
            {"s": start, "e": end},
        ).fetchall()
        trade_days = [r[0] for r in cal_rows]
        total_days = len(trade_days)

        if total_days == 0:
            _set_task(task_id, status="error", error="该时间段内没有交易日数据")
            return

        # ── Pre-fetch all data once for the entire backtest range ─────────────
        _set_task(task_id, message="预加载数据...", current=0, total=total_days)

        # Determine which evaluator types are needed
        enabled_rules = [r for r in scheme.rules if r.enabled]
        rule_metrics = {r.metric for r in enabled_rules}

        PRICE_METRICS_SET = {
            "pct_chg", "close_vs_vwap", "close_vs_ma", "ma_alignment_bull",
            "ma_alignment_diverge", "ma_cross", "new_high", "not_limit",
            "vol_step_up", "vol_vs_ma", "vol_shrink", "n_day_return",
            "consecutive_up_days", "max_drawdown",
            "avg_amount_20d", "price_vs_nd_low", "candlestick_hammer", "three_soldiers",
        }
        TECH_METRICS_SET = {
            "macd_cross", "macd_hist_positive", "kdj_cross", "kdj_j",
            "rsi", "cci", "willr", "atr_expand", "obv_trend", "close_vs_boll",
        }
        FUND_METRICS_SET = {"pe_ttm", "pb", "ps_ttm", "dv_ttm", "turnover_rate", "volume_ratio", "circ_mv", "total_mv"}
        FLOW_METRICS_SET = {
            "net_mf_amount", "net_lg_amount", "net_elg_amount",
            "net_mf_vol_pct", "consecutive_net_inflow", "cumulative_net_inflow", "net_lg_elg_amount",
        }
        BASIC_METRICS_SET = {"exclude_st", "market", "listing_age_days"}
        SECTOR_METRICS_SET = {"sector_pct_chg", "sector_limit_up_count"}

        needs_price = bool(rule_metrics & PRICE_METRICS_SET)
        needs_tech = bool(rule_metrics & TECH_METRICS_SET)
        needs_fund = bool(rule_metrics & FUND_METRICS_SET)
        needs_flow = bool(rule_metrics & FLOW_METRICS_SET)
        needs_basic = bool(rule_metrics & BASIC_METRICS_SET)
        needs_sector = bool(rule_metrics & SECTOR_METRICS_SET)

        preloaded: dict = {}

        # Always fetch stock_basic first — used for name lookup and as codes filter
        # Include industry if sector rules are needed; gracefully degrade if column absent
        base_cols = "ts_code, name"
        if needs_basic:
            base_cols += ", market, list_date"
        if needs_sector:
            try:
                sb_df = pd.read_sql(
                    text(f"SELECT {base_cols}, industry FROM stock_basic WHERE list_status = 'L'"),
                    stockdb_conn,
                )
            except Exception:
                sb_df = pd.read_sql(
                    text(f"SELECT {base_cols} FROM stock_basic WHERE list_status = 'L'"),
                    stockdb_conn,
                )
        else:
            sb_df = pd.read_sql(
                text(f"SELECT {base_cols} FROM stock_basic WHERE list_status = 'L'"),
                stockdb_conn,
            )
        preloaded["sb"] = sb_df
        active_codes = sb_df["ts_code"].tolist()
        name_map_global: dict[str, str] = dict(zip(sb_df["ts_code"], sb_df["name"]))

        # Compute extended start for price pre-fetch
        max_price_lookback = max((r.lookback_days or 0) for r in enabled_rules
                                  if r.metric in PRICE_METRICS_SET) if needs_price else 0
        max_price_lookback = max(max_price_lookback, 65)
        tech_lookback = 110 if needs_tech else 0
        total_lookback = max(max_price_lookback, tech_lookback)
        price_start = trade_days[0] - timedelta(days=total_lookback + 80)

        if needs_price or needs_tech:
            price_df = pd.read_sql(
                text("""
                    SELECT ts_code, trade_date, open, high, low, close, vol, amount, pct_chg
                    FROM daily_price
                    WHERE trade_date BETWEEN :s AND :e
                      AND ts_code = ANY(:codes)
                    ORDER BY ts_code, trade_date
                """),
                stockdb_conn,
                params={"s": price_start, "e": end, "codes": active_codes},
            )
            price_df["trade_date"] = pd.to_datetime(price_df["trade_date"])
            preloaded["price"] = price_df

        if needs_fund:
            fund_df = pd.read_sql(
                text("""
                    SELECT ts_code, trade_date, pe_ttm, pb, ps_ttm, dv_ttm,
                           turnover_rate, volume_ratio, circ_mv, total_mv
                    FROM daily_fundamental
                    WHERE trade_date = ANY(:dates)
                      AND ts_code = ANY(:codes)
                """),
                stockdb_conn,
                params={"dates": trade_days, "codes": active_codes},
            )
            fund_df["trade_date"] = pd.to_datetime(fund_df["trade_date"])
            preloaded["fund"] = fund_df

        if needs_flow:
            max_flow_lookback = max((r.lookback_days or 0) for r in enabled_rules
                                     if r.metric in FLOW_METRICS_SET)
            max_flow_lookback = max(max_flow_lookback, 1)
            flow_start = trade_days[0] - timedelta(days=max_flow_lookback + 15)
            flow_df = pd.read_sql(
                text("""
                    SELECT ts_code, trade_date,
                           buy_sm_amount, sell_sm_amount,
                           buy_md_amount, sell_md_amount,
                           buy_lg_amount, sell_lg_amount,
                           buy_elg_amount, sell_elg_amount,
                           buy_sm_vol, sell_sm_vol,
                           buy_md_vol, sell_md_vol,
                           buy_lg_vol, sell_lg_vol,
                           buy_elg_vol, sell_elg_vol,
                           net_mf_amount, net_mf_vol
                    FROM money_flow
                    WHERE trade_date BETWEEN :s AND :e
                      AND ts_code = ANY(:codes)
                    ORDER BY ts_code, trade_date
                """),
                stockdb_conn,
                params={"s": flow_start, "e": end, "codes": active_codes},
            )
            flow_df["trade_date"] = pd.to_datetime(flow_df["trade_date"])
            preloaded["flow"] = flow_df
        # ─────────────────────────────────────────────────────────────────────

        # Full ordered calendar for sell-date lookup
        ext_cal = stockdb_conn.execute(
            text("""
                SELECT cal_date FROM trade_calendar
                WHERE is_open = 1 AND cal_date >= :s
                ORDER BY cal_date LIMIT 600
            """),
            {"s": start},
        ).fetchall()
        ordered_dates = [r[0] for r in ext_cal]
        date_idx = {d: i for i, d in enumerate(ordered_dates)}

        # 2. Run screening for each day
        batches_raw: dict[date, list] = {}
        for i, td in enumerate(trade_days):
            _set_task(task_id,
                      current=i,
                      total=total_days,
                      message=f"正在筛选 {td}（{i+1}/{total_days}）")
            try:
                matches = _full_matches_on_date(scheme, td, stockdb_conn, preloaded)
            except Exception:
                matches = []

            if matches:
                for m in matches:
                    m["stock_name"] = name_map_global.get(m["ts_code"])
                batches_raw[td] = matches

        if not batches_raw:
            _set_task(task_id, status="error",
                      error="回测期间每日筛选均无完全匹配股票，请检查方案规则或选取其他时间段")
            return

        # 3. Compute sell dates
        buy_dates = sorted(batches_raw.keys())
        sell_date_map: dict[date, date | None] = {}
        for bd in buy_dates:
            idx = date_idx.get(bd)
            if idx is None:
                sell_date_map[bd] = None
                continue
            si = idx + hold_days
            sell_date_map[bd] = ordered_dates[si] if si < len(ordered_dates) else None

        # 4. Fetch sell prices
        _set_task(task_id, message="正在获取卖出价格...")
        unique_sell_dates = list({sd for sd in sell_date_map.values() if sd})
        all_codes = list({m["ts_code"] for stocks in batches_raw.values() for m in stocks})
        sell_prices: dict[tuple, float | None] = {}
        if unique_sell_dates and all_codes:
            pr = stockdb_conn.execute(
                text("""
                    SELECT ts_code, trade_date, close FROM daily_price
                    WHERE ts_code = ANY(:codes) AND trade_date = ANY(:dates)
                """),
                {"codes": all_codes, "dates": unique_sell_dates},
            ).fetchall()
            for r in pr:
                sell_prices[(r[0], r[1])] = float(r[2]) if r[2] is not None else None

        # 5. Compute returns
        batches: list[BatchResult] = []
        equity = 1.0
        equity_curve = [{"date": "start", "value": 0.0}]
        batch_returns: list[float] = []

        for bd in buy_dates:
            sd = sell_date_map.get(bd)
            stocks_in = batches_raw[bd]
            stock_results: list[StockTradeResult] = []
            net_rets: list[float] = []

            for m in stocks_in:
                bp = m["close"]
                sp = sell_prices.get((m["ts_code"], sd)) if sd else None
                raw = net = None
                if bp and sp and bp > 0:
                    raw = round((sp / bp - 1) * 100, 4)
                    net = round(raw - ROUND_TRIP_COST * 100, 4)
                    net_rets.append(net)
                stock_results.append(StockTradeResult(
                    ts_code=m["ts_code"],
                    stock_name=m.get("stock_name"),
                    buy_price=bp,
                    sell_price=sp,
                    raw_return=raw,
                    net_return=net,
                ))

            avg_ret = round(sum(net_rets) / len(net_rets), 4) if net_rets else None
            if avg_ret is not None:
                equity *= (1 + avg_ret / 100)
                batch_returns.append(avg_ret)
                equity_curve.append({"date": str(bd), "value": round((equity - 1) * 100, 4)})

            batches.append(BatchResult(
                buy_date=str(bd),
                sell_date=str(sd) if sd else None,
                stock_count=len(stocks_in),
                valid_count=len(net_rets),
                avg_net_return=avg_ret,
                stocks=stock_results,
            ))

        # 6. Summary
        cum_ret = round((equity - 1) * 100, 4)
        cal_days = max((end - start).days, 1)
        ann = round(((1 + cum_ret / 100) ** (365 / cal_days) - 1) * 100, 2)
        win_rate = round(sum(1 for r in batch_returns if r > 0) / len(batch_returns) * 100, 1) if batch_returns else 0.0
        avg_ret = round(sum(batch_returns) / len(batch_returns), 4) if batch_returns else 0.0

        peak = 1.0; eq_v = 1.0; max_dd = 0.0
        for r in batch_returns:
            eq_v *= (1 + r / 100)
            if eq_v > peak: peak = eq_v
            dd = (eq_v - peak) / peak * 100
            if dd < max_dd: max_dd = dd

        total_trades = sum(b.valid_count for b in batches)
        summary = PortfolioSummary(
            total_batches=len(batches),
            covered_days=len(batches),
            total_trading_days=total_days,
            coverage_pct=100.0,
            cumulative_return=cum_ret,
            annualized_return=ann,
            win_rate=win_rate,
            avg_batch_return=avg_ret,
            max_drawdown=round(max_dd, 2),
            total_trades=total_trades,
            avg_stocks_per_batch=round(total_trades / len(batches), 1) if batches else 0.0,
            transaction_cost_pct=round(ROUND_TRIP_COST * 100, 3),
        )

        result = PortfolioBacktestResult(
            scheme_id=scheme.id,
            scheme_name=scheme.name,
            start_date=str(start),
            end_date=str(end),
            hold_days=hold_days,
            summary=summary,
            equity_curve=equity_curve,
            batches=batches,
        )
        _set_task(task_id,
                  status="done",
                  current=total_days,
                  total=total_days,
                  message="回测完成",
                  result=result.model_dump())
    except Exception as e:
        import traceback
        _set_task(task_id, status="error", error=str(e))
        traceback.print_exc()
    finally:
        db.close()
        stockdb.close()


# ── API endpoints ─────────────────────────────────────────────────────────────

@router.post("/start")
def start_portfolio_backtest(
    body: PortfolioBacktestRequest,
    db: Session = Depends(get_db),
):
    try:
        start = date.fromisoformat(body.start_date)
        end = date.fromisoformat(body.end_date)
    except ValueError:
        raise HTTPException(400, "Invalid date format, use YYYY-MM-DD")
    if start > end:
        raise HTTPException(400, "start_date must be before end_date")
    if body.hold_days not in (1, 2, 3):
        raise HTTPException(400, "hold_days must be 1, 2 or 3")

    scheme = db.get(Scheme, body.scheme_id)
    if not scheme:
        raise HTTPException(404, f"Scheme {body.scheme_id} not found")

    scheme_dict = _scheme_to_dict(scheme)

    task_id = str(uuid.uuid4())
    with _tasks_lock:
        _tasks[task_id] = {
            "status": "running",
            "current": 0,
            "total": 0,
            "message": "初始化中...",
            "result": None,
            "error": None,
        }

    t = threading.Thread(
        target=_run_backtest_task,
        args=(task_id, scheme_dict, start, end, body.hold_days, body.enabled_rule_ids),
        daemon=True,
    )
    t.start()
    return {"task_id": task_id}


@router.get("/progress/{task_id}")
def get_progress(task_id: str):
    with _tasks_lock:
        task = _tasks.get(task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    pct = 0
    if task["total"] > 0:
        pct = round(task["current"] / task["total"] * 100)
    return {
        "status": task["status"],
        "current": task["current"],
        "total": task["total"],
        "pct": pct,
        "message": task["message"],
        "result": task["result"] if task["status"] == "done" else None,
        "error": task["error"],
    }
