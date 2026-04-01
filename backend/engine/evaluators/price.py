"""
Price / MA evaluator — fully vectorized batch implementation.
Processes all stocks simultaneously using numpy arrays.
"""
from datetime import date, timedelta
import warnings
import pandas as pd
import numpy as np
from sqlalchemy import text
from .base import BaseEvaluator, apply_operator

PRICE_METRICS = {
    "pct_chg", "close_vs_vwap", "close_vs_ma", "ma_alignment_bull",
    "ma_alignment_diverge", "ma_cross", "new_high", "not_limit",
    "vol_step_up", "vol_vs_ma", "vol_shrink", "n_day_return",
    "consecutive_up_days", "max_drawdown",
    # New: scoring-model metrics
    "avg_amount_20d", "price_vs_nd_low", "candlestick_hammer", "three_soldiers",
}

_OHLC_METRICS = {"candlestick_hammer", "three_soldiers"}


class PriceEvaluator(BaseEvaluator):
    def evaluate(self, rules, trade_date: date, stock_universe: list[str], stockdb_conn,
                 preloaded_df=None) -> dict:
        results: dict[str, dict[int, bool]] = {ts: {} for ts in stock_universe}
        price_rules = [r for r in rules if r.metric in PRICE_METRICS and r.data_source == "daily_price"]
        if not price_rules:
            return results

        if preloaded_df is not None:
            today_ts = pd.Timestamp(trade_date)
            df = preloaded_df[
                (preloaded_df["trade_date"] <= today_ts) &
                preloaded_df["ts_code"].isin(stock_universe)
            ].copy()
        else:
            max_lookback = max((r.lookback_days or 0) for r in price_rules)
            max_lookback = max(max_lookback, 65)
            # Use +70 calendar days buffer (instead of +25) to ensure ≥63 trading days
            # even across long holiday periods (e.g. Chinese New Year spans ~7 days off)
            start_date = trade_date - timedelta(days=max_lookback + 70)

            needs_ohlc = any(r.metric in _OHLC_METRICS for r in price_rules)
            extra_cols = ", open, high, low" if needs_ohlc else ""
            df = pd.read_sql(
                text(f"""
                    SELECT ts_code, trade_date, close, vol, amount, pct_chg{extra_cols}
                    FROM daily_price
                    WHERE trade_date BETWEEN :s AND :e
                      AND ts_code = ANY(:codes)
                    ORDER BY ts_code, trade_date
                """),
                stockdb_conn,
                params={"s": start_date, "e": trade_date, "codes": stock_universe},
            )
        if df.empty:
            for r in price_rules:
                for ts in stock_universe:
                    results[ts][r.id] = False
            return results

        df["trade_date"] = pd.to_datetime(df["trade_date"])
        today_ts = pd.Timestamp(trade_date)

        # Build aligned matrices: pivot to (trade_date x ts_code) for vectorized ops
        # Filter to today's data first (for today-only metrics)
        today_df = df[df["trade_date"] == today_ts].set_index("ts_code")

        # For lookback metrics, build a padded 3D array
        # Shape: (n_stocks, max_dates) — stocks with fewer dates are NaN-padded on the left
        # We use a fixed window of the last N dates per stock
        MAX_WINDOW = 100  # enough for ma60 + slope check (need ≥63 trading days)

        warnings.filterwarnings("ignore", message="Mean of empty slice")
        # Pre-pivot close/vol arrays aligned to a common date index
        close_pivot = (
            df[["ts_code", "trade_date", "close"]]
            .pivot_table(index="trade_date", columns="ts_code", values="close")
            .sort_index()
        )
        vol_pivot = (
            df[["ts_code", "trade_date", "vol"]]
            .pivot_table(index="trade_date", columns="ts_code", values="vol")
            .sort_index()
        )
        # Only keep columns (stocks) that have data today
        valid_stocks = [s for s in stock_universe if s in today_df.index and s in close_pivot.columns]

        # Trim to MAX_WINDOW most recent dates
        close_pivot = close_pivot[valid_stocks].tail(MAX_WINDOW)
        vol_pivot = vol_pivot[valid_stocks].tail(MAX_WINDOW)

        C = close_pivot.values.astype(float)  # (dates, stocks)
        V = vol_pivot.values.astype(float)
        n_dates = C.shape[0]

        # Amount matrix for avg_amount_20d
        if "amount" in df.columns:
            amt_pivot = (
                df[["ts_code", "trade_date", "amount"]]
                .pivot_table(index="trade_date", columns="ts_code", values="amount")
                .sort_index()
            )[valid_stocks].tail(MAX_WINDOW)
            A = amt_pivot.values.astype(float)
        else:
            A = None

        # OHLC matrices for candlestick pattern metrics
        needs_ohlc = any(r.metric in _OHLC_METRICS for r in price_rules)
        if needs_ohlc and "open" in df.columns:
            open_pivot = (
                df[["ts_code", "trade_date", "open"]]
                .pivot_table(index="trade_date", columns="ts_code", values="open")
                .sort_index()
            )[valid_stocks].tail(MAX_WINDOW)
            high_pivot = (
                df[["ts_code", "trade_date", "high"]]
                .pivot_table(index="trade_date", columns="ts_code", values="high")
                .sort_index()
            )[valid_stocks].tail(MAX_WINDOW)
            low_pivot = (
                df[["ts_code", "trade_date", "low"]]
                .pivot_table(index="trade_date", columns="ts_code", values="low")
                .sort_index()
            )[valid_stocks].tail(MAX_WINDOW)
            O = open_pivot.values.astype(float)
            H = high_pivot.values.astype(float)
            L = low_pivot.values.astype(float)
        else:
            O = H = L = None

        # Precompute commonly needed MAs across ALL stocks at once (vectorized)
        def ma(arr, n):
            if n_dates < n:
                return np.full(arr.shape[1], np.nan)
            return np.nanmean(arr[-n:], axis=0)

        ma5  = ma(C, 5)
        ma10 = ma(C, 10)
        ma20 = ma(C, 20)
        ma60 = ma(C, 60)

        # 3-days-ago MAs for diverge check
        def ma_slice(arr, start, end):
            """mean of arr[start:end] per stock, negative indices"""
            slc = arr[start:end] if end is None else arr[start:end]
            if slc.shape[0] == 0:
                return np.full(arr.shape[1], np.nan)
            return np.nanmean(slc, axis=0)

        ma5_old  = ma_slice(C, -8, -3)   if n_dates >= 8  else np.full(len(valid_stocks), np.nan)
        ma10_old = ma_slice(C, -13, -3)  if n_dates >= 13 else np.full(len(valid_stocks), np.nan)
        ma20_old = ma_slice(C, -23, -3)  if n_dates >= 23 else np.full(len(valid_stocks), np.nan)
        ma60_old = ma_slice(C, -63, -3)  if n_dates >= 63 else np.full(len(valid_stocks), np.nan)
        ma_vol20 = ma_slice(V, -21, -1)  if n_dates >= 21 else np.full(len(valid_stocks), np.nan)

        stock_idx = {ts: i for i, ts in enumerate(valid_stocks)}

        for rule in price_rules:
            rid = rule.id
            v = rule.value or {}
            op = rule.operator
            metric = rule.metric

            # Compute boolean array for all valid_stocks at once
            matched = self._eval_batch(
                metric, op, v,
                C, V, A, O, H, L, today_df, valid_stocks, stock_idx,
                ma5, ma10, ma20, ma60,
                ma5_old, ma10_old, ma20_old, ma60_old, ma_vol20,
                n_dates,
            )

            for i, ts in enumerate(valid_stocks):
                results[ts][rid] = bool(matched[i])

            # Stocks not in valid_stocks get False
            for ts in stock_universe:
                if ts not in stock_idx:
                    results[ts][rid] = False

        return results

    def _eval_batch(
        self, metric, op, v,
        C, V, A, O, H, L, today_df, valid_stocks, stock_idx,
        ma5, ma10, ma20, ma60,
        ma5_old, ma10_old, ma20_old, ma60_old, ma_vol20,
        n_dates,
    ) -> np.ndarray:
        """Return boolean array of shape (n_stocks,)"""
        n = len(valid_stocks)
        nan_mask = ~np.isnan(C[-1])  # stocks that have data today

        if metric == "pct_chg":
            pct = today_df.reindex(valid_stocks)["pct_chg"].values.astype(float)
            return self._apply_op_arr(pct, op, v) & nan_mask

        elif metric == "close_vs_vwap":
            amt = today_df.reindex(valid_stocks)["amount"].fillna(0).values.astype(float)
            vol = today_df.reindex(valid_stocks)["vol"].fillna(0).values.astype(float)
            close = today_df.reindex(valid_stocks)["close"].fillna(0).values.astype(float)
            vwap = np.where(vol > 0, (amt * 1000) / (vol * 100), np.nan)
            return (close > vwap) & nan_mask

        elif metric == "close_vs_ma":
            period = int(v.get("period", 20))
            if n_dates < period:
                return np.zeros(n, dtype=bool)
            ma_p = np.nanmean(C[-period:], axis=0)
            return (C[-1] > ma_p) & ~np.isnan(ma_p) & nan_mask

        elif metric == "ma_alignment_bull":
            return (ma5 > ma10) & (ma10 > ma20) & (ma20 > ma60) & nan_mask & ~np.isnan(ma60)

        elif metric == "ma_alignment_diverge":
            order_ok = (ma5 > ma10) & (ma10 > ma20) & (ma20 > ma60) & ~np.isnan(ma60)
            slope_ok = (
                (ma5 > ma5_old) & (ma10 > ma10_old) &
                (ma20 > ma20_old) & (ma60 > ma60_old) &
                ~np.isnan(ma60_old)
            )
            return order_ok & slope_ok & nan_mask

        elif metric == "ma_cross":
            fast = int(v.get("fast", 5))
            slow = int(v.get("slow", 10))
            days = int(v.get("days", 3))
            if n_dates < slow + days:
                return np.zeros(n, dtype=bool)
            found = np.zeros(n, dtype=bool)
            for i in range(days):
                end = n_dates - i
                if end < slow + 1:
                    break
                mf_now = np.nanmean(C[end - fast:end], axis=0)
                ms_now = np.nanmean(C[end - slow:end], axis=0)
                mf_prev = np.nanmean(C[end - fast - 1:end - 1], axis=0)
                ms_prev = np.nanmean(C[end - slow - 1:end - 1], axis=0)
                found |= (mf_now > ms_now) & (mf_prev <= ms_prev)
            return found & nan_mask

        elif metric == "new_high":
            period = int(v.get("period", 20))
            if n_dates < period:
                return np.zeros(n, dtype=bool)
            high_p = np.nanmax(C[-period:], axis=0)
            return (C[-1] >= high_p) & nan_mask

        elif metric == "not_limit":
            pct = today_df.reindex(valid_stocks)["pct_chg"].fillna(0).values.astype(float)
            return (np.abs(pct) < 9.8) & nan_mask

        elif metric == "vol_step_up":
            window = int(v.get("window", 8))
            min_consec = int(v.get("min_consecutive", 3))
            if n_dates < window:
                return np.zeros(n, dtype=bool)
            w = V[-window:]  # (window, stocks)
            diffs = np.diff(w, axis=0)  # (window-1, stocks)
            up = (diffs > 0).astype(int)
            # Old code starts cur=1 and counts elements (not transitions).
            # So "3 consecutive days" = 2 consecutive True transitions in up[].
            need_transitions = min_consec - 1
            found = np.zeros(n, dtype=bool)
            for j in range(len(up) - need_transitions + 1):
                if j + need_transitions <= len(up):
                    found |= np.all(up[j:j + need_transitions], axis=0).astype(bool)
            # Also check step-up pattern
            seg = window // 3
            if seg >= 1:
                s1 = np.nanmean(w[:seg], axis=0)
                s2 = np.nanmean(w[seg:2 * seg], axis=0)
                s3 = np.nanmean(w[2 * seg:], axis=0)
                found |= (s3 > s2) & (s2 > s1)
            return found & nan_mask

        elif metric == "vol_vs_ma":
            period = int(v.get("period", 20))
            ratio = float(v.get("ratio", 1.2))
            if n_dates <= period:
                return np.zeros(n, dtype=bool)
            ma_v = np.nanmean(V[-period - 1:-1], axis=0)
            return (V[-1] > ma_v * ratio) & ~np.isnan(ma_v) & nan_mask

        elif metric == "vol_shrink":
            days = int(v.get("days", 3))
            if n_dates < days:
                return np.zeros(n, dtype=bool)
            w = V[-days:]
            diffs = np.diff(w, axis=0)
            return np.all(diffs < 0, axis=0) & nan_mask

        elif metric == "n_day_return":
            period = int(v.get("period", 5))
            if n_dates < period + 1:
                return np.zeros(n, dtype=bool)
            ret = (C[-1] / C[-(period + 1)] - 1) * 100
            return self._apply_op_arr(ret, op, v) & nan_mask

        elif metric == "consecutive_up_days":
            # Count consecutive up days per stock
            diffs = np.diff(C, axis=0)  # (dates-1, stocks)
            count = np.zeros(n, dtype=int)
            for i in range(n_dates - 2, -1, -1):
                going = diffs[i] > 0
                count += going.astype(int)
                # Break streaks — stocks where going is False reset to 0
                # But we want the run ending at today, so we stop when going is False
                # Use cumsum from the end
                break  # This naive approach won't work; use proper method below
            # Proper: vectorized consecutive count from end
            count = np.zeros(n, dtype=int)
            reversed_diffs = diffs[::-1]  # most recent first
            streak = np.ones(n, dtype=bool)
            for i in range(len(reversed_diffs)):
                up_today = reversed_diffs[i] > 0
                streak &= up_today
                count += streak.astype(int)
            return self._apply_op_arr(count.astype(float), op, v) & nan_mask

        elif metric == "max_drawdown":
            period = int(v.get("period", 20))
            if n_dates < period:
                return np.zeros(n, dtype=bool)
            w = C[-period:]  # (period, stocks)
            peak = np.maximum.accumulate(w, axis=0)
            dd = np.abs(np.nanmin((w - peak) / peak * 100, axis=0))
            return self._apply_op_arr(dd, op, v) & nan_mask

        elif metric == "avg_amount_20d":
            # 20-day average daily amount (千元 units). Threshold in rule.value["v"].
            if A is None or n_dates < 1:
                return np.zeros(n, dtype=bool)
            period = int(v.get("period", 20))
            use = min(period, n_dates)
            avg_amt = np.nanmean(A[-use:], axis=0)
            return self._apply_op_arr(avg_amt, op, v) & ~np.isnan(avg_amt) & nan_mask

        elif metric == "price_vs_nd_low":
            # (close - N-day low) / N-day low * 100; operator applied against threshold.
            period = int(v.get("period", 60))
            if n_dates < period:
                return np.zeros(n, dtype=bool)
            nd_low = np.nanmin(C[-period:], axis=0)
            pct_above = (C[-1] / nd_low - 1) * 100
            return self._apply_op_arr(pct_above, op, v) & ~np.isnan(nd_low) & (nd_low > 0) & nan_mask

        elif metric == "candlestick_hammer":
            # Pin-bar / hammer: lower shadow >= 2× body, upper shadow <= 30% body.
            if O is None or H is None or L is None:
                return np.zeros(n, dtype=bool)
            o, h, l, c = O[-1], H[-1], L[-1], C[-1]
            body = np.abs(c - o)
            body = np.where(body < 1e-6, 1e-6, body)
            lower_shadow = np.minimum(c, o) - l
            upper_shadow = h - np.maximum(c, o)
            return (lower_shadow >= 2 * body) & (upper_shadow <= 0.3 * body) & nan_mask

        elif metric == "three_soldiers":
            # 3 consecutive green candles each with 1%-5% gain vs prior close, increasing volume.
            if O is None or n_dates < 4:
                return np.zeros(n, dtype=bool)
            all_green = np.ones(n, dtype=bool)
            vol_up = np.ones(n, dtype=bool)
            for i in range(3):
                idx = -(3 - i)       # -3, -2, -1
                prev_idx = idx - 1   # -4, -3, -2
                pct = (C[idx] - C[prev_idx]) / np.where(C[prev_idx] > 0, C[prev_idx], np.nan) * 100
                is_green = (C[idx] > O[idx])
                gain_ok = (pct >= 1) & (pct <= 5)
                all_green &= is_green & gain_ok & ~np.isnan(pct)
            for i in range(2):
                vol_up &= (V[-(2 - i)] > V[-(3 - i)])
            return all_green & vol_up & nan_mask

        return np.zeros(n, dtype=bool)

    @staticmethod
    def _apply_op_arr(arr: np.ndarray, op: str, v: dict) -> np.ndarray:
        """Apply operator to an array, returning boolean array."""
        arr = np.asarray(arr, dtype=float)
        if op == "gt":
            return arr > float(v.get("v", 0))
        elif op == "gte":
            return arr >= float(v.get("v", 0))
        elif op == "lt":
            return arr < float(v.get("v", 0))
        elif op == "lte":
            return arr <= float(v.get("v", 0))
        elif op == "eq":
            return arr == float(v.get("v", 0))
        elif op == "between":
            return (arr >= float(v["min"])) & (arr <= float(v["max"]))
        return np.zeros(len(arr), dtype=bool)
