# StockScan Implementation Plan

## Phase 1: Foundation ✅
- [x] Create `stockscan` DB + `stockscan_user` via `scripts/init_db.sh`
- [x] Project scaffolding: backend/, .env, requirements.txt
- [x] config.py, database.py (dual-engine)
- [x] SQLAlchemy models (Scheme, Rule, RuleTemplate, ScreeningResult, ScreeningResultDetail)
- [x] Alembic initial migration
- [x] Seed: 60 rule templates + 2 built-in schemes

## Phase 2: Backend API ✅
- [x] Pydantic schemas
- [x] Scheme CRUD + copy endpoint
- [x] Rule CRUD + reorder endpoint
- [x] Template listing API
- [x] Market data helpers (trade dates, latest date)

## Phase 3: Screening Engine ✅
- [x] FundamentalEvaluator (SQL, PE/PB/turnover/circ_mv/stock_basic filters)
- [x] PriceEvaluator (vectorized numpy batch, MA/vol/pct_chg)
- [x] FlowEvaluator (money_flow, net inflow metrics)
- [x] TechnicalEvaluator (pandas_ta, MACD/KDJ/RSI/BOLL/CCI)
- [x] Executor orchestrator
- [x] POST /api/screening/run endpoint
- [x] Performance: 8.6s for 5480 stocks (< 10s target) ✅

## Phase 4 & 5: Frontend ✅
- [x] Vue 3 + Vite + Element Plus + vuedraggable setup
- [x] Main layout + routing (3 views)
- [x] ScreeningView: date picker, scheme selector, run button, stats
- [x] ResultTable component with full/partial match display
- [x] SchemesView: CRUD, copy, delete
- [x] SchemeEditorView: draggable rules, template library browser
- [x] HistoryView: past results with detail
- [x] Pinia stores (scheme, screening) + Axios API client
- [x] CSV export

## Review
- Backend: http://localhost:8000/docs (Swagger UI)
- Frontend: http://localhost:5173
- Screening: 8.6s for 5480 stocks with 7-rule scheme ✅
- 14 partial matches found on 2026-03-20 with 下午盯盘选股法 ✅
