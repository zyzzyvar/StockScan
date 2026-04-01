"""
Technical indicator evaluator using pandas_ta.
Metrics: macd_cross, macd_hist_positive, kdj_cross, kdj_j,
         rsi, cci, willr, atr_expand, obv_trend,
         close_vs_boll (BOLL mid/upper/lower)
"""
from datetime import date, timedelta
import pandas as pd
import numpy as np
from sqlalchemy import text
from .base import BaseEvaluator, apply_operator

try:
    import pandas_ta as ta
    HAS_TA = True
except ImportError:
    HAS_TA = False

TECHNICAL_METRICS = {
    "macd_cross", "macd_hist_positive", "kdj_cross", "kdj_j",
    "rsi", "cci", "willr", "atr_expand", "obv_trend", "close_vs_boll",
}


class TechnicalEvaluator(BaseEvaluator):
    def evaluate(self, rules, trade_date: date, stock_universe: list[str], stockdb_conn,
                 preloaded_df=None) -> dict:
        results: dict[str, dict[int, bool]] = {ts: {} for ts in stock_universe}
        tech_rules = [r for r in rules if r.metric in TECHNICAL_METRICS]
        if not tech_rules or not HAS_TA:
            for r in tech_rules:
                for ts in stock_universe:
                    results[ts][r.id] = False
            return results

        if preloaded_df is not None:
            start_ts = pd.Timestamp(trade_date - timedelta(days=110))
            today_ts = pd.Timestamp(trade_date)
            df = preloaded_df[
                (preloaded_df["trade_date"] >= start_ts) &
                (preloaded_df["trade_date"] <= today_ts) &
                preloaded_df["ts_code"].isin(stock_universe)
            ].copy()
        else:
            # Fetch 90 days of OHLCV data
            start_date = trade_date - timedelta(days=110)
            df = pd.read_sql(
                text("""
                    SELECT ts_code, trade_date, open, high, low, close, vol
                    FROM daily_price
                    WHERE trade_date BETWEEN :s AND :e
                      AND ts_code = ANY(:codes)
                    ORDER BY ts_code, trade_date
                """),
                stockdb_conn,
                params={"s": start_date, "e": trade_date, "codes": stock_universe},
            )
        if df.empty:
            for r in tech_rules:
                for ts in stock_universe:
                    results[ts][r.id] = False
            return results

        df["trade_date"] = pd.to_datetime(df["trade_date"])
        today_ts = pd.Timestamp(trade_date)

        for ts, grp in df.groupby("ts_code", sort=False):
            if ts not in results:
                continue
            grp = grp.sort_values("trade_date").reset_index(drop=True)
            if len(grp) < 15:
                for r in tech_rules:
                    results[ts][r.id] = False
                continue

            # Compute indicators once per stock
            indicators = self._compute_indicators(grp, tech_rules)

            for r in tech_rules:
                results[ts][r.id] = self._eval_rule(r, grp, indicators, today_ts)

        for r in tech_rules:
            for ts in stock_universe:
                if r.id not in results[ts]:
                    results[ts][r.id] = False

        return results

    def _compute_indicators(self, grp: pd.DataFrame, rules: list) -> dict:
        metrics_needed = {r.metric for r in rules}
        ind = {}
        c = grp["close"].astype(float)
        h = grp["high"].astype(float)
        l = grp["low"].astype(float)
        o = grp["open"].astype(float)
        v = grp["vol"].astype(float)

        if "macd_cross" in metrics_needed or "macd_hist_positive" in metrics_needed:
            macd_df = ta.macd(c)
            if macd_df is not None and not macd_df.empty:
                ind["macd_dif"] = macd_df.iloc[:, 0].values  # MACD line
                ind["macd_dea"] = macd_df.iloc[:, 1].values  # Signal line
                ind["macd_hist"] = macd_df.iloc[:, 2].values  # Histogram

        if "kdj_cross" in metrics_needed or "kdj_j" in metrics_needed:
            stoch = ta.stoch(h, l, c)
            if stoch is not None and not stoch.empty:
                ind["kdj_k"] = stoch.iloc[:, 0].values
                ind["kdj_d"] = stoch.iloc[:, 1].values
                ind["kdj_j"] = 3 * stoch.iloc[:, 0].values - 2 * stoch.iloc[:, 1].values

        if "rsi" in metrics_needed:
            ind["rsi_6"] = ta.rsi(c, length=6).values if ta.rsi(c, length=6) is not None else None
            ind["rsi_14"] = ta.rsi(c, length=14).values if ta.rsi(c, length=14) is not None else None

        if "cci" in metrics_needed:
            cci = ta.cci(h, l, c)
            ind["cci"] = cci.values if cci is not None else None

        if "willr" in metrics_needed:
            wr = ta.willr(h, l, c)
            ind["willr"] = wr.values if wr is not None else None

        if "atr_expand" in metrics_needed:
            atr = ta.atr(h, l, c)
            ind["atr"] = atr.values if atr is not None else None

        if "obv_trend" in metrics_needed:
            obv = ta.obv(c, v)
            ind["obv"] = obv.values if obv is not None else None

        if "close_vs_boll" in metrics_needed:
            bbands = ta.bbands(c)
            if bbands is not None and not bbands.empty:
                ind["boll_lower"] = bbands.iloc[:, 0].values
                ind["boll_mid"] = bbands.iloc[:, 1].values
                ind["boll_upper"] = bbands.iloc[:, 2].values

        return ind

    def _eval_rule(self, rule, grp: pd.DataFrame, ind: dict, today_ts) -> bool:
        v = rule.value or {}
        op = rule.operator
        metric = rule.metric
        n = len(grp)

        # Find today's index
        today_mask = grp["trade_date"] == today_ts
        if not today_mask.any():
            return False
        idx = grp.index[today_mask][0]

        if metric == "macd_cross":
            dif = ind.get("macd_dif")
            dea = ind.get("macd_dea")
            if dif is None or dea is None:
                return False
            signal = v.get("signal", "golden")
            days = int(v.get("days", 3))
            for i in range(days):
                pos = idx - i
                if pos < 1:
                    break
                if signal == "golden":
                    if dif[pos] > dea[pos] and dif[pos - 1] <= dea[pos - 1]:
                        return True
                else:
                    if dif[pos] < dea[pos] and dif[pos - 1] >= dea[pos - 1]:
                        return True
            return False

        elif metric == "macd_hist_positive":
            hist = ind.get("macd_hist")
            if hist is None or idx < 1:
                return False
            return float(hist[idx]) > 0 and float(hist[idx - 1]) <= 0

        elif metric == "kdj_cross":
            k = ind.get("kdj_k")
            d = ind.get("kdj_d")
            if k is None or d is None:
                return False
            signal = v.get("signal", "golden")
            days = int(v.get("days", 3))
            for i in range(days):
                pos = idx - i
                if pos < 1:
                    break
                if signal == "golden":
                    if k[pos] > d[pos] and k[pos - 1] <= d[pos - 1]:
                        return True
                else:
                    if k[pos] < d[pos] and k[pos - 1] >= d[pos - 1]:
                        return True
            return False

        elif metric == "kdj_j":
            j = ind.get("kdj_j")
            if j is None:
                return False
            val = j[idx]
            if np.isnan(val):
                return False
            return apply_operator(val, op, v)

        elif metric == "rsi":
            period = int(v.get("period", 14))
            key = f"rsi_{period}" if period in (6, 14) else "rsi_14"
            rsi_arr = ind.get(key)
            if rsi_arr is None:
                return False
            val = rsi_arr[idx]
            if np.isnan(val):
                return False
            if op == "between":
                return float(v.get("min", 0)) <= val <= float(v.get("max", 100))
            return apply_operator(val, op, v)

        elif metric == "cci":
            arr = ind.get("cci")
            if arr is None:
                return False
            val = arr[idx]
            if np.isnan(val):
                return False
            if op == "between":
                return float(v.get("min", -200)) <= val <= float(v.get("max", -100))
            return apply_operator(val, op, v)

        elif metric == "willr":
            arr = ind.get("willr")
            if arr is None:
                return False
            val = arr[idx]
            if np.isnan(val):
                return False
            return apply_operator(val, op, v)

        elif metric == "atr_expand":
            arr = ind.get("atr")
            if arr is None or idx < 14:
                return False
            ratio = float(v.get("ratio", 1.2))
            period = int(v.get("period", 14))
            start = max(0, idx - period)
            avg_atr = np.nanmean(arr[start:idx])
            return float(arr[idx]) > avg_atr * ratio if avg_atr > 0 else False

        elif metric == "obv_trend":
            arr = ind.get("obv")
            if arr is None or idx < 5:
                return False
            period = int(v.get("period", 5))
            obv_ma_now = np.nanmean(arr[max(0, idx - period):idx + 1])
            obv_ma_prev = np.nanmean(arr[max(0, idx - period - 5):idx - period + 1])
            return obv_ma_now > obv_ma_prev

        elif metric == "close_vs_boll":
            band = v.get("band", "mid")
            close = float(grp.loc[idx, "close"])
            key = f"boll_{band}"
            arr = ind.get(key)
            if arr is None or np.isnan(arr[idx]):
                return False
            if op == "gt":
                return close > arr[idx]
            elif op == "lt":
                return close < arr[idx]
            return False

        return False
