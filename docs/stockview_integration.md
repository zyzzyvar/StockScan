# StockView 截图集成指引

> 本文档说明如何在 StockView 中集成截图记录写入 StockScan 数据库。

## 概述

StockView 在保存本地截图的同时，需要向 StockScan 的 `screenshot_records` 表中写入元数据，以便 StockScan 前端在历史选股记录中展示截图信息。

**核心流程**：
```
StockView 截图保存 → 查询选股结果 ID → 写入 screenshot_records
                                      ↓
                            StockScan 前端展示截图列
```

---

## 1. 数据库连接配置

### 连接信息

```
主机: localhost (或网络地址)
端口: 5432
数据库: stockscan
用户: stockscan_user
密码: stockscan_pass
```

### 连接字符串示例

**Python (psycopg2)**:
```python
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="stockscan",
    user="stockscan_user",
    password="stockscan_pass"
)
cursor = conn.cursor()
```

**Python (SQLAlchemy)**:
```python
from sqlalchemy import create_engine

engine = create_engine(
    "postgresql+psycopg2://stockscan_user:stockscan_pass@localhost:5432/stockscan"
)
```

**Node.js (pg)**:
```javascript
const { Pool } = require('pg');

const pool = new Pool({
  host: 'localhost',
  port: 5432,
  database: 'stockscan',
  user: 'stockscan_user',
  password: 'stockscan_pass',
});
```

**Go (pq)**:
```go
import _ "github.com/lib/pq"

db, err := sql.Open("postgres", 
  "host=localhost port=5432 user=stockscan_user password=stockscan_pass dbname=stockscan sslmode=disable")
```

**Java (JDBC)**:
```java
String url = "jdbc:postgresql://localhost:5432/stockscan";
String user = "stockscan_user";
String password = "stockscan_pass";
Connection conn = DriverManager.getConnection(url, user, password);
```

---

## 2. 表结构说明

### screenshot_records 表结构

```sql
CREATE TABLE screenshot_records (
    id SERIAL PRIMARY KEY,
    result_detail_id INT NOT NULL REFERENCES screening_result_detail(id) ON DELETE CASCADE,
    task_name VARCHAR(255) NOT NULL,
    ts_code VARCHAR(20) NOT NULL,
    screenshot_date DATE NOT NULL,
    screenshot_filename VARCHAR(512) NOT NULL,
    pdf_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_record UNIQUE(result_detail_id, task_name, screenshot_date),
    INDEX idx_result_detail (result_detail_id),
    INDEX idx_task_date (task_name, screenshot_date),
    INDEX idx_ts_code_date (ts_code, screenshot_date)
);
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | SERIAL | - | 自增主键 |
| `result_detail_id` | INT | ✅ | 外键，指向 screening_result_detail.id（选股结果明细） |
| `task_name` | VARCHAR(255) | ✅ | 选股方案名称，与 scheme.name 对应 |
| `ts_code` | VARCHAR(20) | ✅ | 股票代码（6位或全标准码，如 600000.SH） |
| `screenshot_date` | DATE | ✅ | 截图日期 |
| `screenshot_filename` | VARCHAR(512) | ✅ | 本地截图文件相对/绝对路径 |
| `pdf_path` | TEXT | ❌ | PDF 文件路径（可选，若生成了 PDF） |
| `created_at` | TIMESTAMP | - | 记录创建时间（自动，默认当前时间） |

### 约束说明

**唯一约束**：`UNIQUE(result_detail_id, task_name, screenshot_date)`
- 同一个选股结果明细、同一个任务、同一个截图日期，只能有一条记录
- 防止重复写入，如果尝试插入重复记录会报错

**外键约束**：`result_detail_id` → `screening_result_detail(id)`
- 必须先在选股结果中有对应的明细记录
- 明细记录删除时，对应的所有截图记录自动级联删除

---

## 3. 查询 result_detail_id

在写入截图记录之前，需要先查询对应选股结果的 `screening_result_detail.id`。

### 查询方法

**基于方案名 + 股票代码 + 交易日**：

```sql
SELECT srd.id
FROM screening_result_detail srd
JOIN screening_result sr ON sr.id = srd.result_id
JOIN scheme s ON s.id = sr.scheme_id
WHERE s.name = '低位蓄势主升浪捕捉2'   -- 方案名
  AND srd.ts_code = '000550.SZ'          -- 股票代码
  AND sr.trade_date = '2026-04-01'       -- 交易日
