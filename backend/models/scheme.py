from datetime import datetime
from sqlalchemy import String, Text, Boolean, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base


class Scheme(Base):
    __tablename__ = "scheme"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # "all" = all rules must match; "partial" = min_match of N rules
    match_mode: Mapped[str] = mapped_column(String(20), default="all", nullable=False)
    min_match: Mapped[int | None] = mapped_column(Integer)
    schedule_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    schedule_time: Mapped[str | None] = mapped_column(String(5))  # "HH:MM"

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False
    )

    rules: Mapped[list["Rule"]] = relationship(
        "Rule",
        back_populates="scheme",
        cascade="all, delete-orphan",
        order_by="Rule.sort_order",
    )
    results: Mapped[list["ScreeningResult"]] = relationship(
        "ScreeningResult",
        back_populates="scheme",
        cascade="all, delete-orphan",
    )
