from datetime import datetime
from pydantic import BaseModel, ConfigDict


class RuleBase(BaseModel):
    name: str
    category: str
    data_source: str
    metric: str
    operator: str
    value: dict | None = None
    lookback_days: int = 0
    params: dict | None = None
    enabled: bool = True
    sort_order: int = 0
    template_id: int | None = None


class RuleCreate(RuleBase):
    pass


class RuleUpdate(RuleBase):
    pass


class RuleOut(RuleBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    scheme_id: int


class SchemeBase(BaseModel):
    name: str
    description: str | None = None
    match_mode: str = "all"
    min_match: int | None = None
    schedule_enabled: bool = False
    schedule_time: str | None = None  # "HH:MM"


class SchemeCreate(SchemeBase):
    pass


class SchemeUpdate(SchemeBase):
    pass


class SchemeOut(SchemeBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_builtin: bool
    created_at: datetime
    updated_at: datetime
    rules: list[RuleOut] = []


class SchemeListOut(SchemeBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_builtin: bool
    created_at: datetime
    updated_at: datetime
    rule_count: int = 0
    schedule_enabled: bool = False
    schedule_time: str | None = None


class ReorderRequest(BaseModel):
    rule_ids: list[int]