LIMIT 1;
```

**预期返回**: 一条记录，包含 `id` 字段

### Python 示例

```python
import psycopg2
from datetime import date

conn = psycopg2.connect(...)
cursor = conn.cursor()

# 参数
task_name = "低位蓄势主升浪捕捉2"
ts_code = "000550.SZ"
trade_date = date(2026, 4, 1)

# 查询
query = """
SELECT srd.id
FROM screening_result_detail srd
JOIN screening_result sr ON sr.id = srd.result_id
JOIN scheme s ON s.id = sr.scheme_id
WHERE s.name = %s
  AND srd.ts_code = %s
  AND sr.trade_date = %s
LIMIT 1
"""
cursor.execute(query, (task_name, ts_code, trade_date))
result = cursor.fetchone()

if result:
    result_detail_id = result[0]
    print(f"Found result_detail_id: {result_detail_id}")
else:
    print("Result not found - selection may not have been run yet")
    result_detail_id = None
```

---

## 4. 写入截图记录

### SQL 插入语句

```sql
INSERT INTO screenshot_records 
  (result_detail_id, task_name, ts_code, screenshot_date, screenshot_filename, pdf_path)
VALUES
  (7336, '低位蓄势主升浪捕捉2', '000550.SZ', '2026-04-01', '/Screenshots/20260401_000550_SZ.png', '/PDFs/20260401_000550_SZ.pdf');
```

### Python 示例（psycopg2）

```python
import psycopg2
from datetime import date

