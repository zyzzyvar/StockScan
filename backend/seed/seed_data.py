"""
Seed rule templates and built-in schemes into the stockscan database.
Run: python -m backend.seed.seed_data
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from backend.database import SessionLocal
from backend.models import RuleTemplate, Scheme, Rule

TEMPLATES = [
    # ============ TREND / PRICE (category="trend") ============
    {"name": "MA5支撑 (价格在MA5上方)", "category": "trend", "data_source": "daily_price", "metric": "close_vs_ma", "operator": "gt", "default_value": {"period": 5, "v": 0}, "lookback_days": 5, "description": "收盘价高于5日均线", "sort_order": 1},
    {"name": "MA10支撑 (价格在MA10上方)", "category": "trend", "data_source": "daily_price", "metric": "close_vs_ma", "operator": "gt", "default_value": {"period": 10, "v": 0}, "lookback_days": 10, "description": "收盘价高于10日均线", "sort_order": 2},
    {"name": "MA20支撑 (价格在MA20上方)", "category": "trend", "data_source": "daily_price", "metric": "close_vs_ma", "operator": "gt", "default_value": {"period": 20, "v": 0}, "lookback_days": 20, "description": "收盘价高于20日均线", "sort_order": 3},
    {"name": "MA60支撑 (价格在MA60上方)", "category": "trend", "data_source": "daily_price", "metric": "close_vs_ma", "operator": "gt", "default_value": {"period": 60, "v": 0}, "lookback_days": 60, "description": "收盘价高于60日均线", "sort_order": 4},
    {"name": "均线多头排列 (MA5>MA10>MA20>MA60)", "category": "trend", "data_source": "daily_price", "metric": "ma_alignment_bull", "operator": "eq", "default_value": {"v": 1}, "lookback_days": 60, "description": "MA5>MA10>MA20>MA60，多头排列", "sort_order": 5},
    {"name": "均线多头发散 (多头+各线斜率向上)", "category": "trend", "data_source": "daily_price", "metric": "ma_alignment_diverge", "operator": "eq", "default_value": {"v": 1}, "lookback_days": 60, "description": "MA5>MA10>MA20>MA60 且各均线斜率向上", "sort_order": 6},
    {"name": "MA5金叉MA10 (3日内)", "category": "trend", "data_source": "daily_price", "metric": "ma_cross", "operator": "eq", "default_value": {"fast": 5, "slow": 10, "days": 3}, "lookback_days": 15, "description": "MA5上穿MA10，近3日内发生", "sort_order": 7},
    {"name": "MA10金叉MA20 (3日内)", "category": "trend", "data_source": "daily_price", "metric": "ma_cross", "operator": "eq", "default_value": {"fast": 10, "slow": 20, "days": 3}, "lookback_days": 25, "description": "MA10上穿MA20，近3日内发生", "sort_order": 8},
    {"name": "创近期新高 (20日)", "category": "trend", "data_source": "daily_price", "metric": "new_high", "operator": "eq", "default_value": {"period": 20}, "lookback_days": 20, "description": "收盘价创20日新高", "sort_order": 9},
    {"name": "创近期新高 (60日)", "category": "trend", "data_source": "daily_price", "metric": "new_high", "operator": "eq", "default_value": {"period": 60}, "lookback_days": 60, "description": "收盘价创60日新高", "sort_order": 10},
    {"name": "股价在布林带中轨上方", "category": "trend", "data_source": "daily_price", "metric": "close_vs_boll", "operator": "gt", "default_value": {"band": "mid"}, "lookback_days": 20, "description": "收盘价高于Bollinger中轨(20日MA)", "sort_order": 11},
    {"name": "股价在布林带上轨下方 (未超买)", "category": "trend", "data_source": "daily_price", "metric": "close_vs_boll", "operator": "lt", "default_value": {"band": "upper"}, "lookback_days": 20, "description": "收盘价低于Bollinger上轨", "sort_order": 12},
    {"name": "涨幅3%-5%", "category": "trend", "data_source": "daily_price", "metric": "pct_chg", "operator": "between", "default_value": {"min": 3, "max": 5}, "lookback_days": 0, "description": "当日涨幅在3%到5%之间", "sort_order": 13},
    {"name": "涨幅0%-3% (温和上涨)", "category": "trend", "data_source": "daily_price", "metric": "pct_chg", "operator": "between", "default_value": {"min": 0, "max": 3}, "lookback_days": 0, "description": "当日涨幅在0%到3%之间", "sort_order": 14},
    {"name": "股价在日均价上方 (近似VWAP)", "category": "trend", "data_source": "daily_price", "metric": "close_vs_vwap", "operator": "gt", "default_value": {"v": 0}, "lookback_days": 0, "description": "收盘价高于当日VWAP近似值(amount*1000/vol/100)", "sort_order": 15},
    {"name": "成交量台阶式放大", "category": "trend", "data_source": "daily_price", "metric": "vol_step_up", "operator": "eq", "default_value": {"v": 1, "window": 8, "min_consecutive": 3}, "lookback_days": 8, "description": "近8日内成交量呈台阶式放大，至少3日连续递增", "sort_order": 16},
    {"name": "不在涨跌停板 (过滤极端行情)", "category": "trend", "data_source": "daily_price", "metric": "not_limit", "operator": "eq", "default_value": {"v": 1}, "lookback_days": 0, "description": "当日既未涨停也未跌停", "sort_order": 17},

    # ============ VOLUME (category="volume") ============
    {"name": "换手率2%-10%", "category": "volume", "data_source": "daily_fundamental", "metric": "turnover_rate", "operator": "between", "default_value": {"min": 2, "max": 10}, "lookback_days": 0, "description": "换手率在2%到10%之间，活跃但不过热", "sort_order": 1},
    {"name": "换手率>3%", "category": "volume", "data_source": "daily_fundamental", "metric": "turnover_rate", "operator": "gt", "default_value": {"v": 3}, "lookback_days": 0, "description": "换手率超过3%", "sort_order": 2},
    {"name": "量比>1 (放量)", "category": "volume", "data_source": "daily_fundamental", "metric": "volume_ratio", "operator": "gt", "default_value": {"v": 1}, "lookback_days": 0, "description": "量比大于1，当日成交活跃", "sort_order": 3},
    {"name": "量比>2 (显著放量)", "category": "volume", "data_source": "daily_fundamental", "metric": "volume_ratio", "operator": "gt", "default_value": {"v": 2}, "lookback_days": 0, "description": "量比大于2，显著放量", "sort_order": 4},
    {"name": "成交量>MA20成交量*1.2", "category": "volume", "data_source": "daily_price", "metric": "vol_vs_ma", "operator": "gt", "default_value": {"period": 20, "ratio": 1.2}, "lookback_days": 20, "description": "当日成交量超过20日均量的1.2倍", "sort_order": 5},
    {"name": "成交量连续缩量 (3日)", "category": "volume", "data_source": "daily_price", "metric": "vol_shrink", "operator": "eq", "default_value": {"days": 3}, "lookback_days": 3, "description": "连续3日成交量递减（缩量整理）", "sort_order": 6},
    {"name": "OBV趋势向上", "category": "volume", "data_source": "daily_price", "metric": "obv_trend", "operator": "gt", "default_value": {"period": 5}, "lookback_days": 10, "description": "OBV 5日均值高于10日前值，趋势向上", "sort_order": 7},

    # ============ VALUATION (category="valuation") ============
    {"name": "PE_TTM 0-50 (合理估值)", "category": "valuation", "data_source": "daily_fundamental", "metric": "pe_ttm", "operator": "between", "default_value": {"min": 0, "max": 50}, "lookback_days": 0, "description": "市盈率(TTM)在0到50之间", "sort_order": 1},
    {"name": "PE_TTM 0-30 (低估值)", "category": "valuation", "data_source": "daily_fundamental", "metric": "pe_ttm", "operator": "between", "default_value": {"min": 0, "max": 30}, "lookback_days": 0, "description": "市盈率(TTM)低于30", "sort_order": 2},
    {"name": "PB 0-8", "category": "valuation", "data_source": "daily_fundamental", "metric": "pb", "operator": "between", "default_value": {"min": 0, "max": 8}, "lookback_days": 0, "description": "市净率在0到8之间", "sort_order": 3},
    {"name": "PB 0-3 (低市净率)", "category": "valuation", "data_source": "daily_fundamental", "metric": "pb", "operator": "between", "default_value": {"min": 0, "max": 3}, "lookback_days": 0, "description": "市净率低于3", "sort_order": 4},
    {"name": "PS_TTM 0-10", "category": "valuation", "data_source": "daily_fundamental", "metric": "ps_ttm", "operator": "between", "default_value": {"min": 0, "max": 10}, "lookback_days": 0, "description": "市销率(TTM)在0到10之间", "sort_order": 5},
    {"name": "股息率>1% (有分红)", "category": "valuation", "data_source": "daily_fundamental", "metric": "dv_ttm", "operator": "gt", "default_value": {"v": 1}, "lookback_days": 0, "description": "股息率(TTM)高于1%", "sort_order": 6},
    {"name": "股息率>3% (高分红)", "category": "valuation", "data_source": "daily_fundamental", "metric": "dv_ttm", "operator": "gt", "default_value": {"v": 3}, "lookback_days": 0, "description": "股息率(TTM)高于3%", "sort_order": 7},

    # ============ CAPITAL FLOW (category="flow") ============
    {"name": "主力净流入>0", "category": "flow", "data_source": "money_flow", "metric": "net_mf_amount", "operator": "gt", "default_value": {"v": 0}, "lookback_days": 0, "description": "当日主力资金净流入为正", "sort_order": 1},
    {"name": "大单净流入>0", "category": "flow", "data_source": "money_flow", "metric": "net_lg_amount", "operator": "gt", "default_value": {"v": 0}, "lookback_days": 0, "description": "当日大单净流入为正", "sort_order": 2},
    {"name": "超大单净流入>0", "category": "flow", "data_source": "money_flow", "metric": "net_elg_amount", "operator": "gt", "default_value": {"v": 0}, "lookback_days": 0, "description": "当日超大单净流入为正", "sort_order": 3},
    {"name": "主力净流入率>0%", "category": "flow", "data_source": "money_flow", "metric": "net_mf_vol_pct", "operator": "gt", "default_value": {"v": 0}, "lookback_days": 0, "description": "主力净流入占总成交量比例为正", "sort_order": 4},
    {"name": "连续3日主力净流入", "category": "flow", "data_source": "money_flow", "metric": "consecutive_net_inflow", "operator": "gte", "default_value": {"days": 3}, "lookback_days": 3, "description": "连续3日主力资金净流入", "sort_order": 5},
    {"name": "5日累计主力净流入>0", "category": "flow", "data_source": "money_flow", "metric": "cumulative_net_inflow", "operator": "gt", "default_value": {"days": 5, "v": 0}, "lookback_days": 5, "description": "近5日主力资金累计净流入为正", "sort_order": 6},
    {"name": "超大单+大单合计净流入>0", "category": "flow", "data_source": "money_flow", "metric": "net_lg_elg_amount", "operator": "gt", "default_value": {"v": 0}, "lookback_days": 0, "description": "大单与超大单合计净流入为正", "sort_order": 7},

    # ============ TECHNICAL (category="technical") ============
    {"name": "MACD金叉 (近3日)", "category": "technical", "data_source": "daily_price", "metric": "macd_cross", "operator": "eq", "default_value": {"signal": "golden", "days": 3}, "lookback_days": 60, "description": "MACD DIF上穿DEA，近3日内发生", "sort_order": 1},
    {"name": "MACD死叉 (近3日)", "category": "technical", "data_source": "daily_price", "metric": "macd_cross", "operator": "eq", "default_value": {"signal": "death", "days": 3}, "lookback_days": 60, "description": "MACD DIF下穿DEA，近3日内发生", "sort_order": 2},
    {"name": "MACD柱状线由负转正", "category": "technical", "data_source": "daily_price", "metric": "macd_hist_positive", "operator": "eq", "default_value": {"v": 1}, "lookback_days": 60, "description": "MACD柱状线(HIST)由负转正", "sort_order": 3},
    {"name": "KDJ金叉 (近3日)", "category": "technical", "data_source": "daily_price", "metric": "kdj_cross", "operator": "eq", "default_value": {"signal": "golden", "days": 3}, "lookback_days": 30, "description": "KDJ K线上穿D线，近3日内发生", "sort_order": 4},
    {"name": "KDJ超卖区域 (J<20)", "category": "technical", "data_source": "daily_price", "metric": "kdj_j", "operator": "lt", "default_value": {"v": 20}, "lookback_days": 30, "description": "KDJ J值低于20，处于超卖区域", "sort_order": 5},
    {"name": "KDJ超买区域 (J>80)", "category": "technical", "data_source": "daily_price", "metric": "kdj_j", "operator": "gt", "default_value": {"v": 80}, "lookback_days": 30, "description": "KDJ J值高于80，处于超买区域", "sort_order": 6},
    {"name": "RSI(6) 30-70 (强势区)", "category": "technical", "data_source": "daily_price", "metric": "rsi", "operator": "between", "default_value": {"period": 6, "min": 30, "max": 70}, "lookback_days": 20, "description": "6日RSI在30到70之间", "sort_order": 7},
    {"name": "RSI(14) <30 (超卖)", "category": "technical", "data_source": "daily_price", "metric": "rsi", "operator": "lt", "default_value": {"period": 14, "v": 30}, "lookback_days": 20, "description": "14日RSI低于30，处于超卖", "sort_order": 8},
    {"name": "RSI(14) >70 (超买)", "category": "technical", "data_source": "daily_price", "metric": "rsi", "operator": "gt", "default_value": {"period": 14, "v": 70}, "lookback_days": 20, "description": "14日RSI高于70，处于超买", "sort_order": 9},
    {"name": "CCI 超卖反弹 (<-100到-100内)", "category": "technical", "data_source": "daily_price", "metric": "cci", "operator": "between", "default_value": {"period": 14, "min": -200, "max": -100}, "lookback_days": 20, "description": "CCI在-200到-100，超卖区域", "sort_order": 10},
    {"name": "威廉%R 超卖 (<-80)", "category": "technical", "data_source": "daily_price", "metric": "willr", "operator": "lt", "default_value": {"period": 14, "v": -80}, "lookback_days": 20, "description": "威廉指标低于-80，超卖区域", "sort_order": 11},
    {"name": "ATR波动率扩大", "category": "technical", "data_source": "daily_price", "metric": "atr_expand", "operator": "gt", "default_value": {"period": 14, "ratio": 1.2}, "lookback_days": 20, "description": "ATR高于近期平均ATR的1.2倍，波动率扩大", "sort_order": 12},

    # ============ FILTER (category="filter") ============
    {"name": "流通市值50亿-1500亿 (中大盘)", "category": "filter", "data_source": "daily_fundamental", "metric": "circ_mv", "operator": "between", "default_value": {"min": 500000, "max": 15000000}, "lookback_days": 0, "description": "流通市值在50亿到1500亿万元之间（万元单位）", "sort_order": 1},
    {"name": "流通市值20亿-500亿 (中小盘)", "category": "filter", "data_source": "daily_fundamental", "metric": "circ_mv", "operator": "between", "default_value": {"min": 200000, "max": 5000000}, "lookback_days": 0, "description": "流通市值在20亿到500亿万元之间（万元单位）", "sort_order": 2},
    {"name": "总市值>50亿", "category": "filter", "data_source": "daily_fundamental", "metric": "total_mv", "operator": "gt", "default_value": {"v": 500000}, "lookback_days": 0, "description": "总市值超过50亿（万元单位）", "sort_order": 3},
    {"name": "排除ST股票", "category": "filter", "data_source": "stock_basic", "metric": "exclude_st", "operator": "eq", "default_value": {"v": 1}, "lookback_days": 0, "description": "排除ST/ST*/退市风险股票", "sort_order": 4},
    {"name": "主板股票 (沪深主板)", "category": "filter", "data_source": "stock_basic", "metric": "market", "operator": "eq", "default_value": {"v": "主板"}, "lookback_days": 0, "description": "仅包含沪深主板股票", "sort_order": 5},
    {"name": "上市超过1年", "category": "filter", "data_source": "stock_basic", "metric": "listing_age_days", "operator": "gte", "default_value": {"v": 365}, "lookback_days": 0, "description": "上市超过1年，排除次新股", "sort_order": 6},

    # ============ HISTORICAL STATS (category="historical") ============
    {"name": "近5日涨幅>5%", "category": "historical", "data_source": "daily_price", "metric": "n_day_return", "operator": "gt", "default_value": {"period": 5, "v": 5}, "lookback_days": 5, "description": "近5日累计涨幅超过5%", "sort_order": 1},
    {"name": "近20日涨幅>10%", "category": "historical", "data_source": "daily_price", "metric": "n_day_return", "operator": "gt", "default_value": {"period": 20, "v": 10}, "lookback_days": 20, "description": "近20日累计涨幅超过10%", "sort_order": 2},
    {"name": "连续上涨3日以上", "category": "historical", "data_source": "daily_price", "metric": "consecutive_up_days", "operator": "gte", "default_value": {"v": 3}, "lookback_days": 5, "description": "连续上涨天数达到3日以上", "sort_order": 3},
    {"name": "近20日最大回撤<15%", "category": "historical", "data_source": "daily_price", "metric": "max_drawdown", "operator": "lt", "default_value": {"period": 20, "v": 15}, "lookback_days": 20, "description": "近20日最大回撤幅度小于15%", "sort_order": 4},
]

# Built-in Scheme 1: 下午盯盘选股法 (Afternoon Rally Scanner)
SCHEME_1_RULES = [
    {"sort_order": 1, "name": "涨幅3%-5%", "category": "trend", "data_source": "daily_price", "metric": "pct_chg", "operator": "between", "value": {"min": 3, "max": 5}, "lookback_days": 0},
    {"sort_order": 2, "name": "量比>1", "category": "volume", "data_source": "daily_fundamental", "metric": "volume_ratio", "operator": "gt", "value": {"v": 1}, "lookback_days": 0},
    {"sort_order": 3, "name": "换手率2%-10%", "category": "volume", "data_source": "daily_fundamental", "metric": "turnover_rate", "operator": "between", "value": {"min": 2, "max": 10}, "lookback_days": 0},
    {"sort_order": 4, "name": "流通市值50亿-1500亿", "category": "filter", "data_source": "daily_fundamental", "metric": "circ_mv", "operator": "between", "value": {"min": 500000, "max": 15000000}, "lookback_days": 0},
    {"sort_order": 5, "name": "成交量台阶式放大", "category": "trend", "data_source": "daily_price", "metric": "vol_step_up", "operator": "eq", "value": {"v": 1, "window": 8, "min_consecutive": 3}, "lookback_days": 8},
    {"sort_order": 6, "name": "均线多头发散", "category": "trend", "data_source": "daily_price", "metric": "ma_alignment_diverge", "operator": "eq", "value": {"v": 1}, "lookback_days": 60},
    {"sort_order": 7, "name": "股价在日均价上方", "category": "trend", "data_source": "daily_price", "metric": "close_vs_vwap", "operator": "gt", "value": {"v": 0}, "lookback_days": 0},
]

# Built-in Scheme 2: 成长潜力选股 (Growth Potential)
SCHEME_2_RULES = [
    {"sort_order": 1, "name": "价格在MA20上方", "category": "trend", "data_source": "daily_price", "metric": "close_vs_ma", "operator": "gt", "value": {"period": 20, "v": 0}, "lookback_days": 20},
    {"sort_order": 2, "name": "均线多头排列", "category": "trend", "data_source": "daily_price", "metric": "ma_alignment_bull", "operator": "eq", "value": {"v": 1}, "lookback_days": 60},
    {"sort_order": 3, "name": "换手率2%-10%", "category": "volume", "data_source": "daily_fundamental", "metric": "turnover_rate", "operator": "between", "value": {"min": 2, "max": 10}, "lookback_days": 0},
    {"sort_order": 4, "name": "成交量>MA20均量*1.2", "category": "volume", "data_source": "daily_price", "metric": "vol_vs_ma", "operator": "gt", "value": {"period": 20, "ratio": 1.2}, "lookback_days": 20},
    {"sort_order": 5, "name": "PE_TTM 0-50", "category": "valuation", "data_source": "daily_fundamental", "metric": "pe_ttm", "operator": "between", "value": {"min": 0, "max": 50}, "lookback_days": 0},
    {"sort_order": 6, "name": "PB 0-8", "category": "valuation", "data_source": "daily_fundamental", "metric": "pb", "operator": "between", "value": {"min": 0, "max": 8}, "lookback_days": 0},
    {"sort_order": 7, "name": "主力净流入>0", "category": "flow", "data_source": "money_flow", "metric": "net_mf_amount", "operator": "gt", "value": {"v": 0}, "lookback_days": 0},
    {"sort_order": 8, "name": "大单净流入>0", "category": "flow", "data_source": "money_flow", "metric": "net_lg_amount", "operator": "gt", "value": {"v": 0}, "lookback_days": 0},
    {"sort_order": 9, "name": "流通市值20亿-500亿", "category": "filter", "data_source": "daily_fundamental", "metric": "circ_mv", "operator": "between", "value": {"min": 200000, "max": 5000000}, "lookback_days": 0},
]


# Built-in Scheme 3: 五层加权打分法V1.0
# L1 = hard filter (all must pass)
# L2 = trend (30%), L3 = volume (25%), L4 = pattern (25%), L5 = sector (20%)
SCHEME_3_RULES = [
    # ── Layer 1: Hard filters ──────────────────────────────────────────────────
    {"sort_order": 1,  "name": "L1-排除ST",          "category": "filter",    "data_source": "stock_basic",      "metric": "exclude_st",          "operator": "eq",      "value": {"v": 1},                                  "lookback_days": 0,  "params": {"layer": 1}},
    {"sort_order": 2,  "name": "L1-非涨跌停",         "category": "trend",     "data_source": "daily_price",      "metric": "not_limit",           "operator": "eq",      "value": {"v": 1},                                  "lookback_days": 0,  "params": {"layer": 1}},
    {"sort_order": 3,  "name": "L1-流通市值30亿-2000亿","category": "filter",   "data_source": "daily_fundamental","metric": "circ_mv",             "operator": "between", "value": {"min": 300000, "max": 20000000},            "lookback_days": 0,  "params": {"layer": 1}},
    {"sort_order": 4,  "name": "L1-上市超90天",        "category": "filter",    "data_source": "stock_basic",      "metric": "listing_age_days",    "operator": "gte",     "value": {"v": 90},                                 "lookback_days": 0,  "params": {"layer": 1}},
    {"sort_order": 5,  "name": "L1-20日均额>5000万",   "category": "volume",    "data_source": "daily_price",      "metric": "avg_amount_20d",      "operator": "gte",     "value": {"period": 20, "v": 50000},                 "lookback_days": 20, "params": {"layer": 1}},
    # ── Layer 2: Trend (weight 30%) ────────────────────────────────────────────
    {"sort_order": 6,  "name": "L2-均线多头排列",       "category": "trend",     "data_source": "daily_price",      "metric": "ma_alignment_bull",   "operator": "eq",      "value": {"v": 1},                                  "lookback_days": 60, "params": {"layer": 2}},
    {"sort_order": 7,  "name": "L2-价格>MA20",         "category": "trend",     "data_source": "daily_price",      "metric": "close_vs_ma",         "operator": "gt",      "value": {"period": 20, "v": 0},                    "lookback_days": 20, "params": {"layer": 2}},
    {"sort_order": 8,  "name": "L2-均线多头发散",       "category": "trend",     "data_source": "daily_price",      "metric": "ma_alignment_diverge","operator": "eq",      "value": {"v": 1},                                  "lookback_days": 60, "params": {"layer": 2}},
    {"sort_order": 9,  "name": "L2-MACD金叉近3日",     "category": "technical", "data_source": "daily_price",      "metric": "macd_cross",          "operator": "eq",      "value": {"signal": "golden", "days": 3},            "lookback_days": 60, "params": {"layer": 2}},
    {"sort_order": 10, "name": "L2-距60日低点<40%",    "category": "trend",     "data_source": "daily_price",      "metric": "price_vs_nd_low",     "operator": "lt",      "value": {"period": 60, "v": 40},                   "lookback_days": 60, "params": {"layer": 2}},
    # ── Layer 3: Volume (weight 25%) ───────────────────────────────────────────
    {"sort_order": 11, "name": "L3-量比1.5-5.0",       "category": "volume",    "data_source": "daily_fundamental","metric": "volume_ratio",        "operator": "between", "value": {"min": 1.5, "max": 5.0},                  "lookback_days": 0,  "params": {"layer": 3}},
    {"sort_order": 12, "name": "L3-换手率3%-15%",      "category": "volume",    "data_source": "daily_fundamental","metric": "turnover_rate",       "operator": "between", "value": {"min": 3, "max": 15},                     "lookback_days": 0,  "params": {"layer": 3}},
    {"sort_order": 13, "name": "L3-OBV趋势向上",       "category": "volume",    "data_source": "daily_price",      "metric": "obv_trend",           "operator": "gt",      "value": {"period": 5},                             "lookback_days": 10, "params": {"layer": 3}},
    # ── Layer 4: Pattern (weight 25%) ──────────────────────────────────────────
    {"sort_order": 14, "name": "L4-创20日新高",         "category": "trend",     "data_source": "daily_price",      "metric": "new_high",            "operator": "eq",      "value": {"period": 20},                            "lookback_days": 20, "params": {"layer": 4}},
    {"sort_order": 15, "name": "L4-锤子线",             "category": "technical", "data_source": "daily_price",      "metric": "candlestick_hammer",  "operator": "eq",      "value": {},                                        "lookback_days": 1,  "params": {"layer": 4}},
    {"sort_order": 16, "name": "L4-红三兵",             "category": "technical", "data_source": "daily_price",      "metric": "three_soldiers",      "operator": "eq",      "value": {},                                        "lookback_days": 4,  "params": {"layer": 4}},
    # ── Layer 5: Sector (weight 20%) ───────────────────────────────────────────
    {"sort_order": 17, "name": "L5-板块均涨>1.5%",     "category": "sector",    "data_source": "daily_price",      "metric": "sector_pct_chg",      "operator": "gt",      "value": {"v": 1.5},                                "lookback_days": 0,  "params": {"layer": 5}},
    {"sort_order": 18, "name": "L5-板块涨停≥2",        "category": "sector",    "data_source": "daily_price",      "metric": "sector_limit_up_count","operator": "gte",    "value": {"v": 2},                                  "lookback_days": 0,  "params": {"layer": 5}},
]


def seed():
    db = SessionLocal()
    try:
        seeded_templates = db.query(RuleTemplate).count() > 0
        if not seeded_templates:
            print("Seeding rule templates...")
            template_objs = []
            for t in TEMPLATES:
                obj = RuleTemplate(**t)
                db.add(obj)
                template_objs.append(obj)
            db.flush()
            print("Seeding built-in schemes (1 & 2)...")

            # Scheme 1
            s1 = Scheme(
                name="下午盯盘选股法",
                description="基于午后行情的动量选股策略：涨幅适中、量比活跃、换手合理、市值中等、成交量台阶放大、均线发散向上、价格在均价线上方",
                is_builtin=True,
                match_mode="partial",
                min_match=5,
            )
            db.add(s1)
            db.flush()
            for r in SCHEME_1_RULES:
                db.add(Rule(scheme_id=s1.id, **r))

            # Scheme 2
            s2 = Scheme(
                name="成长潜力选股",
                description="综合趋势、量能、估值、资金流的成长型选股策略",
                is_builtin=True,
                match_mode="partial",
                min_match=6,
            )
            db.add(s2)
            db.flush()
            for r in SCHEME_2_RULES:
                db.add(Rule(scheme_id=s2.id, **r))

            db.commit()
            print(f"Done! {len(TEMPLATES)} templates, 2 built-in schemes.")
        else:
            print("Templates already seeded, skipping templates and schemes 1 & 2.")

        # Scheme 3: 五层加权打分法V1.0 — insert only if not already present
        if db.query(Scheme).filter(Scheme.name == "五层加权打分法V1.0").count() == 0:
            print("Seeding 五层加权打分法V1.0...")
            s3 = Scheme(
                name="五层加权打分法V1.0",
                description="五层加权打分模型：L1硬筛（质地）→L2趋势(30%)→L3量能(25%)→L4形态(25%)→L5板块(20%)，取综合评分前30名",
                is_builtin=True,
                match_mode="scored",
                min_match=30,
            )
            db.add(s3)
            db.flush()
            for r in SCHEME_3_RULES:
                db.add(Rule(scheme_id=s3.id, **r))
            db.commit()
            print("五层加权打分法V1.0 seeded with 18 rules.")
        else:
            print("五层加权打分法V1.0 already exists, skipping.")

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed()
