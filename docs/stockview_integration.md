# StockView 截图集成指引

> 本文档说明如何在 StockView 中集成截图记录，通过 API 提交给 StockScan。

## 概述

StockView 在保存本地截图的同时，通过 HTTP API 向 StockScan 提交截图元数据，StockScan 自动写入数据库。这样两个应用独立运行，无需直接共享数据库凭证。

**核心流程**：
```
StockView 截图保存
    ↓
StockView 调用 API: POST /api/screening/screenshots
    ↓
StockScan 查询对应的选股结果
    ↓
StockScan 数据库写入截图记录
    ↓
StockScan 前端自动展示截图
```

---

## 1. API 端点说明

### 端点信息

```
方法: POST
URL: http://your-stockscan-host:8000/api/screening/screenshots
Content-Type: application/json
```

### 请求体（JSON）

```json
{
  "task_name": "低位蓄势主升浪捕捉2",
  "ts_code": "000550.SZ",
  "trade_date": "2026-04-01",
  "screenshot_filename": "/path/to/screenshot.png",
  "pdf_path": "/path/to/pdf.pdf"
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 | 示例 |
|------|------|------|------|------|
| `task_name` | string | ✅ | 选股方案名称（需与 StockScan 中的方案名完全一致） | `"低位蓄势主升浪捕捉2"` |
| `ts_code` | string | ✅ | 股票代码（标准格式） | `"000550.SZ"` 或 `"600000.SH"` |
| `trade_date` | date | ✅ | 选股交易日期（格式：YYYY-MM-DD） | `"2026-04-01"` |
| `screenshot_filename` | string | ✅ | 本地截图文件的路径或名称 | `"/Users/zyzbot/Screenshots/20260401_000550.png"` |
| `pdf_path` | string | ❌ | PDF 文件路径（可选，仅在生成了 PDF 时提供） | `"/Users/zyzbot/PDFs/20260401_000550.pdf"` |

### 响应示例

**成功（HTTP 200）**：
```json
{
  "id": 2,
  "message": "Screenshot record saved successfully",
  "result_detail_id": 7387
}
```

**失败 - 选股结果不存在（HTTP 404）**：
```json
{
  "detail": "Screening result not found: scheme='低位蓄势主升浪捕捉2', stock='000550.SZ', date=2026-04-01. Please ensure the screening has been run and found this stock."
}
```

**失败 - 重复记录（HTTP 409）**：
```json
{
  "detail": "Duplicate record: A screenshot record for this combination (scheme, stock, date) already exists. Please use a different date or delete the existing record."
}
```

**失败 - 服务器错误（HTTP 500）**：
```json
{
  "detail": "Database error: ..."
}
```

---

## 2. 集成方式

### Python 实现（推荐）

```python
import requests
from datetime import date

