"""
Single-stock backtester.
Pre-fetches all data for one stock over an extended range,
then evaluates each rule per trading date entirely in memory.
"""
from datetime import date, timedelta
import warnings
import pandas as pd
import numpy as np
from sqlalchemy import text
from .evaluators.base import apply_operator

# Number of extra calendar days to fetch before start_date for MA/lookback context
LOOKBACK_BUFFER = 120


def _fmt(val, suffix="", decimals=2):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "-"
    return f"{val:.{decimals}f}{suffix}"


def run_single_stock_backtest(
    ts_code: str,
    start_date: date,
    end_date: date,
    schemes: list,
    stockdb_conn,
) -> dict:
    """
    Returns:
    {
      "ts_code": "...", "stock_name": "...",
      "price_series": [...],
      "schemes": [{
        "scheme_id": ..., "scheme_name": ..., "match_mode": ...,
        "min_match": ..., "total_rules": ..., "rules": [...],
        "daily": [{"date": ..., "matched": ..., "is_matched": ...,
                   "rule_results": {rule_id: {"passed": bool, "display": str}}}],
        "stats": {"total_days": ..., "matched_days": ..., "match_rate": ...}
      }]
    }
    """
    fetch_start = start_date - timedelta(days=LOOKBACK_BUFFER)

    # ---- Stock name ----
    name_row = stockdb_conn.execute(
        text("SELECT name FROM stock_basic WHERE ts_code = :c"),
        {"c": ts_code},
    ).fetchone()
    stock_name = name_row[0] if name_row else None

    # ---- Price data ----
    price_df = pd.read_sql(
        text("""
            SELECT trade_date, open, high, low, close, vol, amount, pct_chg
            FROM daily_price
            WHERE ts_code = :c AND trade_date BETWEEN :s AND :e
            ORDER BY trade_date
        """),
        stockdb_conn,
        params={"c": ts_code, "s": fetch_start, "e": end_date},
    )
    if price_df.empty:
        return {"ts_code": ts_code, "stock_name": stock_name,
                "price_series": [], "schemes": []}

    price_df["trade_date"] = pd.to_datetime(price_df["trade_date"])
    price_df = price_df.set_index("trade_date").sort_index()

    # ---- Fundamental data ----
    fund_df = pd.read_sql(
        text("""
            SELECT trade_date, pe_ttm, pb, ps_ttm, dv_ttm,
                   turnover_rate, volume_ratio, circ_mv, total_mv
            FROM daily_fundamental
            WHERE ts_code = :c AND trade_date BETWEEN :s AND :e
            ORDER BY trade_date
        """),
        stockdb_conn,
        params={"c": ts_code, "s": fetch_start, "e": end_date},
    )
    fund_df["trade_date"] = pd.to_datetime(fund_df["trade_date"])
    fund_df = fund_df.set_index("trade_date").sort_index() if not fund_df.empty else pd.DataFrame()

    # ---- Money flow data ----
    flow_df = pd.read_sql(
        text("""
            SELECT trade_date,
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
            WHERE ts_code = :c AND trade_date BETWEEN :s AND :e
            ORDER BY trade_date
        """),
        stockdb_conn,
        params={"c": ts_code, "s": fetch_start, "e": end_date},
    )
    if not flow_df.empty:
        flow_df["trade_date"] = pd.to_datetime(flow_df["trade_date"])
        flow_df = flow_df.set_index("trade_date").sort_index()
        flow_df["net_lg"] = flow_df["buy_lg_amount"].fillna(0) - flow_df["sell_lg_amount"].fillna(0)
        flow_df["net_elg"] = flow_df["buy_elg_amount"].fillna(0) - flow_df["sell_elg_amount"].fillna(0)
        flow_df["net_lg_elg"] = flow_df["net_lg"] + flow_df["net_elg"]
        total_vol = (
            flow_df["buy_sm_vol"].fillna(0) + flow_df["sell_sm_vol"].fillna(0) +
            flow_df["buy_md_vol"].fillna(0) + flow_df["sell_md_vol"].fillna(0) +
            flow_df["buy_lg_vol"].fillna(0) + flow_df["sell_lg_vol"].fillna(0) +
            flow_df["buy_elg_vol"].fillna(0) + flow_df["sell_elg_vol"].fillna(0)
        )
        flow_df["net_mf_vol_pct"] = (
            flow_df["net_mf_vol"].fillna(0) / total_vol.replace(0, float("nan")) * 100
        )
    else:
        flow_df = pd.DataFrame()

    # ---- Pre-compute technical indicators (pandas_ta) ----
    tech_df = _compute_technical(price_df)

    # ---- Stock basic (for filter rules) ----
    sb_row = stockdb_conn.execute(
        text("SELECT name, market, list_date FROM stock_basic WHERE ts_code = :c"),
        {"c": ts_code},
    ).fetchone()
    stock_basic = {"name": sb_row[0], "market": sb_row[1], "list_date": sb_row[2]} if sb_row else {}

    # Trading dates in the requested range
    trade_dates = price_df.index[price_df.index >= pd.Timestamp(start_date)].tolist()

    # ---- Price series for frontend chart ----
    price_series = []
    for ts_dt in trade_dates:
        row = price_df.loc[ts_dt]
        price_series.append({
            "date": ts_dt.strftime("%Y-%m-%d"),
            "open": float(row["open"]) if not pd.isna(row["open"]) else None,
            "high": float(row["high"]) if not pd.isna(row["high"]) else None,
            "low": float(row["low"]) if not pd.isna(row["low"]) else None,
            "close": float(row["close"]) if not pd.isna(row["close"]) else None,
            "vol": float(row["vol"]) if not pd.isna(row["vol"]) else None,
            "pct_chg": float(row["pct_chg"]) if not pd.isna(row["pct_chg"]) else None,
        })

    # ---- Evaluate schemes ----
    scheme_results = []
    for scheme in schemes:
        enabled_rules = [r for r in scheme.rules if r.enabled]
        total_rules = len(enabled_rules)
        min_match = scheme.min_match or total_rules

        daily = []
        for ts_dt in trade_dates:
            rule_results = {}
            for rule in enabled_rules:
                passed, display = _evaluate_rule(
                    rule, ts_dt, price_df, fund_df, flow_df, tech_df, stock_basic
                )
                # Ensure passed is always a native Python bool (not numpy.bool_)
                rule_results[str(rule.id)] = {"passed": bool(passed), "display": display}

            matched = sum(1 for v in rule_results.values() if v["passed"])
            is_matched = (
                matched == total_rules or
                (scheme.match_mode == "partial" and matched >= min_match)
            )
            daily.append({
                "date": ts_dt.strftime("%Y-%m-%d"),
                "matched": matched,
                "is_matched": is_matched,
                "rule_results": rule_results,
            })

        total_days = len(daily)
        matched_days = sum(1 for d in daily if d["is_matched"])
        scheme_results.append({
            "scheme_id": scheme.id,
            "scheme_name": scheme.name,
            "match_mode": scheme.match_mode,
            "min_match": scheme.min_match,
            "total_rules": total_rules,
            "rules": [{"id": r.id, "name": r.name, "metric": r.metric} for r in enabled_rules],
            "daily": daily,
            "stats": {
                "total_days": total_days,
                "matched_days": matched_days,
                "match_rate": round(matched_days / total_days * 100, 1) if total_days else 0,
            },
        })

    return {
        "ts_code": ts_code,
        "stock_name": stock_name,
        "price_series": price_series,
        "schemes": scheme_results,
    }


