from pydantic import BaseModel
from typing import Optional


class PortfolioBacktestRequest(BaseModel):
    scheme_id: int
    start_date: str            # YYYY-MM-DD
    end_date: str              # YYYY-MM-DD
    hold_days: int = 1         # 1, 2, or 3
    enabled_rule_ids: Optional[list[int]] = None  # None = use all enabled rules


class StockTradeResult(BaseModel):
    ts_code: str
    stock_name: Optional[str]
    buy_price: Optional[float]
    sell_price: Optional[float]
    raw_return: Optional[float]   # %
    net_return: Optional[float]   # % after costs


class BatchResult(BaseModel):
    buy_date: str
    sell_date: Optional[str]
    stock_count: int
    valid_count: int          # stocks with sell price
    avg_net_return: Optional[float]  # %
    stocks: list[StockTradeResult]


class PortfolioSummary(BaseModel):
    total_batches: int
    covered_days: int         # days with existing screening results
    total_trading_days: int   # total trading days in the range
    coverage_pct: float       # covered_days / total_trading_days * 100
    cumulative_return: float  # %
    annualized_return: float  # % (simple annualization)
    win_rate: float           # % of batches with avg_return > 0
    avg_batch_return: float   # %
    max_drawdown: float       # % (negative value)
    total_trades: int
    avg_stocks_per_batch: float
    transaction_cost_pct: float  # round-trip cost applied


class PortfolioBacktestResult(BaseModel):
    scheme_id: int
    scheme_name: str
    start_date: str
    end_date: str
    hold_days: int
    summary: PortfolioSummary
    equity_curve: list[dict]   # [{"date": str, "value": float}] — 0-based cumulative %
    batches: list[BatchResult]