def save_screenshot_to_stockscan(
    stockscan_host: str = "http://localhost:8000",
    task_name: str = None,
    ts_code: str = None,
    trade_date: date = None,
    screenshot_path: str = None,
    pdf_path: str = None
) -> dict:
    """
    通过 API 向 StockScan 提交截图记录。

    Args:
        stockscan_host: StockScan 服务地址，默认本地
        task_name: 选股方案名称
        ts_code: 股票代码
        trade_date: 交易日期
        screenshot_path: 本地截图文件路径
        pdf_path: PDF 文件路径（可选）

    Returns:
        响应字典，包含 id、message 等

    Raises:
        requests.exceptions.RequestException: 网络错误
        ValueError: 参数验证失败
    """

    # 参数验证
    if not all([task_name, ts_code, trade_date, screenshot_path]):
        raise ValueError("task_name, ts_code, trade_date, screenshot_path are required")

    # 构建请求体
    payload = {
        "task_name": task_name,
        "ts_code": ts_code,
        "trade_date": trade_date.isoformat() if isinstance(trade_date, date) else str(trade_date),
        "screenshot_filename": screenshot_path,
        "pdf_path": pdf_path
    }

    # 发送 API 请求
    url = f"{stockscan_host}/api/screening/screenshots"
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()  # 抛出 HTTP 错误
        return response.json()
    except requests.exceptions.Timeout:
        return {"error": f"Request timeout: StockScan at {stockscan_host} not responding"}
    except requests.exceptions.ConnectionError:
        return {"error": f"Connection error: Unable to reach StockScan at {stockscan_host}"}
    except requests.exceptions.HTTPError as e:
        return {"error": f"HTTP {response.status_code}: {response.text}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


# 使用示例
if __name__ == "__main__":
    from datetime import date

    result = save_screenshot_to_stockscan(
        stockscan_host="http://localhost:8000",
        task_name="低位蓄势主升浪捕捉2",
        ts_code="000550.SZ",
        trade_date=date(2026, 4, 1),
        screenshot_path="/Users/zyzbot/Screenshots/20260401_000550_SZ.png",
        pdf_path="/Users/zyzbot/PDFs/20260401_000550_SZ.pdf"
    )

    if "error" in result:
        print(f"❌ {result['error']}")
    else:
        print(f"✅ 成功: ID={result['id']}, message={result['message']}")
```

### Node.js 实现

```javascript
const axios = require('axios');

async function saveScreenshotToStockScan(config) {
  const {
    stockscanHost = 'http://localhost:8000',
    taskName,
    tsCode,
    tradeDate,
    screenshotPath,
    pdfPath = null
  } = config;

  // 参数验证
  if (!taskName || !tsCode || !tradeDate || !screenshotPath) {
    throw new Error('taskName, tsCode, tradeDate, screenshotPath are required');
  }

  const payload = {
    task_name: taskName,
    ts_code: tsCode,
    trade_date: tradeDate,  // 格式: "2026-04-01"
    screenshot_filename: screenshotPath,
    pdf_path: pdfPath
  };

  try {
    const response = await axios.post(
      `${stockscanHost}/api/screening/screenshots`,
      payload,
      { headers: { 'Content-Type': 'application/json' }, timeout: 10000 }
    );
    return { success: true, data: response.data };
  } catch (error) {
    if (error.response) {
      return { 
        success: false, 
        error: `HTTP ${error.response.status}: ${error.response.data?.detail || error.message}` 
      };
    } else if (error.code === 'ECONNREFUSED') {
      return { success: false, error: `Unable to reach StockScan at ${stockscanHost}` };
    } else {
      return { success: false, error: error.message };
    }
  }
}

// 使用示例
(async () => {
  const result = await saveScreenshotToStockScan({
    stockscanHost: 'http://localhost:8000',
    taskName: '低位蓄势主升浪捕捉2',
    tsCode: '000550.SZ',
    tradeDate: '2026-04-01',
    screenshotPath: '/path/to/screenshot.png',
    pdfPath: '/path/to/pdf.pdf'
  });

  if (result.success) {
    console.log(`✅ 成功: ID=${result.data.id}`);
  } else {
    console.log(`❌ ${result.error}`);
  }
})();
```

### cURL 示例

```bash
curl -X POST http://localhost:8000/api/screening/screenshots \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "低位蓄势主升浪捕捉2",
    "ts_code": "000550.SZ",
    "trade_date": "2026-04-01",
    "screenshot_filename": "/path/to/screenshot.png",
    "pdf_path": "/path/to/pdf.pdf"
  }'
```

---

## 3. 错误处理和调试

### 常见错误

#### 404 - 选股结果不存在

```json
{
  "detail": "Screening result not found: scheme='xxx', stock='yyy', date=zzz"
}
```

**原因**：
- StockScan 中未执行过此选股方案
- 选股方案未命中此股票
- 方案名称拼写错误
- 交易日期不正确

**解决**：
1. 在 StockScan 前端确认选股结果存在（历史选股记录页面）
2. 确认方案名称与 StockScan 中的完全一致
3. 确认交易日期正确

#### 409 - 重复记录

```json
{
  "detail": "Duplicate record: A screenshot record for this combination..."
}
```

**原因**：
- 同一个方案+股票+日期的截图记录已存在
- 重复调用了 API

**解决**：
1. 先删除旧记录（使用 StockScan 前端或数据库）
2. 或改为使用不同的日期

#### 503/连接超时

**原因**：
- StockScan 服务未启动
- 网络连接问题
- 防火墙阻止

**解决**：
1. 确认 StockScan 后端正在运行
2. 检查网络连接和防火墙规则
3. 确认 StockScan 地址正确

### 调试建议

```python
# Python 中打印完整的请求和响应
import requests
import json

response = requests.post(
    'http://localhost:8000/api/screening/screenshots',
    json=payload,
    headers={'Content-Type': 'application/json'}
)

