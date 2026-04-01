# StockScan 对话记录

> 每次对话后更新。记录用户原始提问与 Claude 的核心结论应答。

---

## Session 1（历史会话，已压缩）

### Q: 筛选逻辑不一致 — 个股回测中 601877.SH 未被2.0规则命中

**用户提问：**
> 再次出现筛选逻辑不一致的问题，在个股回测入口里 601877.SH 没有被2.0规则命中

**核心结论：**
发现并修复了 `single_stock.py` 中三处 bug：
1. `close_vs_ma`：参数名读取错误（`v.get("n", 20)` 应为 `v.get("period", ...)`）
2. `ma_cross`：未支持 `days` 窗口参数（只检查当天，未扩展到多日内检测交叉）
3. `ma_alignment_bull`：缺少 MA60 检查（只验证 MA5>MA10>MA20，漏了 MA60）

修复后，601877.SH 在2.0规则下可于2026-02-12被命中（比1.0的2026-03-02提前约2.5周）。

---

### Q: 601877.SH 2月份应该已有上涨特征，当前方案能否优化？请制作2.0版本

**用户提问：**
> 我看了一下，基于低位蓄势主升浪捕捉，对于601877基本都是3月份命中规则，但该股2月份我直观感觉已经有一些特征了。目前的筛选方案是否还可以优化，因为我用这个方案对全量股票进行方案回测，效果并不好。如何还能进一步优化该方案？请挖地三尺再进行深入分析，条件多没问题，触发少没问题，但要尽可能满足回测效果，否则不具备实操价值。目前的低位蓄势主升浪捕捉先保留，你可以再做一个2.0版本方案。

**核心结论：**
深度分析601877.SH行情：
- 1.0 方案在 MA5>MA10>MA20>MA60 全排列对齐后（2026-03-02）才命中，信号偏晚
- 2月12日已出现 MA5/MA10 金叉（快线穿越慢线），且量比1.87、成交额放量，是更早的入场信号

**2.0方案设计（id=6，match_mode='all'，10条规则）：**

| 规则 | 指标 | 条件 |
|------|------|------|
| 涨幅1.5%-8% | pct_chg | BETWEEN 1.5, 8 |
| 站稳年线 | close_vs_ma(60) | > MA60 |
| MA5/MA10 金叉 | ma_cross | fast=5, slow=10, days=7 |
| 量比放大 | volume_ratio | ≥ 1.3 |
| 主力净流入 | net_mf_amount | > 0 |
| 近3日累计净流入 | cumulative_net_inflow | > 0, days=3 |
| 合理估值 | pe_ttm | BETWEEN 0, 80 |
| 合理换手 | turnover_rate | BETWEEN 0.8, 10 |
| 合理市值 | circ_mv | BETWEEN 200000, 15000000 |
| 排除ST | exclude_st | — |

---

### Q: 基于2.0回测观察到"连续正/连续负"的批次模式，是否与大盘相关？

**用户提问：**
> 我使用2.0模型，选择持股3天，回测了2026年1月1日至今。数据呈现了一个明显的特征，就是连续的正和连续的负比较多，零星的波动相对不是很多，你观察一下这个形态特征；我不知道你是否有大盘指数数据，是否具有一定相关性，或者跟什么相关，请你挖掘一下。

**核心结论：**
- 2.0方案批次收益与**上证综指3日涨幅**相关系数 = **0.657**（显著正相关）
- 本质原因：MA5/MA10金叉选出的是趋势初期高弹性股票（高Beta），放大市场涨跌
- 连续正/负批次的成因：A股板块轮动有持续性，相邻数日信号重叠度高，市场方向持续时表现聚集
- 加市场过滤器（当日大盘涨/在MA5上方等）实测均无改善，甚至更差（最好机会反而在"市场看似弱"时产生）
- 根治方向：提升个股质量过滤而非市场择时

---

### Q: 基于2.0观察，给出3.0版本

**用户提问：**
> 好的，而且基于你的观察给出方案的3.0版本

**核心结论：**
对2.0最差批次（Jan 27: -4.75%，Feb 3: -3.8%，Feb 26: -2.1%，Mar 3: -3.3%）进行拆解，发现问题个股特征：高涨幅触发但无大单支撑、量比虚高（小盘股放量但无方向性资金）。

