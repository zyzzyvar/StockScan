from pydantic import BaseModel, ConfigDict


class TemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    category: str
    description: str | None
    data_source: str
    metric: str
    operator: str
    default_value: dict | None
    lookback_days: int
    params: dict | None
    sort_order: int
