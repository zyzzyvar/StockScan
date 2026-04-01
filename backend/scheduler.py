"""
Background scheduler: check every minute whether any scheme is due to run,
then execute the screening for the latest available trading day.
"""
import logging
from datetime import date, datetime

from apscheduler.schedulers.background import BackgroundScheduler

from .database import SessionLocal, StockDBSession
from .models import Scheme, ScreeningResult
from .engine.executor import run_screening

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stockscan.scheduler")

_scheduler = BackgroundScheduler(timezone="Asia/Shanghai")


def init_scheduler() -> None:
    _scheduler.add_job(_check_and_run, "cron", minute="*", id="schedule_check",
                       max_instances=1, coalesce=True)
    _scheduler.start()
    logger.info("Scheduler started")


def shutdown_scheduler() -> None:
    _scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")


def _check_and_run() -> None:
    now_hhmm = datetime.now().strftime("%H:%M")
    today = date.today()

    db = SessionLocal()
    stockdb = StockDBSession()
    try:
        # Find schemes scheduled for this minute
        due_schemes = (
            db.query(Scheme)
            .filter(Scheme.schedule_enabled.is_(True),
                    Scheme.schedule_time == now_hhmm)
            .all()
        )
        if not due_schemes:
            return

        # Check if today is a trading day
        is_open = stockdb.execute(
            __import__("sqlalchemy").text(
                "SELECT is_open FROM trade_calendar WHERE cal_date = :d"
            ),
            {"d": today},
        ).scalar()
        if is_open is not None and int(is_open) != 1:
            logger.info("Scheduler: %s is not a trading day, skipping", today)
            return

        # Get latest available trade date in daily_price
        latest_date = stockdb.execute(
            __import__("sqlalchemy").text("SELECT MAX(trade_date) FROM daily_price")
        ).scalar()
        if latest_date is None:
            logger.warning("Scheduler: no data in daily_price, skipping")
            return
        trade_date = latest_date if isinstance(latest_date, date) else latest_date.date()

        stockdb_conn = stockdb.connection()

        for scheme in due_schemes:
            # Skip if already ran for this scheme + trade_date today
            already = (
                db.query(ScreeningResult)
                .filter(
                    ScreeningResult.scheme_id == scheme.id,
                    ScreeningResult.trade_date == trade_date,
                )
                .first()
            )
            if already:
                logger.info("Scheduler: scheme %d (%s) already ran for %s, skipping",
                            scheme.id, scheme.name, trade_date)
                continue

            try:
                result = run_screening(scheme, trade_date, db, stockdb_conn)
                logger.info(
                    "Scheduler: scheme %d (%s) → %s, full=%d partial=%d",
                    scheme.id, scheme.name, trade_date,
                    result.full_match_count, result.partial_match_count,
                )
            except Exception as exc:
                logger.error("Scheduler: scheme %d (%s) failed: %s",
                             scheme.id, scheme.name, exc, exc_info=True)

    except Exception as exc:
        logger.error("Scheduler _check_and_run error: %s", exc, exc_info=True)
    finally:
        db.close()
        stockdb.close()
