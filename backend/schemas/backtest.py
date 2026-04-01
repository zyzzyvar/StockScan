from pydantic import BaseModel


class BacktestRequest(BaseModel):
    ts_code: str
    start_date: str
    end_date: str
    scheme_ids: list[int]
