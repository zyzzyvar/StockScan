from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import settings

# StockScan DB (read/write)
engine = create_engine(
    settings.stockscan_db_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# StockDB (read-only)
stockdb_engine = create_engine(
    settings.stockdb_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    execution_options={"postgresql_readonly": True},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
StockDBSession = sessionmaker(autocommit=False, autoflush=False, bind=stockdb_engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_stockdb():
    db = StockDBSession()
    try:
        yield db
    finally:
        db.close()
