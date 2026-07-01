# NeoTrade3 详细交接文档 (2026-05-30)

**目标读者**: 零项目背景的新工程师，需要能够运行系统、调试问题、安全地继续开发。

**文档目标**: 提供从环境搭建到生产部署的完整指南，确保任何人都能独立接手项目。

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统架构](#2-系统架构)
3. [环境准备](#3-环境准备)
4. [快速启动指南](#4-快速启动指南)
5. [代码结构详解](#5-代码结构详解)
6. [API 参考](#6-api-参考)
7. [Dashboard 使用指南](#7-dashboard-使用指南)
8. [故障排查手册](#8-故障排查手册)
9. [开发工作流](#9-开发工作流)
10. [部署指南](#10-部署指南)
11. [新功能开发](#11-新功能开发)

---

## 1. 项目概述

### 1.1 什么是 NeoTrade3

NeoTrade3 是一个基于 Python 的量化股票分析和运营控制台，包含：

- **API 服务器** (端口 18030): 基于 Python `http.server` 的轻量级 HTTP API，提供 JSON 数据和二进制下载（如 PDF）
- **Dashboard V2** (端口 8765): 原有的 Dashboard，基于原生 JavaScript
- **Dashboard V3/React** (端口 5174): **新开发的 React + Vite + Tailwind CSS Dashboard** ⭐
- **核心库** (`neotrade3/`): 业务逻辑（分析、筛选器、编排、数据控制等）
- **SQLite 数据库**: `var/db/stock_data.db` 运行时数据库

### 1.2 主要功能模块

| 模块 | 说明 | 对应页面 |
|------|------|----------|
| 今日总览 | 系统状态、数据控制状态、筛选器列表 | Overview |
| 低频交易 | 市场阶段、热门板块、持仓监控、候选池、回测 | Lowfreq |
| 筛选器 | 筛选器管理、运行记录、一键运行 | Screeners |
| 单股核验 | 股票查询、信号分析 | StockCheck |

### 1.3 技术栈

**后端:**
- Python 3.9+
- SQLite 数据库
- 自定义 HTTP 服务器 (基于 `http.server`)

**前端 (V3/React):**
- React 18
- Vite (构建工具)
- Tailwind CSS
- React Router (路由)
- Lucide React (图标)

---

## 2. 系统架构

### 2.1 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        浏览器                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Dashboard   │  │ Dashboard   │  │ 外部工具 (curl/脚本) │  │
│  │ V2 (8765)   │  │ V3 (5174)   │  │                     │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
└─────────┼────────────────┼────────────────────┼─────────────┘
          │                │                    │
          └────────────────┴────────────────────┘
                           │
                    ┌──────▼──────┐
                    │ API Server  │
                    │ (18030)     │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼─────┐ ┌───▼────┐ ┌────▼─────┐
        │ SQLite DB │ │ Config │ │ Ledgers  │
        │           │ │ Files  │ │          │
        └───────────┘ └────────┘ └──────────┘
```

### 2.2 数据流

1. **数据采集** (Capture): 从数据源拉取原始数据
2. **数据组合** (Compose): 验证、清洗、计算因子
3. **数据发布** (Publish): 写入官方存储

---

## 3. 环境准备

### 3.1 系统要求

- **操作系统**: macOS (推荐), Linux, Windows (未充分测试)
- **Python**: >= 3.9
- **Node.js**: >= 18 (用于 React Dashboard 开发)
- **curl**: 用于健康检查

### 3.2 项目根目录

```
/Users/mac/NeoTrade3/  (或你的实际路径)
├── apps/
│   ├── api/              # API 服务器
│   └── dashboard/        # Dashboard V2 (原生 JS)
├── neotrade3/            # 核心库
├── config/               # 配置文件
├── var/                  # 运行时数据
│   ├── db/               # SQLite 数据库
│   ├── ledgers/          # 账本
│   └── artifacts/        # 生成的文件
├── neotrade3-dashboard/  # Dashboard V3 (React) ⭐
│   ├── src/              # 源代码
│   ├── dist/             # 构建输出
│   └── package.json      # 依赖
├── dashboard_server.py   # 静态站点服务 + API 反向代理（服务 dist/）
└── HandOver20260530_Detailed.md   # 本文件
```

### 3.3 Python 环境设置

```bash
# 1. 进入项目目录
cd /Users/mac/NeoTrade3

# 2. 创建虚拟环境
python3 -m venv .venv

# 3. 激活虚拟环境
source .venv/bin/activate  # macOS/Linux
# 或 .venv\Scripts\activate  # Windows

# 4. 升级 pip
python -m pip install -U pip

# 5. 安装项目依赖
pip install -e .

# 6. (可选) 安装开发依赖
pip install -e ".[dev]"
```

### 3.4 Node.js 环境设置 (用于 React Dashboard)

```bash
# 1. 进入 React Dashboard 目录
cd neotrade3-dashboard

# 2. 安装依赖
npm install

# 3. 开发模式运行
npm run dev

# 4. 生产构建
npm run build
```

---

## 4. 快速启动指南

### 4.1 启动所有服务 (推荐)

推荐方式：API + React 构建产物 + 内置静态服务（同一台机器/局域网可用）。

### 4.2 手动启动 (分步)

#### 步骤 1: 启动 API 服务器

```bash
# 终端 1
cd /Users/mac/NeoTrade3
source .venv/bin/activate
python -m apps.api.main --host 0.0.0.0 --port 18030
```

验证：
```bash
curl -sS http://127.0.0.1:18030/healthz | python -m json.tool
# 预期输出: {"status": "ok"}
```

#### 步骤 2: 启动 Dashboard V2 (可选)

```bash
# 终端 2
cd /Users/mac/NeoTrade3
source .venv/bin/activate
python -m apps.dashboard.main --host 0.0.0.0 --port 18031 --api-base-url http://127.0.0.1:18030
```

访问: http://127.0.0.1:18031/

#### 步骤 3: 启动 Dashboard V3/React (推荐)

**编辑前端源码（热更新，仅用于开发）:**
```bash
# 终端 3
cd /Users/mac/NeoTrade3/neotrade3-dashboard
npm run dev
```
访问: http://localhost:5173/

**运行构建后的 Dashboard（推荐日常使用）:**
```bash
# 终端 3
cd /Users/mac/NeoTrade3/neotrade3-dashboard
npm run build

# 终端 4
cd /Users/mac/NeoTrade3
source .venv/bin/activate
python dashboard_server.py
```
访问: http://localhost:5174/

### 4.3 服务端口总结

| 服务 | 端口 | 访问地址 | 说明 |
|------|------|----------|------|
| API | 18030 | http://127.0.0.1:18030 | 必须启动 |
| Dashboard V2 | 18031 | http://127.0.0.1:18031 | 旧版 |
| Dashboard V3 (Dev) | 5173 | http://localhost:5173 | React 开发模式 |
| Dashboard V3 (Build) | 5174 | http://localhost:5174 | `dashboard_server.py` 服务 `neotrade3-dashboard/dist` 并反向代理 API |
| Dashboard V2 (已有) | 8765 | http://localhost:8765 | 已有服务 |

---

## 5. 代码结构详解

### 5.1 API 服务器 (`apps/api/`)

```
apps/api/
├── main.py          # 入口 + 服务实现
├── router.py        # 路由分发
├── service.py       # 业务逻辑
├── http.py          # HTTP 处理器 + CORS
└── utils.py         # 工具函数
```

**关键文件:**

- `router.py`: URL 路由映射，定义所有 API 端点
- `main.py`: 包含 `trading_day_view()` 等视图函数
- `http.py`: CORS 配置，允许的 origin 列表

### 5.2 React Dashboard (`neotrade3-dashboard/`)

```
neotrade3-dashboard/
├── src/
│   ├── pages/           # 页面组件
│   │   ├── Overview.jsx      # 今日总览
│   │   ├── Lowfreq.jsx       # 低频交易
│   │   ├── Screeners.jsx     # 筛选器
│   │   └── StockCheck.jsx    # 单股核验
│   ├── components/      # 共享组件
│   │   └── DateSelector.jsx  # 日期选择器
│   ├── services/        # API 服务
│   │   └── api.js
│   ├── context/         # 全局状态
│   │   └── AppContext.jsx
│   ├── App.jsx          # 主应用
│   └── main.jsx         # 入口
├── dist/                # 生产构建输出
├── package.json         # 依赖配置
└── vite.config.js       # Vite 配置
```

### 5.3 核心库 (`neotrade3/`)

```
neotrade3/
├── analysis/            # 分析模块
├── screeners/           # 筛选器
├── data_control/        # 数据控制
├── orchestration/       # 编排
├── labs/                # 实验室
└── issue_center/        # 问题中心
```

### 5.4 配置文件 (`config/`)

```
config/
├── screeners/           # 筛选器定义
│   └── *.json
├── labs/
│   └── labs_registry.json
└── data_control/
    └── source_registry.json
```

---

## 6. API 参考

### 6.1 健康检查

```bash
GET /healthz
```

响应:
```json
{"status": "ok"}
```

### 6.2 交易日检查

```bash
GET /api/trading-day?date=2026-05-30
```

响应:
```json
{
  "target_date": "2026-05-30",
  "is_trading_day": false,
  "nearest_trading_day": "2026-05-28",
  "max_trading_day": "2026-05-28"
}
```

### 6.3 今日总览

```bash
GET /api/bootstrap-summary?date=2026-05-28&source=live
GET /api/data-control?date=2026-05-28&source=live
GET /api/screeners?date=2026-05-28
```

### 6.4 低频交易

```bash
GET /api/market-phase?date=2026-05-28&source=live
GET /api/sectors/hot
GET /api/lowfreq/candidates?date=2026-05-28&source=live
GET /api/lowfreq/backtest?date=2026-05-28&source=live
```

### 6.5 筛选器

```bash
GET /api/screeners?date=2026-05-28
GET /api/screeners/runs?date=2026-05-28
POST /api/screeners/run
```

### 6.6 单股核验

```bash
GET /api/stocks/lookup?code=600000&date=2026-05-28&source=live
```

---

## 7. Dashboard 使用指南

### 7.1 今日总览页面

**功能:**
- 显示计划任务数、问题案例数、学习候选数
- 数据控制状态 (采集 → 组合 → 发布)
- 筛选器列表

**日期选择:**
- 选择非交易日时会显示警告
- 提供「切换到最近交易日」按钮

### 7.2 低频交易页面

**标签页:**
1. **今日快照**: 市场阶段、热门板块
2. **持仓监控**: 投资组合、持仓明细
3. **候选池**: 符合条件的候选股票
4. **回测报告**: 收益指标、交易记录

### 7.3 筛选器页面

**功能:**
- 查看所有筛选器
- 一键运行全部筛选器
- 查看运行记录
- 下载结果 (CSV)

### 7.4 单股核验页面

**功能:**
- 输入股票代码查询
- 显示基本信息、交易信号
- 显示命中的筛选器

---

## 8. 故障排查手册

### 8.1 Dashboard 无法加载

**症状:** 页面空白或一直显示加载中

**排查步骤:**

1. **检查 API 服务器是否运行**
   ```bash
   curl http://127.0.0.1:18030/healthz
   ```

2. **检查 Dashboard 服务器是否运行**
   ```bash
   curl http://localhost:5174/
   ```

3. **检查浏览器控制台错误**
   - 打开 DevTools (F12)
   - 查看 Console 和 Network 标签

4. **清除浏览器缓存**
   - macOS: Cmd+Shift+R
   - Windows: Ctrl+Shift+R

### 8.2 API 请求失败

**症状:** 数据不加载，Network 显示红色错误

**排查步骤:**

1. **直接测试 API**
   ```bash
   curl -v http://127.0.0.1:18030/api/trading-day?date=2026-05-28
   ```

2. **检查 CORS 错误**
   - 确保使用 `localhost` 或 `127.0.0.1` 访问
   - 检查 `apps/api/http.py` 中的 CORS 配置

3. **检查端口占用**
   ```bash
   lsof -i:18030  # API
   lsof -i:5174   # Dashboard
   ```

### 8.3 数据不更新

**症状:** 切换日期后数据不变

**解决方案:**
1. 点击「刷新」按钮
2. 检查浏览器 Network 请求是否发出
3. 检查 API 响应是否正确

### 8.4 构建失败

**症状:** `npm run build` 报错

**解决方案:**
```bash
cd neotrade3-dashboard
rm -rf node_modules package-lock.json
npm install
npm run build
```

---

## 9. 开发工作流

### 9.1 修改 React Dashboard

```bash
cd neotrade3-dashboard

# 开发模式 (热重载)
npm run dev

# 构建版本（输出到 neotrade3-dashboard/dist）
npm run build
```

### 9.2 修改 API

```bash
# 编辑 apps/api/main.py 或 router.py
# 重启 API 服务器
```

### 9.3 添加新 API 端点

1. 在 `router.py` 中添加路由
2. 在 `main.py` 或 `service.py` 中实现逻辑
3. 更新前端调用

### 9.4 添加新页面

1. 在 `neotrade3-dashboard/src/pages/` 创建组件
2. 在 `App.jsx` 中添加路由
3. 在侧边栏添加导航链接

---

## 10. 部署指南

### 10.1 生产构建

```bash
cd neotrade3-dashboard
npm run build
```

### 10.2 运行构建后的 Dashboard（内置静态服务 + API 代理）

```bash
cd /Users/mac/NeoTrade3
source .venv/bin/activate
python dashboard_server.py
```

### 10.3 使用 Cpolar 暴露到公网

```bash
# 安装 cpolar
curl -L https://www.cpolar.com/static/downloads/install-release-cpolar.sh | sudo bash

# 认证
cpolar authtoken <your_token>

# 创建隧道
cpolar http 5174
```

---

## 11. 新功能开发

### 11.1 添加新的 API 端点

**示例: 添加 `/api/my-feature`**

1. **router.py:**
```python
elif parsed.path == "/api/my-feature":
    return self._service.my_feature_view(**kwargs)
```

2. **main.py:**
```python
def my_feature_view(self, **kwargs):
    return {"status": "ok", "data": ...}
```

3. **前端调用:**
```javascript
fetch('/api/my-feature?date=2026-05-28')
```

### 11.2 添加新的 Dashboard 页面

**示例: 添加「设置」页面**

1. **创建页面:** `src/pages/Settings.jsx`
2. **添加路由:** `App.jsx`
3. **添加导航:** 侧边栏

### 11.3 修改数据控制流程

数据控制三个阶段:
1. **Capture (采集)**: 拉取原始数据
2. **Compose (组合)**: 验证、清洗、计算
3. **Publish (发布)**: 写入官方存储

修改文件: `neotrade3/data_control/`

---

## 附录

### A. 常用命令

```bash
# 启动 API
python -m apps.api.main --host 0.0.0.0 --port 18030

# 启动 Dashboard V3（服务 dist 并反向代理 /api）
python dashboard_server.py

# 启动 Dashboard V3 (Dev)
cd neotrade3-dashboard && npm run dev

# 构建 Dashboard
npm run build

# 检查端口
lsof -i:18030
lsof -i:5174

# 测试 API
curl http://127.0.0.1:18030/healthz
```

### B. 环境变量

```bash
export NEOTRADE3_API_KEY="your-api-key"
export NEOTRADE3_STOCK_DB_V2_PATH="/path/to/v2.db"
```

### C. 参考文档

- [HANDOVER_DETAILED.md](HANDOVER_DETAILED.md)
- [docs/operations/bootstrap_runbook.md](docs/operations/bootstrap_runbook.md)
- [docs/operations/bootstrap_notes.md](docs/operations/bootstrap_notes.md)
- [PROJECT_STATUS.md](PROJECT_STATUS.md)

---

**最后更新**: 2026-05-31
**作者**: AI Assistant
**版本**: 2.0 (包含 React Dashboard)