def _compute_technical(price_df: pd.DataFrame) -> pd.DataFrame:
    """Compute pandas_ta indicators on OHLCV data."""
    try:
        import pandas_ta as ta
    except ImportError:
        return pd.DataFrame(index=price_df.index)

    df = price_df[["open", "high", "low", "close", "vol"]].copy()
    df.columns = ["open", "high", "low", "close", "volume"]

    warnings.filterwarnings("ignore")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        df.ta.macd(append=True)        # MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9
        df.ta.stoch(append=True)       # STOCHk_14_3_3, STOCHd_14_3_3 (KDJ approx)
        df.ta.rsi(append=True)         # RSI_14
        df.ta.bbands(append=True)      # BBL_5_2.0, BBM_5_2.0, BBU_5_2.0
        df.ta.cci(append=True)         # CCI_14_0.015
        df.ta.willr(append=True)       # WILLR_14
        df.ta.atr(append=True)         # ATRr_14

    return df


def _get_price_at(price_df: pd.DataFrame, dt: pd.Timestamp, col: str):
    if dt in price_df.index:
        val = price_df.loc[dt, col]
        return float(val) if not pd.isna(val) else None
    return None


def _get_fund_at(fund_df: pd.DataFrame, dt: pd.Timestamp, col: str):
    if fund_df.empty or dt not in fund_df.index:
        return None
    val = fund_df.loc[dt, col]
    return float(val) if not pd.isna(val) else None