**3.0方案设计（id=7，match_mode='all'，11条规则）：**

| 规则 | 相比2.0变化 |
|------|------------|
| 涨幅2%-8% | 下限提高至2%（过滤弱势跟涨） |
| 站稳年线 | 保留 |
| 站稳20日线 | **新增**（close > MA20，确认中期趋势） |
| MA5/MA10 金叉 | 保留 |
| 量比 ≥ 1.5 | 提高至1.5（更强量能确认） |
| 主力净流入 | 保留 |
| **大单+超大单净流入 > 0** | **新增**（net_lg_elg > 0，过滤散户炒作） |
| pe_ttm 0-70 | 收紧至70 |
| 换手率1%-8% | 收紧（去除极低换手） |
| 合理市值 | 保留 |
| 排除ST | 保留 |

效果验证（对比2.0最差日）：
- Jan 27: 候选股 30→10 只（-4.75%批次大幅收缩）
- Feb 3: 候选股 7→1 只（-3.8%批次几乎无信号，规避风险）
- Feb 26: 候选股 126→40 只（减少低质量信号）
- 2026-02-12（601877.SH 最佳入场日）：仍有28只候选，保留信号

---

### Q: 前端服务不稳定 / 局域网无法访问

**用户提问：**
> 前端的服务是不是又不在了，好像昨天就出过类似问题，确认一下服务状态，也确认服务是否稳定，有什么问题没有。
> 确认一下前端是否正常启动，我从局域网设备为什么没办法访问

**核心结论：**
发现两个问题并修复：
1. **Vite 只绑定 localhost**：`vite.config.ts` 缺少 `host: '0.0.0.0'`，局域网设备无法访问 → 已添加
2. **后端高CPU（51%）**：`uvicorn --reload` 监听了整个项目目录，包含 `frontend/node_modules`（268MB），文件系统事件风暴 → 改为 `--reload-dir backend`，CPU降至1.3%

修复后，局域网设备通过 `http://[服务器IP]:5173` 即可访问前端。

---

## Session 2（2026-03-22）

### Q: 方案回测跨越多个日期时速度慢，如何提升效率？

**用户提问：**
> 目前进行跨越多个日期的方案回测有些慢，这个有什么办法提升运行效率吗

**核心结论：**
定位瓶颈：每个交易日各自执行4次大 SQL 查询（PriceEvaluator 每次拉取100+天×5500只历史数据），对于49日回测 = 196次查询，总计约2700万行冗余数据传输。

**解决方案：预取缓存（Pre-fetch Once, Slice Per Day）**

修改文件：
- `evaluators/price.py`、`fundamental.py`、`flow.py`、`technical.py`：各增加 `preloaded_df` 可选参数，有传入时跳过 SQL 直接切片
- `api/portfolio_backtest.py`：在日循环前一次性预取所有所需数据表，传入各 Evaluator

**性能对比（2个月 / 49日回测）：**

| | 优化前 | 优化后 |
|--|--------|--------|
| SQL 查询次数 | ~196次 | ~5次 |
| 总数据量 | ~2700万行 | ~120万行 |
| 预计速度提升 | — | **10-20倍** |

实现细节：
- stock_basic 优先预取，作为 codes 过滤器供后续查询使用
- 股票名称 name_map 改为一次预取，消除每日名称查询
- 进度条新增"预加载数据..."状态提示
- 与原有单日筛选接口完全兼容（不传 preloaded 则走原 SQL 路径）

---

### Q: 优化已经完成了吗？

**用户提问：**
> 优化已经完成了吗

**核心结论：**
是的，全部代码修改已完成。重启后端后即生效。

---

## Session 4（2026-03-26）

### Q: 界面显示还是窄窄的

**用户提问：**
> 界面显示还是窄窄的 这个再确认一下

**核心结论：**
根因：`frontend/src/assets/main.css` 是 Vue 脚手架自带示例样式，含 `#app { max-width: 1280px }` 和 `@media { body { display:flex } #app { grid-template-columns: 1fr 1fr } }` 两处限制，覆盖所有页面。修复：将 main.css 替换为 `#app { width: 100%; min-height: 100vh; }`。

---

### Q: 删除按钮不能点击

