"""
Screening engine executor.
Orchestrates all evaluators and stores results.
"""
import time
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..models import Scheme, ScreeningResult, ScreeningResultDetail
from .evaluators.fundamental import FundamentalEvaluator
from .evaluators.price import PriceEvaluator
from .evaluators.flow import FlowEvaluator
from .evaluators.technical import TechnicalEvaluator
from .evaluators.sector import SectorEvaluator
from .scoring import compute_scored_results


def run_screening(scheme: Scheme, trade_date: date, db: Session, stockdb_conn) -> ScreeningResult:
    """
    Execute full screening pipeline for a scheme on a given trade date.
    Returns the ScreeningResult (saved to DB).
    """
    t0 = time.time()

    # 1. Get stock universe (all listed A-share stocks with data on trade_date)
    rows = stockdb_conn.execute(
        text("""
            SELECT dp.ts_code, sb.name
            FROM daily_price dp
            JOIN stock_basic sb ON sb.ts_code = dp.ts_code
            WHERE dp.trade_date = :d
              AND sb.list_status = 'L'
            ORDER BY dp.ts_code
        """),
        {"d": trade_date},
    ).fetchall()

    if not rows:
        result = ScreeningResult(
            scheme_id=scheme.id,
            trade_date=trade_date,
            total_stocks=0,
            full_match_count=0,
            partial_match_count=0,
            duration_seconds=time.time() - t0,
        )
        db.add(result)
        db.commit()
        db.refresh(result)
        return result

    stock_universe = [r[0] for r in rows]
    stock_names = {r[0]: r[1] for r in rows}
    enabled_rules = [r for r in scheme.rules if r.enabled]
    total_rules = len(enabled_rules)

    # 2. Route rules to evaluators
    evaluators = [
        FundamentalEvaluator(),
        PriceEvaluator(),
        FlowEvaluator(),
        TechnicalEvaluator(),
        SectorEvaluator(),
    ]

    # Merge results: {ts_code: {rule_id: bool}}
    merged: dict[str, dict[int, bool]] = {ts: {} for ts in stock_universe}

    for evaluator in evaluators:
        partial = evaluator.evaluate(enabled_rules, trade_date, stock_universe, stockdb_conn)
        for ts, rule_map in partial.items():
            merged[ts].update(rule_map)

    # 3. Snapshot data for display
    snap_rows = stockdb_conn.execute(
        text("""
            SELECT dp.ts_code, dp.close, dp.pct_chg, dp.vol,
                   df.turnover_rate, df.circ_mv, df.volume_ratio, df.pe_ttm, df.pb
            FROM daily_price dp
            LEFT JOIN daily_fundamental df
              ON df.ts_code = dp.ts_code AND df.trade_date = dp.trade_date
            WHERE dp.trade_date = :d
        """),
        {"d": trade_date},
    ).fetchall()
    snap_map = {r[0]: {"close": r[1], "pct_chg": r[2], "vol": r[3],
                       "turnover_rate": r[4], "circ_mv": r[5],
                       "volume_ratio": r[6], "pe_ttm": r[7], "pb": r[8]} for r in snap_rows}

    # 4. Classify results
    match_mode = scheme.match_mode
    min_match = scheme.min_match or total_rules

    full_match_count = 0
    partial_match_count = 0
    details = []

    if match_mode == "scored":
        # Weighted layer scoring: top min_match stocks by score
        top_n = scheme.min_match or 30
        scored = compute_scored_results(merged, enabled_rules, top_n)
        full_match_count = len(scored)
        for ts, score in scored:
            rule_res = merged.get(ts, {})
            matched = sum(1 for v in rule_res.values() if v)
            snap = snap_map.get(ts, {})
            rr = {str(k): bool(v) for k, v in rule_res.items()}
            rr["_score"] = round(score, 4)
            details.append(ScreeningResultDetail(
                ts_code=ts,
                stock_name=stock_names.get(ts),
                matched_rules=matched,
                total_rules=total_rules,
                is_full_match=True,
                rule_results=rr,
                close=snap.get("close"),
                pct_chg=snap.get("pct_chg"),
                vol=snap.get("vol"),
                turnover_rate=snap.get("turnover_rate"),
                circ_mv=snap.get("circ_mv"),
                volume_ratio=snap.get("volume_ratio"),
                pe_ttm=snap.get("pe_ttm"),
                pb=snap.get("pb"),
            ))
        # Already sorted by score desc from compute_scored_results
    else:
        for ts in stock_universe:
            rule_res = merged.get(ts, {})
            matched = sum(1 for v in rule_res.values() if v)

            is_full = matched == total_rules
            is_partial = (match_mode == "partial" and matched >= min_match and not is_full)

            if not is_full and not is_partial:
                continue

            if is_full:
                full_match_count += 1
            elif is_partial:
                partial_match_count += 1

            snap = snap_map.get(ts, {})
            details.append(ScreeningResultDetail(
                ts_code=ts,
                stock_name=stock_names.get(ts),
                matched_rules=matched,
                total_rules=total_rules,
                is_full_match=is_full,
                rule_results={str(k): bool(v) for k, v in rule_res.items()},
                close=snap.get("close"),
                pct_chg=snap.get("pct_chg"),
                vol=snap.get("vol"),
                turnover_rate=snap.get("turnover_rate"),
                circ_mv=snap.get("circ_mv"),
                volume_ratio=snap.get("volume_ratio"),
                pe_ttm=snap.get("pe_ttm"),
                pb=snap.get("pb"),
            ))

        # Sort: full matches first, then by matched_rules desc
        details.sort(key=lambda d: (-int(d.is_full_match), -d.matched_rules))

    # 5. Save
    result = ScreeningResult(
        scheme_id=scheme.id,
        trade_date=trade_date,
        total_stocks=len(stock_universe),
        full_match_count=full_match_count,
        partial_match_count=partial_match_count,
        duration_seconds=round(time.time() - t0, 2),
    )
    db.add(result)
    db.flush()
    for d in details:
        d.result_id = result.id
        db.add(d)
    db.commit()
    db.refresh(result)
    return result