def _get_flow_at(flow_df: pd.DataFrame, dt: pd.Timestamp, col: str):
    if flow_df.empty or dt not in flow_df.index:
        return None
    val = flow_df.loc[dt, col]
    return float(val) if not pd.isna(val) else None


def _ma(closes: np.ndarray, n: int):
    """Last MA(n) from an array of close prices."""
    if len(closes) < n:
        return None
    return float(np.mean(closes[-n:]))


def _evaluate_rule(rule, dt: pd.Timestamp, price_df, fund_df, flow_df, tech_df, stock_basic):
    """Returns (passed: bool, display: str)."""
    metric = rule.metric
    op = rule.operator
    v = rule.value or {}

    # --- Fundamental metrics ---
    if metric in {"pe_ttm", "pb", "ps_ttm", "dv_ttm", "turnover_rate", "volume_ratio", "circ_mv", "total_mv"}:
        val = _get_fund_at(fund_df, dt, metric)
        passed = apply_operator(val, op, v)
        suffix = "亿" if metric == "circ_mv" else ("%"  if metric in {"turnover_rate"} else "")
        display_val = val / 10000 if metric == "circ_mv" and val is not None else val
        return passed, _fmt(display_val, suffix)

    # --- Price today ---
    if metric == "pct_chg":
        val = _get_price_at(price_df, dt, "pct_chg")
        return apply_operator(val, op, v), _fmt(val, "%")

    if metric == "close_vs_vwap":
        row = price_df.loc[dt] if dt in price_df.index else None
        if row is None:
            return False, "-"
        close = float(row["close"]) if not pd.isna(row["close"]) else None
        vol = float(row["vol"]) if not pd.isna(row["vol"]) else None
        amount = float(row["amount"]) if not pd.isna(row["amount"]) else None
        if close is None or vol is None or amount is None or vol == 0:
            return False, "-"
        vwap = amount * 1000 / (vol * 100)
        passed = close > vwap
        return passed, f"{close:.2f}>{vwap:.2f}" if passed else f"{close:.2f}<{vwap:.2f}"

    # --- MA / lookback metrics ---
    closes_up_to = price_df.loc[:dt, "close"].dropna().values

    if metric == "close_vs_ma":
        # support both "period" (new) and "n" (legacy) parameter names
        n = int(v.get("period", v.get("n", 20)))
        if rule.params:
            n = int(rule.params.get("period", n))
        ma_val = _ma(closes_up_to, n)
        close = _get_price_at(price_df, dt, "close")
        if ma_val is None or close is None:
            return False, "-"
        passed = apply_operator(close, op, {"v": ma_val})
        return passed, f"C={close:.2f} MA{n}={ma_val:.2f}"

    if metric == "ma_alignment_bull":
        ma5 = _ma(closes_up_to, 5)
        ma10 = _ma(closes_up_to, 10)
        ma20 = _ma(closes_up_to, 20)
        ma60 = _ma(closes_up_to, 60)
        if any(x is None for x in [ma5, ma10, ma20, ma60]):
            return False, "-"
        passed = ma5 > ma10 > ma20 > ma60
        return passed, f"MA5={ma5:.2f} MA10={ma10:.2f} MA20={ma20:.2f} MA60={ma60:.2f}"

    if metric == "ma_alignment_diverge":
        ma5 = _ma(closes_up_to, 5)
        ma10 = _ma(closes_up_to, 10)
        ma20 = _ma(closes_up_to, 20)
        ma60 = _ma(closes_up_to, 60)
        if any(x is None for x in [ma5, ma10, ma20, ma60]):
            return False, "-"
        order_ok = ma5 > ma10 > ma20 > ma60
        # Slope check: compare to 3 days ago
        old_closes = closes_up_to[:-3] if len(closes_up_to) > 3 else np.array([])
        ma5_old = _ma(old_closes, 5)
        ma10_old = _ma(old_closes, 10)
        ma20_old = _ma(old_closes, 20)
        ma60_old = _ma(old_closes, 60)
        if any(x is None for x in [ma5_old, ma10_old, ma20_old, ma60_old]):
            return order_ok, f"5>{ma5:.2f} 10>{ma10:.2f} 20>{ma20:.2f} 60>{ma60:.2f}"
        slope_ok = ma5 > ma5_old and ma10 > ma10_old and ma20 > ma20_old and ma60 > ma60_old
        passed = order_ok and slope_ok
        return passed, f"MA5={ma5:.2f} MA10={ma10:.2f} MA20={ma20:.2f} MA60={ma60:.2f}"

    if metric == "ma_cross":
        fast = int(v.get("fast", 5))
        slow = int(v.get("slow", 20))
        days_window = int(v.get("days", 1))
        ma_fast = _ma(closes_up_to, fast)
        ma_slow = _ma(closes_up_to, slow)
        if ma_fast is None or ma_slow is None:
            return False, "-"
        # Check if fast MA crossed above slow MA within the last `days_window` trading days
        crossed = False
        for i in range(days_window):
            end = len(closes_up_to) - i
            if end < slow + 1:
                break
            curr_fast = _ma(closes_up_to[:end], fast)
            curr_slow = _ma(closes_up_to[:end], slow)
            prev_fast = _ma(closes_up_to[:end - 1], fast)
            prev_slow = _ma(closes_up_to[:end - 1], slow)
            if None in (curr_fast, curr_slow, prev_fast, prev_slow):
                continue
            if prev_fast <= prev_slow and curr_fast > curr_slow:
                crossed = True
                break
        return crossed, f"MA{fast}={ma_fast:.2f} MA{slow}={ma_slow:.2f}"

    if metric == "vol_vs_ma":
        n = int(v.get("n", 20))
        vols_up_to = price_df.loc[:dt, "vol"].dropna().values
        if len(vols_up_to) < n + 1:
            return False, "-"
        today_vol = vols_up_to[-1]
        ma_vol = float(np.mean(vols_up_to[-n-1:-1]))
        ratio = float(v.get("ratio", 1.2))
        passed = today_vol >= ma_vol * ratio
        return passed, f"V={today_vol:.0f} MA{n}V={ma_vol:.0f}"

    if metric == "vol_step_up":
        lookback = rule.lookback_days or 8
        min_consec = int((rule.params or {}).get("min_consec", 3))
        vols_up_to = price_df.loc[:dt, "vol"].dropna().values
        if len(vols_up_to) < lookback:
            return False, "-"
        recent_vol = vols_up_to[-lookback:]
        up = np.diff(recent_vol) > 0
        # Check for min_consec consecutive increasing days
        need_transitions = min_consec - 1
        found = False
        for j in range(len(up) - need_transitions + 1):
            if np.all(up[j:j + need_transitions]):
                found = True
                break
        return found, f"近{lookback}日量" + ("递增✓" if found else "递增✗")

    if metric == "vol_shrink":
        n = int(v.get("n", 5))
        vols_up_to = price_df.loc[:dt, "vol"].dropna().values
        if len(vols_up_to) < n + 1:
            return False, "-"
        today_vol = vols_up_to[-1]
        ma_vol = float(np.mean(vols_up_to[-n-1:-1]))
        ratio = float(v.get("ratio", 0.7))
        passed = today_vol <= ma_vol * ratio
        return passed, f"V={today_vol:.0f}"

    if metric == "n_day_return":
        n = int(v.get("n", 5))
        if len(closes_up_to) < n + 1:
            return False, "-"
        ret = (closes_up_to[-1] / closes_up_to[-n-1] - 1) * 100
        passed = apply_operator(ret, op, v)
        return passed, _fmt(ret, "%")

    if metric == "consecutive_up_days":
        n = int(v.get("n", 3))
        if len(closes_up_to) < n + 1:
            return False, "-"
        diffs = np.diff(closes_up_to[-n-1:])
        passed = bool(np.all(diffs > 0))
        return passed, f"连涨{n}日" + ("✓" if passed else "✗")

    if metric == "new_high":
        n = int(v.get("n", 20))
        highs_up_to = price_df.loc[:dt, "high"].dropna().values
        if len(highs_up_to) < n:
            return False, "-"
        today_high = highs_up_to[-1]
        prev_high = float(np.max(highs_up_to[-n:-1]))
        passed = today_high >= prev_high
        return passed, f"H={today_high:.2f} MaxH={prev_high:.2f}"

    if metric == "not_limit":
        val = _get_price_at(price_df, dt, "pct_chg")
        if val is None:
            return True, "-"
        passed = abs(val) < 9.8
        return passed, _fmt(val, "%")

    # --- Flow metrics ---
    if metric == "net_mf_amount":
        val = _get_flow_at(flow_df, dt, "net_mf_amount")
        return apply_operator(val, op, v), _fmt(val if val else None, "万") if val else "-"

    if metric == "net_lg_amount":
        val = _get_flow_at(flow_df, dt, "net_lg")
        return apply_operator(val, op, v), _fmt(val, "万") if val is not None else "-"

    if metric == "net_elg_amount":
        val = _get_flow_at(flow_df, dt, "net_elg")
        return apply_operator(val, op, v), _fmt(val, "万") if val is not None else "-"

    if metric == "net_lg_elg_amount":
        val = _get_flow_at(flow_df, dt, "net_lg_elg")
        return apply_operator(val, op, v), _fmt(val, "万") if val is not None else "-"

    if metric == "net_mf_vol_pct":
        val = _get_flow_at(flow_df, dt, "net_mf_vol_pct")
        return apply_operator(val, op, v), _fmt(val, "%") if val is not None else "-"

    if metric == "consecutive_net_inflow":
        if flow_df.empty:
            return False, "-"
        min_days = int(v.get("days", 3))
        recent = flow_df.loc[:dt, "net_mf_amount"].dropna().tail(min_days)
        passed = len(recent) >= min_days and all(x > 0 for x in recent)
        return passed, f"连{min_days}日净流入" + ("✓" if passed else "✗")

    if metric == "cumulative_net_inflow":
        if flow_df.empty:
            return False, "-"
        days = int(v.get("days", 5))
        recent = flow_df.loc[:dt, "net_mf_amount"].dropna().tail(days)
        total = float(recent.sum())
        passed = apply_operator(total, op, v)
        return passed, _fmt(total, "万")

    # --- Technical indicators ---
    if not tech_df.empty and dt in tech_df.index:
        tech_row = tech_df.loc[dt]
    else:
        tech_row = None

    if metric == "macd_cross":
        if tech_row is None:
            return False, "-"
        macd = tech_row.get("MACD_12_26_9")
        signal = tech_row.get("MACDs_12_26_9")
        hist = tech_row.get("MACDh_12_26_9")
        if pd.isna(macd) or pd.isna(signal):
            return False, "-"
        passed = float(macd) > float(signal)
        return passed, f"MACD={float(macd):.3f}"

    if metric == "macd_hist":
        if tech_row is None:
            return False, "-"
        hist = tech_row.get("MACDh_12_26_9")
        if hist is None or pd.isna(hist):
            return False, "-"
        passed = apply_operator(float(hist), op, v)
        return passed, _fmt(float(hist), "", 3)

    if metric == "kdj_golden_cross":
        if tech_row is None:
            return False, "-"
        k = tech_row.get("STOCHk_14_3_3")
        d = tech_row.get("STOCHd_14_3_3")
        if k is None or d is None or pd.isna(k) or pd.isna(d):
            return False, "-"
        passed = float(k) > float(d)
        return passed, f"K={float(k):.1f} D={float(d):.1f}"

    if metric == "kdj_k":
        if tech_row is None:
            return False, "-"
        k = tech_row.get("STOCHk_14_3_3")
        if k is None or pd.isna(k):
            return False, "-"
        passed = apply_operator(float(k), op, v)
        return passed, _fmt(float(k))

    if metric == "rsi":
        if tech_row is None:
            return False, "-"
        rsi = tech_row.get("RSI_14")
        if rsi is None or pd.isna(rsi):
            return False, "-"
        passed = apply_operator(float(rsi), op, v)
        return passed, _fmt(float(rsi))

    if metric == "boll_position":
        if tech_row is None:
            return False, "-"
        close = _get_price_at(price_df, dt, "close")
        mid = tech_row.get("BBM_5_2.0")
        upper = tech_row.get("BBU_5_2.0")
        lower = tech_row.get("BBL_5_2.0")
        if close is None or any(pd.isna(x) for x in [mid, upper, lower] if x is not None):
            return False, "-"
        pos = v.get("position", "above_mid")
        if pos == "above_mid":
            passed = close > float(mid)
        elif pos == "below_mid":
            passed = close < float(mid)
        elif pos == "near_upper":
            passed = close >= float(upper) * 0.98
        elif pos == "near_lower":
            passed = close <= float(lower) * 1.02
        else:
            passed = False
        return passed, f"C={close:.2f} Mid={float(mid):.2f}"

    if metric == "cci":
        if tech_row is None:
            return False, "-"
        cci = tech_row.get("CCI_14_0.015")
        if cci is None or pd.isna(cci):
            return False, "-"
        passed = apply_operator(float(cci), op, v)
        return passed, _fmt(float(cci))

    if metric == "willr":
        if tech_row is None:
            return False, "-"
        wr = tech_row.get("WILLR_14")
        if wr is None or pd.isna(wr):
            return False, "-"
        passed = apply_operator(float(wr), op, v)
        return passed, _fmt(float(wr))

    if metric == "atr":
        if tech_row is None:
            return False, "-"
        atr = tech_row.get("ATRr_14")
        if atr is None or pd.isna(atr):
            return False, "-"
        passed = apply_operator(float(atr), op, v)
        return passed, _fmt(float(atr))

    # --- Stock basic filters ---
    if metric == "exclude_st":
        name = stock_basic.get("name", "") or ""
        passed = "ST" not in name.upper() and "*" not in name
        return passed, name

    if metric == "market":
        passed = str(stock_basic.get("market", "")) == str(v.get("v", ""))
        return passed, str(stock_basic.get("market", ""))

    if metric == "listing_age_days":
        list_date = stock_basic.get("list_date")
        if list_date is None:
            return False, "-"
        age = (dt.date() - list_date).days
        passed = apply_operator(age, op, v)
        return passed, f"{age}天"

    # Fallback
    return False, "-"