**用户提问：**
> 选股方案管理里面的方案 很多删除按钮不能点击

**核心结论：**
原因：SchemesView.vue 中 `:disabled="row.is_builtin"`，三个内置方案均 `is_builtin=true`，删除按钮被禁用。用户自建方案可正常删除。待用户选择处理方式。

---

### Q: 每个方案设置定时自动触发筛选

**用户提问：**
> 后面我需要每个交易日能让部分方案在设定的时间自动触发筛选，需要增加这个功能能够对每个方案设置是否自动跑，以及自动跑的触发时间，然后另外一个程序会根据筛选结果的数据库记录，自动触发后面的操作

**核心结论：**
实现了完整的定时自动选股功能：
- DB 新增 `schedule_enabled (bool)` + `schedule_time (varchar "HH:MM")` 两列，Alembic 迁移已执行
- `backend/scheduler.py`（新增）：APScheduler BackgroundScheduler，每分钟检查一次，匹配方案时验证交易日、获取最新交易日、调用 `run_screening()` 写入 DB，防重跑
- `backend/main.py`：FastAPI lifespan 注册调度器
- 前端 SchemesView：列表页新增"自动运行"switch 列 + "触发时间"time-select 列，变更直接保存
- 验证：后端日志 `INFO:stockscan.scheduler:Scheduler started`，API 含 schedule 字段

---

## Session 3（2026-03-23）

### Q: 新建五层加权打分法V1.0选股模型

**用户提问：**
> 再新建一个选股模型 取名为五层加权打分法V1.0
> 模型构成：五层过滤器
> 第一层（硬筛）：质地筛选，同时满足所有条件才能进入后续评分
>   - 排除ST/ST*股票
>   - 非涨跌停板（过滤极端行情）
>   - 流通市值 30亿-2000亿
>   - 上市时间 ≥ 90天
>   - 近20日平均成交额 ≥ 5000万
> 第二层（趋势，权重30%）：均线多头排列、价格>MA20、均线多头发散、MACD金叉（近3日内）、距60日低点涨幅<40%
> 第三层（量能，权重25%）：量比1.5-5.0、换手率3%-15%、OBV趋势向上
> 第四层（形态，权重25%）：创近期20日新高、锤子线、红三兵
> 第五层（板块，权重20%）：所在板块平均涨幅>1.5%、板块涨停数≥2
> 选出综合评分最高的前30名

**核心结论：**
实现了完整的五层加权打分框架：

**新增/修改文件：**
1. `backend/engine/scoring.py`（新增）：`compute_scored_results()` 函数，layer_weights={2:0.30, 3:0.25, 4:0.25, 5:0.20}，L1全通过后对L2-L5计算加权得分，取top_n
2. `backend/engine/evaluators/sector.py`（新增）：`SectorEvaluator`，支持 `sector_pct_chg`（板块均涨幅）和 `sector_limit_up_count`（板块涨停数），使用 `stock_basic.industry` 分组，graceful fallback（列不存在时降级）
3. `backend/engine/evaluators/price.py`（修改）：新增4个指标 `avg_amount_20d`、`price_vs_nd_low`、`candlestick_hammer`（锤子线）、`three_soldiers`（红三兵），并增加 OHLC (open/high/low) 矩阵支持
4. `backend/engine/executor.py`（修改）：导入 SectorEvaluator 和 compute_scored_results，添加 `scored` 分支
5. `backend/api/portfolio_backtest.py`（修改）：添加 SectorEvaluator 到 evaluators 列表，添加 scored 分支，stock_basic 预取增加 `industry` 列（try/except 降级），SECTOR_METRICS_SET 加入预加载判断，新增价格指标也纳入 PRICE_METRICS_SET
6. `backend/seed/seed_data.py`（修改）：新增 SCHEME_3_RULES（18条规则，含 params={"layer": N}），seed() 函数改为幂等逻辑（按方案名判断是否已存在）

**执行结果：** 数据库写入成功，API 验证：id=8，match_mode=scored，min_match=30，18条规则，L1×5 / L2×5 / L3×3 / L4×3 / L5×2 分配正确。

---

## Session 5（2026-03-31）

### Q: 触发时间运行使用的是哪日的数据？

