# StockScan - 智能选股系统

> 一个基于多层评分体系的 A 股选股平台，支持定时自动筛选、回测分析、方案管理等功能。

## 🌟 核心特性

### 选股策略
- **五层加权打分法 V1.0** — 综合评分模型，包含 5 层筛选器和加权评分：
  - L1 硬筛：质地筛选（排除 ST、涨跌停、市值、上市时间、成交额）
  - L2 趋势（30%）：均线多头、MACD 金叉、距低点涨幅等
  - L3 量能（25%）：量比、换手率、OBV 趋势
  - L4 形态（25%）：创近期新高、锤子线、红三兵
  - L5 板块（20%）：板块涨幅、涨停数

- **低位蓄势主升浪捕捉系列** — 趋势初期介入策略
  - 2.0 版：MA5/MA10 金叉 + 量比放量 + 资金确认
  - 3.0 版：在 2.0 基础上增加 MA20 确认、大单资金筛选

- **下午盯盘选股法** — 动量短期策略
  - 午后行情动量、量比活跃、换手合理

### 定时自动筛选
- 每个方案独立设定触发时间和启用状态
- APScheduler 驱动，每分钟检查一次
- 自动防重跑（同日期不重复执行）
- 筛选结果自动保存到数据库

### 回测分析
- **单方案回测**：日期范围内指定方案的历史表现
- **组合回测**：多个方案组合，支持持股天数、买卖信号等配置
- **性能优化**：预取缓存机制，跨月份回测速度提升 10-20 倍

### 方案管理
- 图形化规则编辑器
- 支持 18+ 个技术指标
- 规则模板库（快速复用）
- 内置方案与自定义方案

## 🛠️ 技术栈

### 后端
- **框架**：FastAPI + SQLAlchemy ORM
- **数据库**：PostgreSQL（本地 stockscan + 远端 stockdb）
- **任务调度**：APScheduler（定时筛选）
- **数据处理**：Pandas + NumPy

### 前端
- **框架**：Vue 3 + TypeScript
- **UI 组件**：Element Plus
- **图表**：ECharts
- **路由**：Vue Router
- **状态管理**：Pinia
- **构建工具**：Vite

### 基础设施
- **Web 服务器**：Uvicorn
- **开发服务器**：Vite dev server
- **数据库迁移**：Alembic
- **进程管理**：macOS launchd（自启动）

## 📋 前置条件

- Python 3.10+
- Node.js 20+
- PostgreSQL 12+（2 个数据库）
  - `stockscan` — 方案、规则、筛选结果
  - `stockdb` — 股票行情数据（read-only）

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone git@github.com:zyzzyvar/StockScan.git
cd StockScan
```

### 2. 配置环境

```bash
# 复制环境配置模板
cp .env.example .env

# 编辑 .env，配置数据库连接
# STOCKSCAN_DB_URL=postgresql+psycopg2://user:pass@localhost:5432/stockscan
# STOCKDB_URL=postgresql+psycopg2://user:pass@localhost:5432/stockdb
```

### 3. 初始化数据库

```bash
# 创建数据库（如果未创建）
createdb stockscan
createdb stockdb

# 运行迁移，创建表结构
cd backend
alembic upgrade head
cd ..

# 种子数据（创建内置方案和规则）
python3 -c "from backend.seed.seed_data import seed; seed()"
```

### 4. 安装依赖

```bash
# 后端依赖
pip install -r requirements.txt

# 前端依赖
cd frontend
npm install
cd ..
```

### 5. 启动服务

#### 方式 A：开发模式（前后端分离）

```bash
# 终端 1 — 启动后端（端口 8000）
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload-dir backend

