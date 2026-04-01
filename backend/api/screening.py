from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import text
from ..database import get_db, get_stockdb
from ..models import Scheme, ScreeningResult, ScreeningResultDetail, ScreenshotRecord
from ..schemas.screening import (
    ScreeningRunRequest, ScreeningResultOut, ScreeningResultDetailOut, StockResultOut, ScreenshotRecordOut
)
from ..engine.executor import run_screening

router = APIRouter(prefix="/api/screening", tags=["screening"])


@router.post("/run", response_model=ScreeningResultDetailOut)
def run(body: ScreeningRunRequest, db: Session = Depends(get_db), stockdb: Session = Depends(get_stockdb)):
    scheme = db.get(Scheme, body.scheme_id)
    if not scheme:
        raise HTTPException(404, "Scheme not found")
    if not scheme.rules:
        raise HTTPException(400, "Scheme has no rules")

    # Check trade date is valid — calendar first, fall back to actual price data presence
    is_open = stockdb.execute(
        text("SELECT is_open FROM trade_calendar WHERE cal_date = :d"),
        {"d": body.trade_date},
    ).scalar()
    if is_open is not None and int(is_open) != 1:
        raise HTTPException(400, f"{body.trade_date} is not a trading day")
    if is_open is None:
        has_data = stockdb.execute(
            text("SELECT 1 FROM daily_price WHERE trade_date = :d LIMIT 1"),
            {"d": body.trade_date},
        ).scalar()
        if not has_data:
            raise HTTPException(400, f"{body.trade_date} is not a trading day")

    stockdb_conn = stockdb.connection()
    result = run_screening(scheme, body.trade_date, db, stockdb_conn)

    return _build_detail_response(result)


@router.get("/results", response_model=list[ScreeningResultOut])
def list_results(scheme_id: int | None = None, limit: int = 20, db: Session = Depends(get_db)):
    q = db.query(ScreeningResult).order_by(ScreeningResult.created_at.desc())
    if scheme_id:
        q = q.filter(ScreeningResult.scheme_id == scheme_id)
    return q.limit(limit).all()


@router.get("/results/{result_id}", response_model=ScreeningResultDetailOut)
def get_result(result_id: int, db: Session = Depends(get_db)):
    result = db.query(ScreeningResult).options(
        selectinload(ScreeningResult.details).selectinload(ScreeningResultDetail.screenshots)
    ).filter_by(id=result_id).first()
    if not result:
        raise HTTPException(404, "Result not found")
    return _build_detail_response(result)


