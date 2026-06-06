# NeoTrade3 项目详细 Handover 文档

## 1. 项目架构总览

```
NeoTrade3/
├── apps/
│   ├── api/                    # REST API 服务 (端口 18030)
│   │   └── main.py             # 主入口，~8200行，基于 http.server
│   ├── dashboard/              # 前端仪表盘 (端口 18031)
│   │   ├── main.py             # HTML生成 + 静态文件服务
│   │   └── static/
│   │       ├── dashboard.css   # 样式文件
│   │       └── dashboard.js    # 交互逻辑
│   └── worker/                 # 后台任务执行器
├── neotrade3/                  # 核心业务包
│   ├── ml/                     # 机器学习模块
│   │   ├── trainer.py          # 主训练器
│   │   └── autore/             # autoretch 自动优化框架
│   │       ├── train.py        # 可配置训练脚本
│   │       ├── config.py       # 配置和工具
│   │       └── program.md      # 研究指令
│   ├── screeners/              # 筛选器引擎
│   ├── analysis/               # 分析引擎
│   └── data_control/           # 数据管线
├── config/                     # 配置文件
│   └── screeners/              # 筛选器注册表
├── var/                        # 运行时数据
│   ├── db/stock_data.db        # SQLite 数据库
│   ├── ledgers/                # 运行台账
│   └── artifacts/              # 运行产物
└── pyproject.toml              # 项目配置
```

## 2. 环境配置

### 2.1 虚拟环境（已配置）
```bash
cd /path/to/NeoTrade3
source venv/bin/activate
```

### 2.2 依赖安装
```bash
# 已在虚拟环境中安装
pip install -e .
```

### 2.3 Python 版本
- 要求：Python 3.10+
- 已修改 pyproject.toml 支持 3.10

## 3. 服务启动（详细步骤）

### 3.1 启动 API 服务
```bash
cd /path/to/NeoTrade3
source venv/bin/activate

python apps/api/main.py --host 0.0.0.0 --port 18030
```

**验证**：
```bash
curl http://localhost:18030/healthz
# 预期输出: {"status": "ok", ...}
```

### 3.2 启动 Dashboard 服务
```bash
cd /path/to/NeoTrade3
source venv/bin/activate

python apps/dashboard/main.py \
  --host 0.0.0.0 \
  --port 18031 \
  --api-base-url http://localhost:18030
```

**验证**：
```bash
curl http://localhost:18031/ | head -5
# 预期输出: <!doctype html>...
```

### 3.3 访问地址
- 本地: `http://localhost:18031/`
- 网络: `http://<IP>:18031/`

## 4. 前端功能验证清单

### 4.1 全局状态栏
- [ ] 显示"数据更新至：YYYY-MM-DD"
- [ ] 显示绿色/红色状态圆点
- [ ] 数据异常时显示红色警告

**API**: `GET /api/bootstrap-summary`, `GET /api/data-control`

### 4.2 热门板块展示
- [ ] 显示 Top 7 板块卡片
- [ ] 每个板块显示龙头/中军/跟随股
- [ ] 显示 20日/50日确定性评分
- [ ] 默认展开前 3 个板块

**API**: `GET /api/sector-rotation`, `GET /api/stock-tiering`

### 4.3 筛选器一键运行
- [ ] "一键运行全部"按钮醒目显示
- [ ] 点击后弹出确认对话框
- [ ] 运行状态实时反馈
- [ ] 结果支持折叠/展开
- [ ] CSV 下载按钮可用

**API**: `POST /api/screeners/bulk-run`, `GET /api/screeners/runs`

### 4.4 单股票查询增强
- [ ] 输入股票代码后显示所属板块
- [ ] 显示个股分层（龙头/中军/跟随）
- [ ] 显示 RPS 评分
- [ ] 显示命中的筛选器列表

**API**: `GET /api/stocks/lookup`, `GET /api/stock-tiering`, `GET /api/screeners/runs`

## 5. ML 模型使用

