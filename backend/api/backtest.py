from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db, get_stockdb
from ..models import Scheme
from ..schemas.backtest import BacktestRequest
from ..engine.single_stock import run_single_stock_backtest

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.post("/run")
def run_backtest(
    body: BacktestRequest,
    db: Session = Depends(get_db),
    stockdb: Session = Depends(get_stockdb),
):
    if not body.scheme_ids:
        raise HTTPException(400, "At least one scheme required")

    try:
        start = date.fromisoformat(body.start_date)
        end = date.fromisoformat(body.end_date)
    except ValueError:
        raise HTTPException(400, "Invalid date format, use YYYY-MM-DD")

    if start > end:
        raise HTTPException(400, "start_date must be before end_date")

    schemes = []
    for sid in body.scheme_ids:
        s = db.get(Scheme, sid)
        if not s:
            raise HTTPException(404, f"Scheme {sid} not found")
        schemes.append(s)

    stockdb_conn = stockdb.connection()
    result = run_single_stock_backtest(
        ts_code=body.ts_code,
        start_date=start,
        end_date=end,
        schemes=schemes,
        stockdb_conn=stockdb_conn,
    )
    return result
