from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field


class ScreeningRunRequest(BaseModel):
    scheme_id: int
    trade_date: date


class ScreenshotRecordCreateRequest(BaseModel):
    task_name: str = Field(..., description="选股方案名称")
    ts_code: str = Field(..., description="股票代码（如600000.SH）")
    trade_date: date = Field(..., description="选股交易日期")
    screenshot_filename: str = Field(..., description="截图文件路径或名称")
    pdf_path: str | None = Field(None, description="PDF 文件路径（可选）")


class RuleResultOut(BaseModel):
    rule_id: int
    rule_name: str
    matched: bool


class ScreenshotRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    task_name: str
    ts_code: str
    screenshot_date: date
    screenshot_filename: str
    pdf_path: str | None = None
    created_at: datetime


class StockResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
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
    screenshots: list[ScreenshotRecordOut] = []


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
