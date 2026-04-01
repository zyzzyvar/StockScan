from sqlalchemy import String, Integer, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base


class Rule(Base):
    __tablename__ = "rule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scheme_id: Mapped[int] = mapped_column(Integer, ForeignKey("scheme.id", ondelete="CASCADE"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    template_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("rule_template.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # trend/volume/valuation/flow/technical/filter/historical
    data_source: Mapped[str] = mapped_column(String(50), nullable=False)  # daily_price/daily_fundamental/money_flow/computed
    metric: Mapped[str] = mapped_column(String(100), nullable=False)
    operator: Mapped[str] = mapped_column(String(20), nullable=False)  # gt/lt/gte/lte/between/eq/custom
    value: Mapped[dict | None] = mapped_column(JSONB)  # {"v": 3.0} or {"min": 3, "max": 5}
    lookback_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    params: Mapped[dict | None] = mapped_column(JSONB)  # extra params for complex rules
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    scheme: Mapped["Scheme"] = relationship("Scheme", back_populates="rules")
    template: Mapped["RuleTemplate | None"] = relationship("RuleTemplate")
