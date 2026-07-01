# NeoTrade3 v1 用户操作手册

**版本**: v1.0.0  
**更新日期**: 2026-06-06

---

## 1. 系统简介

NeoTrade3 是一个面向低频交易的量化选股系统，核心目标是在市场条件符合时，筛选出未来 20-60 个交易日确定性在 80% 以上的股票。

### 核心能力

- **市场情绪/升浪识别（可选）**: 支持市场情绪打分与升浪阶段识别（配置可开关）
- **板块/概念聚焦**: 输出人气板块（行业板块口径）与概念主线热度（同花顺概念口径）
- **个股筛选与信号**: 结合结构形态、趋势/量价与基本面阈值过滤，生成可交易候选
- **低频回测报告**: 支持生成回测报告列表，并下载 PDF/JSON 作为交付与复验依据

---

## 2. 快速开始

### 2.1 启动系统

```bash
# 1. 启动 API 服务（端口 18030）
./.venv/bin/python -m apps.api.main --host 0.0.0.0 --port 18030

# 2. 启动当前正式前端（端口 4173）
cd neotrade3-dashboard && npm run dev -- --host 0.0.0.0 --port 4173

# 3. 打开浏览器访问
http://localhost:4173
```

### 2.2 首次运行

1. 打开 Dashboard 首页
2. 确认"今日分析总览"卡片显示数据
3. 点击"运行今日分析"按钮生成当日矩阵
4. 查看"高确定性候选"和"交易信号"卡片

---

## 3. 核心功能使用

### 3.1 查看今日分析（首页）

首页展示 5 个核心分析卡片：

| 卡片 | 说明 | 操作 |
|------|------|------|
| **市场阶段** | 当前市场处于牛市/熊市/震荡/过渡 | 点击展开详情 |
| **高确定性候选** | 确定性 ≥80% 的股票数量 | 点击跳转到量化交易页 |
| **交易信号** | A/B/C 等级信号数量及 Top 3 | 点击跳转到信号详情 |
| **Top 板块** | RPS 评分最高的 5 个板块 | 实时更新 |
| **筛选器命中** | 各筛选器命中股票总数 | 点击跳转到筛选器页 |

**问题与告警**: 折叠区域显示当前运行问题，点击展开查看详情和建议。

### 3.2 运行分析任务

**方式一: Dashboard 一键运行**

1. 在首页点击"运行今日分析"按钮
2. 等待状态变为"运行中..."
3. 约 10-30 秒后刷新页面查看最新结果

**方式二: API 调用**

```bash
# 运行因子矩阵
curl -X POST "http://localhost:18030/api/factor-matrix/daily/run" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"target_date": "2025-05-23"}'

# 运行量化实验室
curl -X POST "http://localhost:18030/api/labs/run" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"target_date": "2025-05-23", "lab_id": "quant_trading_lab"}'
```

### 3.3 查看交易信号

1. 在首页"交易信号"卡片查看信号统计
2. 点击卡片跳转到"量化交易"页面
3. 查看完整信号列表，包含:
   - 股票代码、名称
   - 信号等级 (A/B/C)
   - 入场价、止损价、止盈价
   - 预期收益区间

### 3.4 使用筛选器

1. 进入"筛选器"页面
2. 选择筛选器类型（杯柄、老鸭头等）
3. 调整参数（如需要）
4. 点击运行
5. 查看命中结果，支持 CSV 导出

**CSV 导出**:
```bash
curl "http://localhost:18030/api/screeners/run/cup_handle/2025-05-23/export.csv" \
  -H "X-API-Key: your-api-key" \
  -o cup_handle_results.csv
```

---

## 4. 开发者模式

### 4.1 开启方式

**方式一: URL 参数**
```
http://localhost:18031/?dev=1
```

**方式二: 设置面板**
1. 进入"系统设置"页面
2. 勾选"开发者模式"复选框

### 4.2 开发者模式功能

开启后可查看：
- 运维指标（运行通过/失败统计）
- 原始数据 payload
- 路线图、迁移台账、配置契约等内部页面

---

## 5. API 参考

### 5.1 获取 API 文档

```bash
curl http://localhost:18030/api
```

返回所有可用端点列表。

