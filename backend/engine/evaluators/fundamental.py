"""
Fundamental evaluator: PE, PB, PS, turnover_rate, volume_ratio, circ_mv, total_mv, dv_ttm
Evaluates via single SQL query on daily_fundamental for the target date.
Also handles stock_basic filters (exclude_st, market, listing_age).
"""
from datetime import date
import pandas as pd
from sqlalchemy import text
from .base import BaseEvaluator, apply_operator

# Metrics served by daily_fundamental
FUNDAMENTAL_METRICS = {
    "pe_ttm", "pb", "ps_ttm", "dv_ttm", "turnover_rate",
    "volume_ratio", "circ_mv", "total_mv",
}

# Metrics served by stock_basic
STOCK_BASIC_METRICS = {"exclude_st", "market", "listing_age_days"}


class FundamentalEvaluator(BaseEvaluator):
    def evaluate(self, rules, trade_date: date, stock_universe: list[str], stockdb_conn,
                 preloaded_fund_df=None, preloaded_sb_df=None) -> dict:
        results: dict[str, dict[int, bool]] = {ts: {} for ts in stock_universe}

        fund_rules = [r for r in rules if r.metric in FUNDAMENTAL_METRICS and r.data_source == "daily_fundamental"]
        basic_rules = [r for r in rules if r.metric in STOCK_BASIC_METRICS and r.data_source == "stock_basic"]

        if fund_rules:
            if preloaded_fund_df is not None:
                df = preloaded_fund_df[preloaded_fund_df["trade_date"] == pd.Timestamp(trade_date)]
            else:
                df = pd.read_sql(
                    text("""
                        SELECT ts_code, pe_ttm, pb, ps_ttm, dv_ttm,
                               turnover_rate, volume_ratio, circ_mv, total_mv
                        FROM daily_fundamental
                        WHERE trade_date = :d
                    """),
                    stockdb_conn,
                    params={"d": trade_date},
                )
            df_idx = df.set_index("ts_code")

            for r in fund_rules:
                col = r.metric
                if col not in df_idx.columns:
                    continue
                series = df_idx[col]
                for ts in stock_universe:
                    if ts in series.index:
                        val = series[ts]
                        results[ts][r.id] = apply_operator(val, r.operator, r.value or {})
                    else:
                        results[ts][r.id] = False

        if basic_rules:
            if preloaded_sb_df is not None:
                sb_df = preloaded_sb_df.set_index("ts_code") if "ts_code" in preloaded_sb_df.columns else preloaded_sb_df
            else:
                sb_df = pd.read_sql(
                    text("SELECT ts_code, name, market, list_date FROM stock_basic WHERE list_status = 'L'"),
                    stockdb_conn,
                )
                sb_df = sb_df.set_index("ts_code")

            for r in basic_rules:
                for ts in stock_universe:
                    if ts not in sb_df.index:
                        results[ts][r.id] = False
                        continue
                    row = sb_df.loc[ts]
                    if r.metric == "exclude_st":
                        # True means NOT an ST stock
                        name = str(row["name"]) if row["name"] else ""
                        results[ts][r.id] = ("ST" not in name.upper() and "*" not in name)
                    elif r.metric == "market":
                        results[ts][r.id] = (str(row["market"]) == str((r.value or {}).get("v", "")))
                    elif r.metric == "listing_age_days":
                        list_date = row["list_date"]
                        if list_date is None:
                            results[ts][r.id] = False
                        else:
                            age = (trade_date - list_date).days
                            results[ts][r.id] = apply_operator(age, r.operator, r.value or {})

        return results
