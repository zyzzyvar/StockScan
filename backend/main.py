from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .api import schemes, templates, screening, market, backtest, portfolio_backtest
from .scheduler import init_scheduler, shutdown_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title="StockScan API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(schemes.router)
app.include_router(templates.router)
app.include_router(screening.router)
app.include_router(market.router)
app.include_router(backtest.router)
app.include_router(portfolio_backtest.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