# 终端 2 — 启动前端（端口 5173）
cd frontend
npm run dev
```

访问 http://localhost:5173

#### 方式 B：自启动模式（macOS）

系统重启后自动启动后端和前端（launchd 配置已预置）。

```bash
# 检查启动状态
launchctl list | grep stockscan
```

## 📚 主要目录结构

```
StockScan/
├── backend/
│   ├── api/              # FastAPI 路由（筛选、回测、方案管理）
│   ├── engine/           # 选股引擎核心
│   │   ├── evaluators/   # 5 类评估器（价格、基本面、资金流、技术、板块）
│   │   ├── executor.py   # 筛选执行器
│   │   └── scoring.py    # 加权打分计算
│   ├── models/           # SQLAlchemy ORM 模型
│   ├── schemas/          # Pydantic 数据模式
│   ├── seed/             # 初始化数据（方案、规则）
│   ├── scheduler.py      # 定时任务调度器
│   ├── main.py           # FastAPI 应用入口
│   └── database.py       # 数据库连接配置
├── frontend/
│   ├── src/
│   │   ├── views/        # 页面组件（筛选、回测、管理）
│   │   ├── components/   # 可复用组件
│   │   ├── stores/       # Pinia 状态管理
│   │   ├── api/          # 后端 API 调用
│   │   └── router/       # 路由配置
│   ├── package.json      # 项目依赖
│   └── vite.config.ts    # 构建配置
├── alembic/              # 数据库迁移脚本
├── docs/                 # 文档
│   ├── 操作手册.md       # 用户操作指南
│   ├── downstream_integration.md  # 外部应用接入指南
│   └── dba_pg_hba_instructions.md # PostgreSQL 配置指引
└── requirements.txt      # Python 依赖
```

## 📖 使用指南

### 创建筛选方案

1. 进入 **方案管理** 页面
2. 点击 **新建方案**，填写：
   - 方案名称、描述
   - 匹配模式（all / partial / scored）
3. 进入 **规则编辑器**，添加规则（支持 18+ 指标）
4. 配置 **自动触发**：
   - 启用自动运行
   - 设定触发时间（推荐 19:00，确保数据完整）

### 执行筛选

#### 手动筛选
- **实时筛选**：选择方案和日期，获取当日的候选股
- 结果显示：候选股代码、名称、评分、走势图

#### 定时自动筛选
- 方案在设定时间自动运行
- 结果自动保存，可在 **筛选历史** 中查看

### 回测分析

#### 单方案回测
1. 选择方案、日期范围、持股天数
2. 查看批次统计（胜率、平均涨幅、最大回撤等）
3. 导出 Excel 报告

#### 组合回测
1. 选择多个方案、权重、持股配置
2. 运行回测，获取组合表现
3. 对比不同配置的效果

## 🔧 配置说明

### 环境变量（.env）

```ini
# 本地 StockScan 数据库（写入方案、规则、筛选结果）
STOCKSCAN_DB_URL=postgresql+psycopg2://user:pass@localhost:5432/stockscan

# 远端 StockDB 数据库（读取股票行情数据，只读）
STOCKDB_URL=postgresql+psycopg2://user:pass@stockdb-server:5432/stockdb
```

### 定时筛选时间建议

StockDB 数据入库时间：每日 **18:30 ~ 18:35**

- ✅ 安全时间：**19:00 及之后**
- ⚠️ 风险时间：18:30 前（数据可能不完整）

### PostgreSQL 远端连接

如果 StockDB 在不同机器上，DBA 需修改 `pg_hba.conf`：

```conf
host    stockdb    stockscan_user    <client_ip>/32    trust
```

参考 `docs/dba_pg_hba_instructions.md`。

## 🎯 API 端点概览

### 筛选相关
- `POST /api/screening/run` — 执行筛选
- `GET /api/screening/history` — 筛选历史
- `GET /api/screening/result/{result_id}` — 筛选结果详情

### 方案管理
- `GET /api/schemes` — 获取所有方案
- `POST /api/schemes` — 创建方案
- `PUT /api/schemes/{id}` — 更新方案
- `DELETE /api/schemes/{id}` — 删除方案

### 回测
- `POST /api/backtest/single-scheme` — 单方案回测
- `POST /api/backtest/portfolio` — 组合回测

### 规则和模板
- `GET /api/rule-templates` — 规则模板列表
- `POST /api/rules` — 创建规则

详见 `docs/downstream_integration.md` 获取完整 API 文档。

## 📊 数据库关系图

```
Scheme（筛选方案）
├── Rule（规则）
│   └── RuleTemplate（规则模板）
└── ScreeningResult（筛选结果）
    └── ScreeningResultDetail（候选股详情）
```

## 🔍 故障排除

### 后端无法连接 StockDB
**错误**：`relation "stockdb.daily_price" does not exist`

**原因**：StockDB 跨机器访问，pg_hba.conf 未配置允许规则

**解决**：
1. 联系 DBA，按 `docs/dba_pg_hba_instructions.md` 修改 pg_hba.conf
2. 重启 PostgreSQL

### 前端无法访问
**检查**：
- 后端是否运行：`curl http://localhost:8000/api/schemes`
- 前端是否运行：`curl http://localhost:5173`

### 定时筛选未触发
**检查**：
1. 方案是否启用自动运行（schedule_enabled=true）
2. 触发时间是否在当前时间之前
3. 后端日志是否有 scheduler 错误：`tail -f ~/Library/Logs/stockscan_backend.log | grep scheduler`

## 📝 文档

- `docs/操作手册.md` — 详细的用户操作指南
- `docs/downstream_integration.md` — 外部应用读取筛选结果的方式
- `docs/dba_pg_hba_instructions.md` — PostgreSQL 远端连接配置

## 🤝 贡献

欢迎提交 Issue 和 Pull Request。

## 📄 许可证

MIT License

---

**快速链接**：
- [API 文档](docs/downstream_integration.md)
- [操作手册](docs/操作手册.md)
- [DBA 配置指引](docs/dba_pg_hba_instructions.md)
