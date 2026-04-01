from datetime import datetime, date
from sqlalchemy import String, Integer, Float, Date, DateTime, ForeignKey, Numeric, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base


class ScreeningResult(Base):
    __tablename__ = "screening_result"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scheme_id: Mapped[int] = mapped_column(Integer, ForeignKey("scheme.id", ondelete="CASCADE"), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_stocks: Mapped[int] = mapped_column(Integer, default=0)
    full_match_count: Mapped[int] = mapped_column(Integer, default=0)
    partial_match_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)

    scheme: Mapped["Scheme"] = relationship("Scheme", back_populates="results")
    details: Mapped[list["ScreeningResultDetail"]] = relationship(
        "ScreeningResultDetail",
        back_populates="result",
        cascade="all, delete-orphan",
    )


class ScreeningResultDetail(Base):
    __tablename__ = "screening_result_detail"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    result_id: Mapped[int] = mapped_column(Integer, ForeignKey("screening_result.id", ondelete="CASCADE"), nullable=False)
    ts_code: Mapped[str] = mapped_column(String(12), nullable=False)
    stock_name: Mapped[str | None] = mapped_column(String(20))
    matched_rules: Mapped[int] = mapped_column(Integer, default=0)
    total_rules: Mapped[int] = mapped_column(Integer, default=0)
    is_full_match: Mapped[bool] = mapped_column(Boolean, default=False)
    rule_results: Mapped[dict | None] = mapped_column(JSONB)  # {rule_id: bool, ...}

    # Snapshot fields for display
    close: Mapped[float | None] = mapped_column(Numeric(12, 4))
    pct_chg: Mapped[float | None] = mapped_column(Numeric(10, 4))
    vol: Mapped[float | None] = mapped_column(Numeric(20, 2))
    turnover_rate: Mapped[float | None] = mapped_column(Numeric(12, 4))
    circ_mv: Mapped[float | None] = mapped_column(Numeric(20, 4))
    volume_ratio: Mapped[float | None] = mapped_column(Numeric(12, 4))
    pe_ttm: Mapped[float | None] = mapped_column(Numeric(12, 4))
    pb: Mapped[float | None] = mapped_column(Numeric(12, 4))

    result: Mapped["ScreeningResult"] = relationship("ScreeningResult", back_populates="details")
