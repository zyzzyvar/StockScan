"""
Money flow evaluator.
Metrics: net_mf_amount, net_lg_amount, net_elg_amount,
         net_mf_vol_pct, consecutive_net_inflow, cumulative_net_inflow,
         net_lg_elg_amount
"""
from datetime import date, timedelta
import pandas as pd
from sqlalchemy import text
from .base import BaseEvaluator, apply_operator

FLOW_METRICS = {
    "net_mf_amount", "net_lg_amount", "net_elg_amount",
    "net_mf_vol_pct", "consecutive_net_inflow",
    "cumulative_net_inflow", "net_lg_elg_amount",
}


class FlowEvaluator(BaseEvaluator):
    def evaluate(self, rules, trade_date: date, stock_universe: list[str], stockdb_conn,
                 preloaded_df=None) -> dict:
        results: dict[str, dict[int, bool]] = {ts: {} for ts in stock_universe}
        flow_rules = [r for r in rules if r.metric in FLOW_METRICS and r.data_source == "money_flow"]
        if not flow_rules:
            return results

        if preloaded_df is not None:
            max_lookback = max((r.lookback_days or 0) for r in flow_rules)
            max_lookback = max(max_lookback, 1)
            start_ts = pd.Timestamp(trade_date - timedelta(days=max_lookback + 10))
            today_ts = pd.Timestamp(trade_date)
            df = preloaded_df[
                (preloaded_df["trade_date"] >= start_ts) &
                (preloaded_df["trade_date"] <= today_ts) &
                preloaded_df["ts_code"].isin(stock_universe)
            ].copy()
        else:
            max_lookback = max((r.lookback_days or 0) for r in flow_rules)
            max_lookback = max(max_lookback, 1)
            start_date = trade_date - timedelta(days=max_lookback + 10)

            df = pd.read_sql(
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
                params={"s": start_date, "e": trade_date, "codes": stock_universe},
            )

        if df.empty:
            for r in flow_rules:
                for ts in stock_universe:
                    results[ts][r.id] = False
            return results

        df["trade_date"] = pd.to_datetime(df["trade_date"])
        df["net_lg"] = df["buy_lg_amount"].fillna(0) - df["sell_lg_amount"].fillna(0)
        df["net_elg"] = df["buy_elg_amount"].fillna(0) - df["sell_elg_amount"].fillna(0)
        df["net_lg_elg"] = df["net_lg"] + df["net_elg"]
        total_vol = (
            df["buy_sm_vol"].fillna(0) + df["sell_sm_vol"].fillna(0) +
            df["buy_md_vol"].fillna(0) + df["sell_md_vol"].fillna(0) +
            df["buy_lg_vol"].fillna(0) + df["sell_lg_vol"].fillna(0) +
            df["buy_elg_vol"].fillna(0) + df["sell_elg_vol"].fillna(0)
        )
        df["net_mf_vol_pct"] = df["net_mf_vol"].fillna(0) / total_vol.replace(0, float("nan")) * 100

        for r in flow_rules:
            v = r.value or {}
            today = pd.Timestamp(trade_date)

            for ts, grp in df.groupby("ts_code", sort=False):
                if ts not in results:
                    continue
                grp = grp.sort_values("trade_date")
                today_row = grp[grp["trade_date"] == today]

                if today_row.empty and r.metric not in {"consecutive_net_inflow", "cumulative_net_inflow"}:
                    results[ts][r.id] = False
                    continue

                if r.metric == "net_mf_amount":
                    val = float(today_row.iloc[0]["net_mf_amount"]) if not today_row.empty else None
                    results[ts][r.id] = apply_operator(val, r.operator, v)

                elif r.metric == "net_lg_amount":
                    val = float(today_row.iloc[0]["net_lg"]) if not today_row.empty else None
                    results[ts][r.id] = apply_operator(val, r.operator, v)

                elif r.metric == "net_elg_amount":
                    val = float(today_row.iloc[0]["net_elg"]) if not today_row.empty else None
                    results[ts][r.id] = apply_operator(val, r.operator, v)

                elif r.metric == "net_lg_elg_amount":
                    val = float(today_row.iloc[0]["net_lg_elg"]) if not today_row.empty else None
                    results[ts][r.id] = apply_operator(val, r.operator, v)

                elif r.metric == "net_mf_vol_pct":
                    val = float(today_row.iloc[0]["net_mf_vol_pct"]) if not today_row.empty else None
                    results[ts][r.id] = apply_operator(val, r.operator, v)

                elif r.metric == "consecutive_net_inflow":
                    min_days = int(v.get("days", 3))
                    recent = grp[grp["trade_date"] <= today].tail(min_days)
                    if len(recent) < min_days:
                        results[ts][r.id] = False
                    else:
                        results[ts][r.id] = all(float(x) > 0 for x in recent["net_mf_amount"].fillna(0))

                elif r.metric == "cumulative_net_inflow":
                    days = int(v.get("days", 5))
                    recent = grp[grp["trade_date"] <= today].tail(days)
                    total = float(recent["net_mf_amount"].fillna(0).sum())
                    results[ts][r.id] = apply_operator(total, r.operator, v)

        for r in flow_rules:
            for ts in stock_universe:
                if r.id not in results[ts]:
                    results[ts][r.id] = False

        return results
