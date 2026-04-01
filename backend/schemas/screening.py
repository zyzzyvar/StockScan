from datetime import date, datetime
from pydantic import BaseModel, ConfigDict


class ScreeningRunRequest(BaseModel):
    scheme_id: int
    trade_date: date


class RuleResultOut(BaseModel):
    rule_id: int
    rule_name: str
    matched: bool


class StockResultOut(BaseModel):
    ts_code: str
    stock_name: str | None
    matched_rules: int
    total_rules: int
    is_full_match: bool
    rule_results: dict | None
    close: float | None
    pct_chg: float | None
    vol: float | None
    turnover_rate: float | None
    circ_mv: float | None
    volume_ratio: float | None = None
    pe_ttm: float | None = None
    pb: float | None = None


class ScreeningResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    scheme_id: int
    trade_date: date
    total_stocks: int
    full_match_count: int
    partial_match_count: int
    duration_seconds: float | None
    created_at: datetime


class ScreeningResultDetailOut(ScreeningResultOut):
    details: list[StockResultOut] = []
