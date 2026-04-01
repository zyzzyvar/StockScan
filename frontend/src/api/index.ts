import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000
})

export interface Scheme {
  id: number
  name: string
  description: string | null
  match_mode: string
  min_match: number | null
  is_builtin: boolean
  created_at: string
  updated_at: string
  rules?: Rule[]
  rule_count?: number
  schedule_enabled: boolean
  schedule_time: string | null
}

export interface Rule {
  id: number
  scheme_id: number
  sort_order: number
  template_id: number | null
  name: string
  category: string
  data_source: string
  metric: string
  operator: string
  value: Record<string, unknown> | null
  lookback_days: number
  params: Record<string, unknown> | null
  enabled: boolean
}

export interface RuleTemplate {
  id: number
  name: string
  category: string
  description: string | null
  data_source: string
  metric: string
  operator: string
  default_value: Record<string, unknown> | null
  lookback_days: number
  params: Record<string, unknown> | null
  sort_order: number
}

export interface ScreeningResult {
  id: number
  scheme_id: number
  trade_date: string
  total_stocks: number
  full_match_count: number
  partial_match_count: number
  duration_seconds: number | null
  created_at: string
  details?: StockResult[]
}

export interface ScreenshotRecord {
  id: number
  task_name: string
  ts_code: string
  screenshot_date: string
  screenshot_filename: string
  pdf_path: string | null
  created_at: string
}

export interface StockResult {
  ts_code: string
  stock_name: string | null
  matched_rules: number
  total_rules: number
  is_full_match: boolean
  rule_results: Record<string, boolean> | null
  close: number | null
  pct_chg: number | null
  vol: number | null
  turnover_rate: number | null
  circ_mv: number | null
  volume_ratio: number | null
  pe_ttm: number | null
  pb: number | null
  screenshots: ScreenshotRecord[]
}

// Schemes
export const schemesApi = {
  list: () => api.get<Scheme[]>('/schemes'),
  get: (id: number) => api.get<Scheme>(`/schemes/${id}`),
  create: (data: Partial<Scheme>) => api.post<Scheme>('/schemes', data),
  update: (id: number, data: Partial<Scheme>) => api.put<Scheme>(`/schemes/${id}`, data),
  delete: (id: number) => api.delete(`/schemes/${id}`),
  copy: (id: number) => api.post<Scheme>(`/schemes/${id}/copy`),
  addRule: (schemeId: number, data: Partial<Rule>) => api.post<Rule>(`/schemes/${schemeId}/rules`, data),
  updateRule: (schemeId: number, ruleId: number, data: Partial<Rule>) =>
    api.put<Rule>(`/schemes/${schemeId}/rules/${ruleId}`, data),
  deleteRule: (schemeId: number, ruleId: number) =>
    api.delete(`/schemes/${schemeId}/rules/${ruleId}`),
  reorderRules: (schemeId: number, ruleIds: number[]) =>
    api.put<Rule[]>(`/schemes/${schemeId}/rules/reorder`, { rule_ids: ruleIds })
}

// Templates
export const templatesApi = {
  list: (category?: string) => api.get<RuleTemplate[]>('/templates', { params: { category } })
}

// Screening
export const screeningApi = {
  run: (schemeId: number, tradeDate: string) =>
    api.post<ScreeningResult>('/screening/run', { scheme_id: schemeId, trade_date: tradeDate }),
  results: (schemeId?: number) => api.get<ScreeningResult[]>('/screening/results', { params: { scheme_id: schemeId } }),
  getResult: (id: number) => api.get<ScreeningResult>(`/screening/results/${id}`),
  getForward: (id: number) => api.get<ForwardPerformance>(`/screening/results/${id}/forward`)
}

export interface ForwardDayData {
  close: number | null
  pct_chg: number | null
  pct_vs_t0: number | null
}

export interface ForwardSummaryDay {
  date: string
  avg_return: number | null
  positive_count: number
  flat_count: number
  negative_count: number
  total_count: number
}

export interface ForwardPerformance {
  forward_dates: string[]
  stocks: Record<string, { t1?: ForwardDayData; t2?: ForwardDayData; t3?: ForwardDayData }>
  summary: { t1?: ForwardSummaryDay; t2?: ForwardSummaryDay; t3?: ForwardSummaryDay }
}

// Backtest
export interface BacktestRuleResult {
  passed: boolean
  display: string | null
}

export interface BacktestDayResult {
  date: string
  matched: number
  is_matched: boolean
  rule_results: Record<string, BacktestRuleResult>
}

export interface BacktestSchemeResult {
  scheme_id: number
  scheme_name: string
  match_mode: string
  min_match: number | null
  total_rules: number
  rules: Rule[]
  daily: BacktestDayResult[]
  stats: { total_days: number; matched_days: number; match_rate: number }
}

export interface BacktestPricePoint {
  date: string
  open: number
  high: number
  low: number
  close: number
  vol: number
  pct_chg: number
}

export interface BacktestResult {
  ts_code: string
  stock_name: string | null
  price_series: BacktestPricePoint[]
  schemes: BacktestSchemeResult[]
}

export const backtestApi = {
  run: (params: { ts_code: string; start_date: string; end_date: string; scheme_ids: number[] }) =>
    api.post<BacktestResult>('/backtest/run', params)
}

// Portfolio backtest
export interface PortfolioStockTrade {
  ts_code: string
  stock_name: string | null
  buy_price: number | null
  sell_price: number | null
  raw_return: number | null
  net_return: number | null
}

export interface PortfolioBatch {
  buy_date: string
  sell_date: string | null
  stock_count: number
  valid_count: number
  avg_net_return: number | null
  stocks: PortfolioStockTrade[]
}

export interface PortfolioSummary {
  total_batches: number
  covered_days: number
  total_trading_days: number
  coverage_pct: number
  cumulative_return: number
  annualized_return: number
  win_rate: number
  avg_batch_return: number
  max_drawdown: number
  total_trades: number
  avg_stocks_per_batch: number
  transaction_cost_pct: number
}

export interface PortfolioBacktestResult {
  scheme_id: number
  scheme_name: string
  start_date: string
  end_date: string
  hold_days: number
  summary: PortfolioSummary
  equity_curve: { date: string; value: number }[]
  batches: PortfolioBatch[]
}

export interface PortfolioTaskProgress {
  status: 'running' | 'done' | 'error'
  current: number
  total: number
  pct: number
  message: string
  result: PortfolioBacktestResult | null
  error: string | null
}

export const portfolioBacktestApi = {
  start: (params: { scheme_id: number; start_date: string; end_date: string; hold_days: number; enabled_rule_ids?: number[] }) =>
    api.post<{ task_id: string }>('/portfolio-backtest/start', params),
  progress: (taskId: string) =>
    api.get<PortfolioTaskProgress>(`/portfolio-backtest/progress/${taskId}`),
}

// Market
export const marketApi = {
  latestTradeDate: () => api.get<{ trade_date: string }>('/market/latest-trade-date'),
  tradeDates: (start?: string, end?: string) =>
    api.get<{ dates: string[] }>('/market/trade-dates', { params: { start, end } })
}

export default api