print(f"Status Code: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
```

---

## 4. 前端验证

StockScan 前端会自动展示已保存的截图记录。

**查看方式**：
1. 打开 StockScan 前端（http://your-stockscan-host:5173）
2. 进入 **历史选股记录** 页面
3. 选择任一选股结果，右侧展开详情
4. 在结果表格中查看 **"截图"** 列
   - 有截图：显示 "N 张" 蓝色标签，点击查看详情
   - 无截图：显示 "无" 灰色标签

---

## 5. 集成清单

完成集成前，请检查：

- [ ] 确认 StockScan 后端正在运行（http://host:8000/api/schemes 可访问）
- [ ] StockScan 中已执行所需的选股方案
- [ ] 选股方案已找到目标股票
- [ ] StockView 代码已更新，使用 `save_screenshot_to_stockscan()` 或 `saveScreenshotToStockScan()`
- [ ] 测试：手动调用 API，确保返回 HTTP 200 和正确的 ID
- [ ] 前端验证：在 StockScan 历史记录页面看到截图列和记录数
- [ ] 错误处理：异常情况被妥善捕获并记录日志

---

## 6. 配置参考

### 本地开发环境

```
StockScan Host: http://localhost:8000
Frontend: http://localhost:5173
Database: localhost:5432 (StockScan 内部使用)
```

### 远程部署环境

```
StockScan Host: http://your.domain.com:8000
或
StockScan Host: http://192.168.x.x:8000
```

---

## 7. 常见集成模式

### 模式 1：截图保存后立即上报

```python
# StockView 主流程
def save_screenshot(ts_code, screenshot_path, pdf_path=None):
    # 1. 本地保存截图
    save_to_local_storage(screenshot_path)
    
    # 2. 获取当前任务信息
    task_name = get_current_task_name()  # 当前正在执行的选股任务
    trade_date = get_current_trade_date()  # 当前选股的交易日
    
    # 3. 上报到 StockScan
    result = save_screenshot_to_stockscan(
        task_name=task_name,
        ts_code=ts_code,
        trade_date=trade_date,
        screenshot_path=screenshot_path,
        pdf_path=pdf_path
    )
    
    if "error" in result:
        log_warning(f"Failed to save screenshot metadata: {result['error']}")
        # 继续执行，不中断流程
    else:
        log_info(f"Screenshot metadata saved: ID={result['id']}")
```

### 模式 2：批量上报

```python
# 集合多个截图后统一上报
screenshots_to_upload = []

def collect_screenshot(ts_code, screenshot_path, pdf_path=None):
    screenshots_to_upload.append({
        'ts_code': ts_code,
        'screenshot_path': screenshot_path,
        'pdf_path': pdf_path
    })

def flush_screenshots(task_name, trade_date):
    """批量上报所有收集的截图"""
    for item in screenshots_to_upload:
        result = save_screenshot_to_stockscan(
            task_name=task_name,
            ts_code=item['ts_code'],
            trade_date=trade_date,
            screenshot_path=item['screenshot_path'],
            pdf_path=item['pdf_path']
        )
        if "error" not in result:
            log_info(f"✅ {item['ts_code']}: {result['id']}")
        else:
            log_error(f"❌ {item['ts_code']}: {result['error']}")
    
    screenshots_to_upload.clear()
```

---

## 8. API 文档

完整的 Swagger 文档可在以下地址查看：

```
http://your-stockscan-host:8000/docs
```

在 Swagger UI 中搜索 "screenshots" 可查看完整的请求/响应格式。

---

## 9. 故障排查

### 快速诊断脚本

**Python**：
```python
import requests

def test_stockscan_connection(host="http://localhost:8000"):
    try:
        # 测试后端是否在线
        response = requests.get(f"{host}/api/schemes", timeout=5)
        print(f"✅ StockScan 后端在线（HTTP {response.status_code}）")
        
        # 测试 API 是否可用
        response = requests.post(
            f"{host}/api/screening/screenshots",
            json={
                "task_name": "test",
                "ts_code": "000001.SZ",
                "trade_date": "2026-01-01",
                "screenshot_filename": "test.png"
            },
            timeout=5
        )
        if response.status_code == 404:
            print(f"✅ API 端点存在且正常工作（预期返回 404：未找到选股结果）")
        else:
            print(f"⚠️ API 返回 {response.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"❌ 无法连接 {host} - 确保 StockScan 后端正在运行")
    except Exception as e:
        print(f"❌ 错误: {e}")

test_stockscan_connection()
```

---

## 10. 支持和反馈

遇到问题时，请提供：
1. StockView 日志（截图提交的请求和响应）
2. StockScan 后端日志（/tmp/uvicorn.log）
3. 使用的参数值（不包括密钥信息）
4. 完整的错误信息

---

**最后更新**：2026-04-01
**API 版本**：1.0
**兼容版本**：StockScan v1.0 及以上