@router.get("/results/{result_id}/forward")
def get_forward_performance(
    result_id: int,
    db: Session = Depends(get_db),
    stockdb: Session = Depends(get_stockdb),
):
    """返回选股结果后续最多3个交易日的实际涨跌表现。"""
    result = db.get(ScreeningResult, result_id)
    if not result:
        raise HTTPException(404, "Result not found")
    if not result.details:
        return {"forward_dates": [], "stocks": {}, "summary": {}}

    trade_date = result.trade_date

    # 获取之后最多3个交易日
    date_rows = stockdb.execute(
        text("""
            SELECT DISTINCT trade_date FROM daily_price
            WHERE trade_date > :d
            ORDER BY trade_date LIMIT 3
        """),
        {"d": trade_date},
    ).fetchall()
    # 保留 date 对象用于 SQL，字符串用于返回 JSON
    forward_date_objs = [r[0] for r in date_rows]
    forward_dates = [str(d) for d in forward_date_objs]

    if not forward_dates:
        return {"forward_dates": [], "stocks": {}, "summary": {}}

    ts_codes = [d.ts_code for d in result.details]
    t0_map = {d.ts_code: float(d.close) if d.close is not None else None for d in result.details}

    # 批量查询后续各日收盘价（传 date 对象避免类型转换错误）
    rows = stockdb.execute(
        text("""
            SELECT ts_code, trade_date, close, pct_chg
            FROM daily_price
            WHERE trade_date = ANY(:dates) AND ts_code = ANY(:codes)
        """),
        {"dates": forward_date_objs, "codes": ts_codes},
    ).fetchall()

    # price_map[ts_code][date_str] = {close, pct_chg}
    price_map: dict[str, dict[str, dict]] = {}
    for r in rows:
        ts = r[0]
        ds = str(r[1])
        if ts not in price_map:
            price_map[ts] = {}
        price_map[ts][ds] = {
            "close": float(r[2]) if r[2] is not None else None,
            "pct_chg": float(r[3]) if r[3] is not None else None,
        }

    # 构建每只股票的 t1/t2/t3 数据
    stocks: dict[str, dict] = {}
    for ts in ts_codes:
        t0 = t0_map.get(ts)
        entry: dict[str, dict | None] = {}
        for i, fd in enumerate(forward_dates):
            day = price_map.get(ts, {}).get(fd)
            if day and day["close"] is not None and t0:
                pct_vs_t0 = round((day["close"] - t0) / t0 * 100, 2)
            else:
                pct_vs_t0 = None
            entry[f"t{i+1}"] = {
                "close": day["close"] if day else None,
                "pct_chg": day["pct_chg"] if day else None,   # 当日自身涨跌幅
                "pct_vs_t0": pct_vs_t0,                       # 相对选股日收盘价的涨跌幅
            }
        stocks[ts] = entry

    # 汇总：等权组合收益
    summary: dict[str, dict] = {}
    for i, fd in enumerate(forward_dates):
        key = f"t{i+1}"
        pcts = [stocks[ts][key]["pct_vs_t0"] for ts in ts_codes if stocks[ts][key]["pct_vs_t0"] is not None]
        summary[key] = {
            "date": fd,
            "avg_return": round(sum(pcts) / len(pcts), 2) if pcts else None,
            "positive_count": sum(1 for p in pcts if p > 0),
            "flat_count": sum(1 for p in pcts if p == 0),
            "negative_count": sum(1 for p in pcts if p < 0),
            "total_count": len(pcts),
        }

    return {"forward_dates": forward_dates, "stocks": stocks, "summary": summary}


def _build_detail_response(result: ScreeningResult) -> ScreeningResultDetailOut:
    details = [
        StockResultOut(
            ts_code=d.ts_code,
            stock_name=d.stock_name,
            matched_rules=d.matched_rules,
            total_rules=d.total_rules,
            is_full_match=bool(d.is_full_match),
            rule_results=d.rule_results,
            close=float(d.close) if d.close is not None else None,
            pct_chg=float(d.pct_chg) if d.pct_chg is not None else None,
            vol=float(d.vol) if d.vol is not None else None,
            turnover_rate=float(d.turnover_rate) if d.turnover_rate is not None else None,
            circ_mv=float(d.circ_mv) if d.circ_mv is not None else None,
            volume_ratio=float(d.volume_ratio) if d.volume_ratio is not None else None,
            pe_ttm=float(d.pe_ttm) if d.pe_ttm is not None else None,
            pb=float(d.pb) if d.pb is not None else None,
            screenshots=[
                ScreenshotRecordOut(
                    id=sr.id,
                    task_name=sr.task_name,
                    ts_code=sr.ts_code,
                    screenshot_date=sr.screenshot_date,
                    screenshot_filename=sr.screenshot_filename,
                    pdf_path=sr.pdf_path,
                    created_at=sr.created_at,
                )
                for sr in d.screenshots
            ],
        )
        for d in result.details
    ]
    return ScreeningResultDetailOut(
        id=result.id,
        scheme_id=result.scheme_id,
        trade_date=result.trade_date,
        total_stocks=result.total_stocks,
        full_match_count=result.full_match_count,
        partial_match_count=result.partial_match_count,
        duration_seconds=result.duration_seconds,
        created_at=result.created_at,
        details=details,
    )