### 5.2 常用端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/trading-day?date=YYYY-MM-DD` | GET | 查询是否为交易日 |
| `/api/factor-matrix/daily?date=YYYY-MM-DD` | GET | 获取因子矩阵 |
| `/api/market-phase?date=YYYY-MM-DD` | GET | 获取市场阶段 |
| `/api/signals?codes=xxx,yyy&date=YYYY-MM-DD` | GET | 获取交易信号 |
| `/api/labs/runs/<date>/<lab_id>` | GET | 获取实验室结果 |
| `/api/sectors/hot?date=YYYY-MM-DD` | GET | 获取当日热门板块与龙头/中军/跟随结构 |
| `/api/concepts/mainline?date=YYYY-MM-DD` | GET | 获取概念主线热度榜 |
| `/api/concepts/mainline/detail?concept_code=...&date=YYYY-MM-DD` | GET | 获取概念主线明细与成分表现 |
| `/api/ashare/midcap/audit?date=YYYY-MM-DD` | GET | A 股 200—500 亿市值标的审计（可用池与剔除原因） |
| `/api/lowfreq/backtest/reports?limit=N` | GET | 获取低频回测报告列表 |
| `/api/lowfreq/backtest/reports/<report_id>.pdf` | GET | 下载回测报告 PDF |
| `/api/lowfreq/backtest/reports/<report_id>.json` | GET | 下载回测报告 JSON（审计/复验） |

说明：
- 所有端点同时支持 `/api/v1/...` 前缀（例如 `/api/v1/sectors/hot`）。
- `/api` 返回的端点列表以系统内置文档为准；若需完整清单，以 `apps/api/router.py` 的路由分发逻辑为准。

### 5.3 错误处理

所有错误返回统一格式：
```json
{
  "error": {
    "code": "error_code",
    "message": "错误描述",
    "details": { ... }
  }
}
```

---

## 6. 常见问题

### Q1: 首页显示"未生成"怎么办？

**原因**: 当日因子矩阵尚未运行  
**解决**: 点击"运行今日分析"按钮，等待 10-30 秒后刷新页面

### Q2: 交易信号为"无信号"怎么办？

**原因**: 当前市场阶段可能不适合交易，或候选股票未达信号阈值  
**解决**: 检查"市场阶段"卡片，如为"熊市"建议观望

### Q3: 如何导出筛选器结果？

**解决**: 使用 CSV 导出端点：
```bash
curl "http://localhost:18030/api/screeners/run/<screener_id>/<date>/export.csv" \
  -H "X-API-Key: your-api-key"
```

### Q4: 如何查看运行日志？

**解决**: 进入"每日任务运行"页面（需开启开发者模式），查看各 task 的执行状态和日志

### Q5: 系统提示"数据未就绪"怎么办？

**原因**: 数据库中缺少必要的行情数据  
**解决**: 
1. 进入"数据主链"页面
2. 点击"同步行情数据"
3. 等待同步完成后重试

### Q6: 为什么无法直接把报告写到 ~/Downloads？

**原因**: 当前运行环境对 `~/Downloads` 目录写入存在限制（沙箱/白名单）  
**解决**: 先在项目目录生成报告文件（例如回测报告下载、或 `var/tmp/...` 下的研究报告 PDF），再用本机终端或 Finder 手动拷贝到 Downloads。

---

## 7. 系统限制

| 限制项 | 说明 | 建议 |
|--------|------|------|
| ROE 数据覆盖 | 仅 0.06% 股票有数据 | 使用 PE/PB 替代，或接入外部财务数据源 |
| 定时任务 | 当前仅支持手动触发 | 使用系统 cron 或 APScheduler 扩展 |
| 政策/新闻数据 | 当前未接入 | 参考 `docs/research/external_data_sources.md` 扩展 |

---

## 8. 联系与支持

- **项目地址**: https://github.com/your-org/neotrade3
- **问题反馈**: 在 GitHub Issues 中提交
- **文档更新**: 本手册随版本更新，请查看最新版本

---

**附: 数据流示意图**

```
行情数据 → 数据主链 → 因子矩阵 → 量化实验室 → 交易信号
                ↓              ↓              ↓
           板块轮动      高确定性候选      策略池
```