### 5.1 当前最优模型配置
```python
# neotrade3/ml/autore/train.py 中的默认配置
N_ESTIMATORS = 500
MAX_DEPTH = 15
MIN_SAMPLES_LEAF = 8
THRESHOLD_UP = 1.5
THRESHOLD_DOWN = -1.5
USE_RSI = False
USE_MACD = True
USE_BOLLINGER = True
USE_VOLATILITY_REGIME = True
USE_MARKET_BREADTH = True
USE_MONEY_FLOW = True
```

### 5.2 运行自动优化
```bash
cd /path/to/NeoTrade3
source venv/bin/activate

python run_autore.py 5
```

**输出**：
- `neotrade3/ml/autore/BASELINE.txt` - 当前最优分数
- `neotrade3/ml/autore/SUCCESS.md` - 成功实验记录
- `neotrade3/ml/autore/FAILED.md` - 失败实验记录

### 5.3 手动训练
```bash
python neotrade3/ml/autore/train.py
```

**输出**：
- `neotrade3/ml/autore/last_result.txt` - 最后一次结果
- `var/models/` - 保存的模型文件

## 6. 关键 API 端点

### 6.1 数据类
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/bootstrap-summary` | GET | 系统总览 |
| `/api/data-control` | GET | 数据管线状态 |
| `/api/sector-rotation` | GET | 板块轮动分析 |
| `/api/stock-tiering` | GET | 个股分层 |
| `/api/screeners` | GET | 筛选器列表 |
| `/api/screeners/runs` | GET | 筛选器运行记录 |
| `/api/stocks/lookup` | GET | 股票查询 |

### 6.2 操作类
| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/screeners/bulk-run` | POST | 批量运行筛选器 |
| `/api/screeners/run` | POST | 运行单个筛选器 |
| `/api/orchestration/run` | POST | 运行每日编排 |

## 7. 常见问题排查

### 7.1 端口被占用
```bash
# 查找占用 18030/18031 的进程
lsof -i :18030
lsof -i :18031

# 终止进程
kill -9 <PID>
```

### 7.2 数据库连接失败
```bash
# 检查数据库文件
ls -la var/db/stock_data.db

# 验证数据库
sqlite3 var/db/stock_data.db ".tables"
```

### 7.3 依赖缺失
```bash
source venv/bin/activate
pip install -e .
```

## 8. 文件修改记录

### 8.1 前端修改
| 文件 | 修改内容 | 行数变化 |
|------|---------|---------|
| `apps/dashboard/main.py` | 新增状态栏、板块展示、筛选器按钮、单股增强 | +~50 |
| `apps/dashboard/static/dashboard.css` | 新增状态栏、板块卡片、分层标签样式 | +~360 |
| `apps/dashboard/static/dashboard.js` | 新增 6 个渲染函数 + 控件绑定 | +~350 |

### 8.2 ML 修改
| 文件 | 修改内容 |
|------|---------|
| `neotrade3/ml/trainer.py` | 新增资金流向特征 |
| `neotrade3/ml/autore/train.py` | 新增资金流向特征开关 |
| `run_autore.py` | 新增组合优化假设 |

### 8.3 配置修改
| 文件 | 修改内容 |
|------|---------|
| `pyproject.toml` | Python 版本 3.11 -> 3.10 |

## 9. 下一步工作建议

### 高优先级
1. **验证前端功能**：在浏览器中逐一验证 4.1-4.4 的功能清单
2. **修复网络访问**：如果 localhost:18031 无法访问，检查防火墙或尝试 127.0.0.1:18031

### 中优先级
3. **继续 ML 优化**：运行 `run_autore.py 10` 探索更多参数组合
4. **资金流向数据**：接入真实数据源替换模拟计算

### 低优先级
5. **回测框架**：基于 ML 预测构建完整回测
6. **单元测试**：为新增功能添加测试

## 10. 联系信息

- 项目路径：`/sessions/6a114a44ee100de4314469d7/workspace/NeoTrade3`
- 虚拟环境：`NeoTrade3/venv/`
- Handover 文档：`NeoTrade3/HANDOVER_DETAILED.md`

---

**生成时间**：2026-05-25
**版本**：v2.0
