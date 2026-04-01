from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from ..database import get_stockdb

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/latest-trade-date")
def latest_trade_date(db: Session = Depends(get_stockdb)):
    row = db.execute(
        text("SELECT MAX(cal_date) FROM trade_calendar WHERE is_open = 1 AND cal_date <= CURRENT_DATE")
    ).scalar()
    return {"trade_date": row}


@router.get("/trade-dates")
def trade_dates(start: date | None = None, end: date | None = None, db: Session = Depends(get_stockdb)):
    if start is None:
        start = date(2020, 1, 1)
    if end is None:
        end = date.today()
    rows = db.execute(
        text("SELECT cal_date FROM trade_calendar WHERE is_open = 1 AND cal_date BETWEEN :s AND :e ORDER BY cal_date DESC LIMIT 500"),
        {"s": start, "e": end},
    ).fetchall()
    return {"dates": [r[0] for r in rows]}


@router.get("/stocks")
def list_stocks(q: str | None = None, limit: int = 50, db: Session = Depends(get_stockdb)):
    if q:
        rows = db.execute(
            text("SELECT ts_code, name, market FROM stock_basic WHERE list_status='L' AND (ts_code ILIKE :q OR name ILIKE :q) LIMIT :limit"),
            {"q": f"%{q}%", "limit": limit},
        ).fetchall()
    else:
        rows = db.execute(
            text("SELECT ts_code, name, market FROM stock_basic WHERE list_status='L' ORDER BY ts_code LIMIT :limit"),
            {"limit": limit},
        ).fetchall()
    return {"stocks": [{"ts_code": r[0], "name": r[1], "market": r[2]} for r in rows]}
