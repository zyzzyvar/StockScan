"""
Sector/industry resonance evaluator.
Metrics: sector_pct_chg, sector_limit_up_count

Requires stock_basic.industry column (TuShare field).
Gracefully returns False for all rules if the column is absent.
"""
from datetime import date
import pandas as pd
from sqlalchemy import text
from .base import BaseEvaluator, apply_operator

SECTOR_METRICS = {"sector_pct_chg", "sector_limit_up_count"}


class SectorEvaluator(BaseEvaluator):
    def evaluate(
        self,
        rules,
        trade_date: date,
        stock_universe: list[str],
        stockdb_conn,
        preloaded_df=None,
        preloaded_sb_df=None,
    ) -> dict:
        results: dict[str, dict[int, bool]] = {ts: {} for ts in stock_universe}
        sector_rules = [r for r in rules if r.metric in SECTOR_METRICS]
        if not sector_rules:
            return results

        def _fail_all():
            for r in sector_rules:
                for ts in stock_universe:
                    results[ts][r.id] = False
            return results

        # ── Industry mapping ──────────────────────────────────────────────────
        if preloaded_sb_df is not None:
            sb = preloaded_sb_df
            if "ts_code" in sb.columns:
                sb = sb.set_index("ts_code")
        else:
            try:
                sb = pd.read_sql(
                    text("SELECT ts_code, industry FROM stock_basic WHERE list_status = 'L'"),
                    stockdb_conn,
                ).set_index("ts_code")
            except Exception:
                return _fail_all()

        if "industry" not in sb.columns:
            return _fail_all()

        # ── Daily pct_chg for this date ────────────────────────────────────────
        if preloaded_df is not None:
            today_price = preloaded_df[
                preloaded_df["trade_date"] == pd.Timestamp(trade_date)
            ][["ts_code", "pct_chg"]].set_index("ts_code")
        else:
            today_price = pd.read_sql(
                text("SELECT ts_code, pct_chg FROM daily_price WHERE trade_date = :d"),
                stockdb_conn,
                params={"d": trade_date},
            ).set_index("ts_code")

        if today_price.empty:
            return _fail_all()

        # ── Aggregate by industry ─────────────────────────────────────────────
        stats: dict[str, dict] = {}
        for ts_code in today_price.index:
            if ts_code not in sb.index:
                continue
            industry = sb.loc[ts_code, "industry"]
            if not industry or (isinstance(industry, float) and pd.isna(industry)):
                continue
            pct = float(today_price.loc[ts_code, "pct_chg"] or 0)
            if industry not in stats:
                stats[industry] = {"count": 0, "pct_sum": 0.0, "limit_up": 0}
            stats[industry]["count"] += 1
            stats[industry]["pct_sum"] += pct
            if pct >= 9.8:
                stats[industry]["limit_up"] += 1

        for ind in stats:
            n = stats[ind]["count"]
            stats[ind]["avg_pct_chg"] = stats[ind]["pct_sum"] / n if n else 0.0

        # ── Evaluate per stock ────────────────────────────────────────────────
        for r in sector_rules:
            v = r.value or {}
            for ts in stock_universe:
                if ts not in sb.index:
                    results[ts][r.id] = False
                    continue
                industry = sb.loc[ts, "industry"]
                if not industry or (isinstance(industry, float) and pd.isna(industry)):
                    results[ts][r.id] = False
                    continue
                if industry not in stats:
                    results[ts][r.id] = False
                    continue
                s = stats[industry]
                if r.metric == "sector_pct_chg":
                    results[ts][r.id] = apply_operator(s["avg_pct_chg"], r.operator, v)
                elif r.metric == "sector_limit_up_count":
                    results[ts][r.id] = apply_operator(s["limit_up"], r.operator, v)

        return results