**用户提问：**
> 我已经给各方案设定了触发时间了，比如今天晚上跑，那它跑的日期是25号的数据还是26号的数据

**核心结论：**
scheduler 使用 `SELECT MAX(trade_date) FROM daily_price` 获取当前 stockdb 最新的交易日数据。
- StockDB 数据入库时间：每日 18:30~18:35 完成
- 19:00 触发 → 使用当日（26号）数据
- 18:00 之前触发 → 数据未入库，使用前日（25号）数据

**推荐：触发时间设在 19:00 之后确保数据完整**

---

### Q: 远端程序数据库连接失败，需修改 pg_hba.conf

**用户提问：**
> 远端程序执行了，但报错：`connection to server at "192.168.99.150", port 5432 failed: server closed the connection unexpectedly`
> 后续报错：`FATAL: no pg_hba.conf entry for host "10.7.7.66", user "stockscan_user", database "stockscan", no encryption`

**核心结论：**
PostgreSQL 服务器 (192.168.99.150) 的 `pg_hba.conf` 缺少允许远端 IP (10.7.7.66) 的规则。

需要操作：
1. 修改 PostgreSQL 服务器的 `/var/lib/pgsql/data/pg_hba.conf` 或 `/etc/postgresql/pg_hba.conf`
2. 添加规则：`host    stockscan    stockscan_user    10.7.7.66/32    trust` 或 `md5`
3. 重启 PostgreSQL 服务

用户要求直接修改，但 SSH 认证失败（权限/密码问题），需要：
- SSH 私钥路径、PostgreSQL 数据目录路径、或 root 密码

---

## Session 6（2026-04-01）

### Q: StockView 截图集成 — 创建 screenshot_records 表，前端展示截图记录

**用户提问：**
> StockView（截图工具）需要在本地保存截图的同时，向 StockScan 库中记录元数据，便于后续查询关联。
> 截图元数据包括：结果关联、任务名、股票代码、截图日期、文件名等。
> 核心需求：建表 → 提供查询 API → 前端能展示记录（文件名、日期等元数据，不展示实际图片）

**核心结论：**
完整的截图记录集成改造，分为 7 步逐步实施：

**1. Alembic 迁移（`9dccd3ccca38`）**
- 创建 `screenshot_records` 表，含 8 字段 + 3 索引 + 唯一约束
- 外键：result_detail_id → screening_result_detail(id) CASCADE
- 唯一约束：(result_detail_id, task_name, screenshot_date)

**2. SQLAlchemy 模型**
- `ScreenshotRecord` 类，关联 `ScreeningResultDetail.screenshots`
- 自动跟踪 created_at，反向关联支持级联删除

**3. Pydantic Schema**
- `ScreenshotRecordOut`：序列化截图记录（id, task_name, ts_code, screenshot_date, screenshot_filename, pdf_path, created_at）
- 扩展 `StockResultOut`：添加 `screenshots: list[ScreenshotRecordOut] = []`

**4. 后端 API 修改**
- GET `/api/screening/results/{id}` 使用 `selectinload` 显式加载 screenshots 关系
- `_build_detail_response()` 在构建 StockResultOut 时动态序列化 screenshots 列表

**5. 前端 API 类型**
- 添加 `ScreenshotRecord` 接口（7 字段）
- 更新 `StockResult` 接口：添加 `screenshots: ScreenshotRecord[]`

**6. 前端 UI 组件**
- ResultTable.vue：新增"截图"列（在"匹配"列之后）
- 展示逻辑：
  * 有截图：显示蓝色标签 "$数字 张"，点击弹窗展示列表
  * 无截图：显示灰色禁用标签"无"
- 弹窗内容：任务名 / 日期+时间 / 文件名 / PDF路径（若存在）

**7. 验证与测试**
- 数据库插入测试记录：screenshot_records 写入成功，关系正确
- API 查询验证：eager-load selectinload 工作，返回完整数据
- 前端展示验证：截图列正确显示，popover 内容完整

**改造成果**
- Commit: `998739d` Integrate StockView screenshot recording system
- StockView 可直接向 screenshot_records 表 INSERT 元数据
- StockScan 历史选股记录页面可立即查看并展示所有相关截图
- 支持多任务、多截图关联，唯一约束防重复