def insert_screenshot(
    result_detail_id: int,
    task_name: str,
    ts_code: str,
    screenshot_date: date,
    screenshot_filename: str,
    pdf_path: str = None
):
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="stockscan",
        user="stockscan_user",
        password="stockscan_pass"
    )
    cursor = conn.cursor()
    
    try:
        query = """
        INSERT INTO screenshot_records 
          (result_detail_id, task_name, ts_code, screenshot_date, screenshot_filename, pdf_path)
        VALUES 
          (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (
            result_detail_id,
            task_name,
            ts_code,
            screenshot_date,
            screenshot_filename,
            pdf_path
        ))
        conn.commit()
        print(f"✅ 截图记录写入成功")
        return True
    except psycopg2.IntegrityError as e:
        conn.rollback()
        print(f"❌ 写入失败（可能是重复记录）: {e}")
        return False
    except Exception as e:
        conn.rollback()
        print(f"❌ 数据库错误: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

# 使用示例
insert_screenshot(
    result_detail_id=7336,
    task_name="低位蓄势主升浪捕捉2",
    ts_code="000550.SZ",
    screenshot_date=date(2026, 4, 1),
    screenshot_filename="/Users/zyzbot/Screenshots/20260401_000550_SZ.png",
    pdf_path="/Users/zyzbot/PDFs/20260401_000550_SZ.pdf"
)
```

### Python 示例（SQLAlchemy）

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import date
from backend.models import ScreenshotRecord

engine = create_engine("postgresql+psycopg2://stockscan_user:stockscan_pass@localhost:5432/stockscan")
Session = sessionmaker(bind=engine)
session = Session()

def insert_screenshot_alchemy(
    result_detail_id: int,
    task_name: str,
    ts_code: str,
    screenshot_date: date,
    screenshot_filename: str,
    pdf_path: str = None
):
    try:
        record = ScreenshotRecord(
            result_detail_id=result_detail_id,
            task_name=task_name,
            ts_code=ts_code,
            screenshot_date=screenshot_date,
            screenshot_filename=screenshot_filename,
            pdf_path=pdf_path
        )
        session.add(record)
        session.commit()
        print(f"✅ 截图记录写入成功: ID={record.id}")
        return record.id
    except Exception as e:
        session.rollback()
        print(f"❌ 写入失败: {e}")
        return None
    finally:
        session.close()
```

### Node.js 示例（pg）

```javascript
const { Pool } = require('pg');

const pool = new Pool({
  host: 'localhost',
  port: 5432,
  database: 'stockscan',
  user: 'stockscan_user',
  password: 'stockscan_pass',
});

async function insertScreenshot(data) {
  const {
    result_detail_id,
    task_name,
    ts_code,
    screenshot_date,
    screenshot_filename,
    pdf_path
  } = data;

  const query = `
    INSERT INTO screenshot_records 
      (result_detail_id, task_name, ts_code, screenshot_date, screenshot_filename, pdf_path)
    VALUES 
      ($1, $2, $3, $4, $5, $6)
    RETURNING id
  `;

  try {
    const result = await pool.query(query, [
      result_detail_id,
      task_name,
      ts_code,
      screenshot_date,
      screenshot_filename,
      pdf_path
    ]);
    console.log('✅ 截图记录写入成功:', result.rows[0].id);
    return result.rows[0].id;
  } catch (error) {
    console.error('❌ 写入失败:', error.message);
    return null;
  }
}

// 使用示例
insertScreenshot({
  result_detail_id: 7336,
  task_name: '低位蓄势主升浪捕捉2',
  ts_code: '000550.SZ',
  screenshot_date: '2026-04-01',
  screenshot_filename: '/Screenshots/20260401_000550_SZ.png',
  pdf_path: '/PDFs/20260401_000550_SZ.pdf'
});
```

---

## 5. 完整工作流示例

### Python 完整示例

```python
import psycopg2
from datetime import date

def save_screenshot_to_stockscan(
    task_name: str,           # 选股方案名称
    ts_code: str,             # 股票代码
    trade_date: date,         # 选股交易日
    screenshot_path: str,     # 本地截图路径
    pdf_path: str = None      # PDF 路径（可选）
):
    """
    完整的截图保存流程：
    1. 连接数据库
    2. 查询选股结果 ID
    3. 写入截图记录
    4. 返回结果
    """
    
    conn = psycopg2.connect(
        host="localhost", port=5432, database="stockscan",
        user="stockscan_user", password="stockscan_pass"
    )
    cursor = conn.cursor()
    
    try:
        # Step 1: 查询 result_detail_id
        query_detail = """
        SELECT srd.id
        FROM screening_result_detail srd
        JOIN screening_result sr ON sr.id = srd.result_id
        JOIN scheme s ON s.id = sr.scheme_id
        WHERE s.name = %s
          AND srd.ts_code = %s
          AND sr.trade_date = %s
        LIMIT 1
        """
        cursor.execute(query_detail, (task_name, ts_code, trade_date))
        result = cursor.fetchone()
        
        if not result:
            print(f"❌ 未找到选股结果 - 方案: {task_name}, 股票: {ts_code}, 日期: {trade_date}")
            print("   请确保选股方案已运行且找到了此股票")
            return None
        
        result_detail_id = result[0]
        print(f"✅ 找到选股结果: result_detail_id={result_detail_id}")
        
        # Step 2: 写入截图记录
        query_insert = """
        INSERT INTO screenshot_records 
          (result_detail_id, task_name, ts_code, screenshot_date, screenshot_filename, pdf_path)
        VALUES 
          (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """
        cursor.execute(query_insert, (
            result_detail_id, task_name, ts_code, trade_date, screenshot_path, pdf_path
        ))
        conn.commit()
        
        screenshot_id = cursor.fetchone()[0]
        print(f"✅ 截图记录写入成功: screenshot_id={screenshot_id}")
        return screenshot_id
        
    except psycopg2.IntegrityError as e:
        conn.rollback()
        print(f"❌ 唯一约束冲突（可能是重复记录）: {e}")
        return None
    except Exception as e:
        conn.rollback()
        print(f"❌ 错误: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

# 使用示例
if __name__ == "__main__":
    screenshot_id = save_screenshot_to_stockscan(
        task_name="低位蓄势主升浪捕捉2",
        ts_code="000550.SZ",
        trade_date=date(2026, 4, 1),
        screenshot_path="/Users/zyzbot/Screenshots/20260401_000550_SZ.png",
        pdf_path="/Users/zyzbot/PDFs/20260401_000550_SZ.pdf"
    )
    
    if screenshot_id:
        print(f"记录成功保存，可在 StockScan 前端查看")
```

---

## 6. 错误处理

### 常见错误和解决方案

#### 错误 1: 找不到选股结果
```
❌ 未找到选股结果 - 方案: xxx, 股票: yyy, 日期: zzz
```

**原因**：
- 选股方案未运行或未命中此股票
- 方案名称拼写错误
- 交易日期不正确

**解决**：
1. 检查 StockScan 中是否已执行选股（历史选股记录页面）
2. 确认方案名称与 scheme.name 完全一致
3. 确认交易日期是 StockDB 中有数据的交易日

#### 错误 2: 唯一约束冲突
```
ERROR: duplicate key value violates unique constraint "unique_record"
```

**原因**：
- 同一个 result_detail_id + task_name + screenshot_date 已存在记录
- 重复调用了写入函数

**解决**：
1. 可以先删除旧记录再重新插入（如果需要覆盖）
2. 或者检查是否误重复调用了保存函数
3. 使用 `ON CONFLICT` 子句实现 upsert（更新或插入）

#### 错误 3: 数据库连接失败
```
ERROR: could not connect to server: Connection refused
```

**原因**：
- PostgreSQL 服务未启动
- 连接信息（IP/端口/用户/密码）错误
- 防火墙阻止

**解决**：
1. 确认 PostgreSQL 正在运行：`systemctl status postgresql`
2. 确认连接参数正确
3. 测试连接：`psql -h localhost -U stockscan_user -d stockscan`

---

## 7. 查询已保存的截图

### 查看某股票的所有截图

```sql
SELECT sr.id, sr.task_name, sr.screenshot_date, sr.screenshot_filename, sr.pdf_path, sr.created_at
FROM screenshot_records sr
WHERE sr.ts_code = '000550.SZ'
ORDER BY sr.created_at DESC;
```

### 查看某方案的所有截图

```sql
SELECT sr.id, sr.ts_code, sr.screenshot_date, sr.screenshot_filename, sr.created_at
FROM screenshot_records sr
WHERE sr.task_name = '低位蓄势主升浪捕捉2'
ORDER BY sr.screenshot_date DESC, sr.created_at DESC;
```

### 查看最近写入的 10 条

```sql
SELECT * FROM screenshot_records 
ORDER BY created_at DESC 
LIMIT 10;
```

---

## 8. 前端验证

StockScan 前端在 **历史选股记录** 页面会自动展示截图信息。

**访问方式**：
1. 打开 StockScan 前端（http://localhost:5173）
2. 进入 **历史选股记录** 页面
3. 选择任一选股结果
4. 在右侧结果表格中查看 **"截图"** 列
   - 有截图：显示 "N 张" 标签，点击查看详情
   - 无截图：显示 "无" 灰色标签

---

## 9. 技术支持

### 数据库验证脚本

```sql
-- 检查表是否存在且结构正确
\d screenshot_records

-- 检查索引是否创建
\di screenshot_records*

-- 查看所有已保存的记录数
SELECT COUNT(*) as total_records FROM screenshot_records;

-- 检查约束
SELECT constraint_name, constraint_type 
FROM information_schema.table_constraints 
WHERE table_name = 'screenshot_records';
```

### 常用查询命令

```bash
# 连接数据库
psql -h localhost -U stockscan_user -d stockscan

# 列出所有截图记录
SELECT * FROM screenshot_records LIMIT 20;

# 删除某条记录（如需要）
DELETE FROM screenshot_records WHERE id = 123;

# 删除某方案的所有截图
DELETE FROM screenshot_records WHERE task_name = '低位蓄势主升浪捕捉2';
```

---

## 10. 集成清单

完成集成前，请检查以下项目：

- [ ] PostgreSQL 服务正在运行
- [ ] stockscan 数据库存在
- [ ] stockscan_user 用户可用
- [ ] screenshot_records 表已创建（Alembic 迁移已运行）
- [ ] StockScan 后端正在运行
- [ ] StockView 代码已更新为使用 `save_screenshot_to_stockscan()` 函数
- [ ] 本地测试：手动调用函数，验证数据库写入成功
- [ ] 前端验证：在 StockScan 历史记录页面看到截图列
- [ ] 错误处理：确保异常情况被捕获并记录

---

**问题反馈**：如遇问题，请提供：
1. 错误日志完整内容
2. 使用的 SQL 语句或代码片段
3. 数据库连接参数（隐去密码）
4. StockView 和 StockScan 的版本信息
