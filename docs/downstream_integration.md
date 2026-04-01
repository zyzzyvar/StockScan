# StockScan 下游集成指引

> 本文档面向需要读取 StockScan 选股结果的外部应用。
> 无论未来方案数量、触发时间、筛选结果如何变化，外部应用只需遵循本文档描述的查询模式即可。

---

## 1. 数据库连接

```
Host:     localhost
Port:     5432
Database: stockscan
User:     stockscan_user
Password: stockscan_pass   # 见 StockScan/.env
```

> 该账号对 `stockscan` 库只有 SELECT / INSERT / UPDATE / DELETE 权限，不能修改表结构。

---

## 2. 有哪些方案、何时运行、何时有结果

### 2.1 动态查询方案列表（推荐）

外部应用**不应硬编码方案 ID 或名称**，而是运行时查询：

```sql
SELECT
    id,
    name,
    match_mode,          -- 'all' | 'partial' | 'scored'
    min_match,           -- partial: 最低匹配数; scored: 取前N名
    schedule_enabled,    -- true = 已开启自动运行
    schedule_time        -- 'HH:MM' 触发时间，如 '19:00'
FROM scheme
WHERE schedule_enabled = true
ORDER BY id;
```

**示例结果（当前）：**

| id | name | match_mode | min_match | schedule_time |
|----|------|------------|-----------|---------------|
| 1 | 下午盯盘选股法 | all | null | 19:00 |
| 6 | 低位蓄势主升浪捕捉2.0 | all | null | 19:00 |
| 7 | 低位蓄势主升浪捕捉3.0 | all | null | 19:00 |
| 8 | 五层加权打分法V1.0 | scored | 30 | 19:00 |

> 未来新增方案、修改触发时间，外部应用无需改代码，每次查询即获取最新配置。

### 2.2 结果可用时间

| 触发时间 | 单方案耗时 | 最晚完成 | 建议读取时间 |
|---------|-----------|---------|------------|
| 19:00 | 5~20 秒/方案 | 19:02（4方案约 60 秒） | **19:05 之后** |

**计算逻辑：**
- 所有方案在调度器内**顺序执行**（非并行）
- 当前 4 个方案总耗时约 40~60 秒
- 即使未来增加到 10 个方案，19:10 前必然全部完成

**安全读取策略：**
```
等待到 schedule_time + 10 分钟 再查询，即可保证所有方案结果均已写入。
例：触发时间 19:00 → 19:10 之后读取，100% 安全。
```

---

## 3. 如何判断某方案当天是否已有结果

```sql
SELECT id, trade_date, full_match_count, partial_match_count, created_at
FROM screening_result
WHERE scheme_id = :scheme_id
  AND trade_date = :trade_date   -- 当天日期，如 '2026-03-26'
ORDER BY created_at DESC
LIMIT 1;
```

- 有结果 → 返回 1 行，`created_at` 为写入时间
- 无结果 → 返回 0 行（方案未运行、非交易日、或运行失败）

**轮询示例（伪代码）：**
```python
# 在 schedule_time + 5min 后开始轮询，最多等 15 分钟
for scheme in get_enabled_schemes():
    result = wait_for_result(scheme.id, today, timeout=15*60)
    if result:
        process(result)
```

---

## 4. 获取筛选结果股票列表

### 4.1 汇总信息

```sql
SELECT
    r.id           AS result_id,
    r.trade_date,
    s.name         AS scheme_name,
    s.match_mode,
    r.full_match_count,
    r.partial_match_count,
    r.total_stocks,
    r.duration_seconds,
    r.created_at
FROM screening_result r
JOIN scheme s ON s.id = r.scheme_id
WHERE r.scheme_id = :scheme_id
  AND r.trade_date = :trade_date
ORDER BY r.created_at DESC
LIMIT 1;
```

### 4.2 股票明细列表

```sql
SELECT
    d.ts_code,                          -- 股票代码，如 '000001.SZ'
    d.stock_name,                       -- 股票名称，如 '平安银行'
    d.close,                            -- 选股日收盘价
    d.pct_chg,                          -- 选股日涨跌幅（%）
    d.vol,                              -- 成交量（手）
    d.turnover_rate,                    -- 换手率（%）
    d.circ_mv,                          -- 流通市值（万元，÷10000=亿元）
    d.volume_ratio,                     -- 量比
    d.pe_ttm,                           -- 市盈率TTM（可为 null）
    d.pb,                               -- 市净率（可为 null）
    d.matched_rules,                    -- 命中规则数
    d.total_rules,                      -- 总规则数
    d.is_full_match,                    -- 是否全部规则命中
    d.rule_results                      -- JSONB，见下方说明
FROM screening_result_detail d
WHERE d.result_id = :result_id
ORDER BY
    -- scored 模式按评分排序，其他模式按涨幅排序
    (d.rule_results->>'_score')::float DESC NULLS LAST,
    d.pct_chg DESC;
```

### 4.3 `rule_results` 字段说明

`rule_results` 是 JSONB 格式，结构如下：

```json
{
  "66": true,
  "67": true,
  "68": false,
  "_score": 0.7733
}
```

| 键 | 类型 | 含义 |
|----|------|------|
| `"<rule_id>"` | boolean | 该规则是否命中（key 为规则 ID 的字符串形式） |
| `"_score"` | float \| null | 仅 `match_mode='scored'` 时存在，取值 0.0~1.0，越高越好 |

**不同 match_mode 下的结果含义：**

| match_mode | full_match_count | partial_match_count | is_full_match | _score |
|-----------|-----------------|---------------------|---------------|--------|
| `all` | 全部规则命中的股票数 | 0 | true | 无 |
| `partial` | 全部命中的股票数 | 满足最低数但未全中的股票数 | true/false | 无 |
| `scored` | 取得分前 N 名的股票数 | 0 | 均为 true | 0.0~1.0 |

---

## 5. 一次性获取当天所有方案结果（推荐模式）

```sql
SELECT
    s.id           AS scheme_id,
    s.name         AS scheme_name,
    s.match_mode,
    r.id           AS result_id,
    r.trade_date,
    r.full_match_count,
    r.created_at,
    d.ts_code,
    d.stock_name,
    d.close,
    d.pct_chg,
    d.turnover_rate,
    d.circ_mv,
    d.is_full_match,
    (d.rule_results->>'_score')::float AS score
FROM scheme s
JOIN screening_result r
    ON r.scheme_id = s.id AND r.trade_date = :trade_date
JOIN screening_result_detail d
    ON d.result_id = r.id
WHERE s.schedule_enabled = true
  AND d.is_full_match = true       -- 只取主要结果（去掉此条件可含 partial）
ORDER BY s.id, score DESC NULLS LAST, d.pct_chg DESC;
```

---

## 6. 异常情况处理

| 情况 | 现象 | 建议处理 |
|------|------|---------|
| 当天是非交易日 | `screening_result` 无当天记录 | 跳过，等下一个交易日 |
| 方案运行失败 | 无记录（调度器 catch 后记日志） | 检查 StockScan 后端日志 `/tmp/uvicorn.log` |
| 数据入库未完成 | 记录存在但 `full_match_count=0` | 等待后重试，或检查 StockDB 入库任务 |
| 结果为空（无股票通过筛选） | 记录存在，detail 表无对应行 | 正常，当天市场无符合条件标的 |

---

## 7. 方案配置变更通知

外部应用无需订阅变更通知。每次读取前执行 **第 2.1 节的方案列表查询**，即可获取最新的方案数量、名称和触发时间配置。数据库是唯一的 source of truth。
