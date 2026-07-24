# NeoTrade3 Repo Tree

## 一级目录语义（仓库根目录）

### SSOT（默认不清理）

- `apps/`：运行入口（API/worker；历史 dashboard 壳已于 2026-07-23 移除）
- `neotrade3/`：核心 Python 包（业务逻辑）
- `config/`：配置真相源（orchestrator/labs/screeners/strategies 等）
- `docs/`：架构/运维/迁移/交接/验收文档
- `scripts/`：脚本与维护工具（可能包含一次性迁移脚本）
- `tests/`：单元测试与验收证据
- `pyproject.toml`：项目元数据与工具配置
- `CLAUDE.md`：项目级工作规则
- `PROJECT_STATUS.md`：项目状态与交接入口

### 派生物（可再生/可清理候选，详见 cleanup_candidates）

- `.venv/`：Python 虚拟环境（通常可重建，但重建依赖是否可确定需要证据）
- `neotrade3-dashboard/node_modules/`：前端依赖缓存（可重建）
- `neotrade3-dashboard/dist/`：前端构建产物（可重建）
- `__pycache__/`：Python 字节码缓存（可重建）
- `.pytest_cache/`：pytest 缓存（可重建）
- `.DS_Store`：macOS Finder 元数据（可重建）

### 运行时数据（不在 Git，清理需单独决策）

- `var/`：运行时数据根目录（ledger/artifact/log/db 等）
  - 当前环境中为外置盘符号链接：`var -> /Volumes/NEO/NeoTradeDB/var`（2026-07-22 起；此前快照为 /Volumes/Data，已失效）
  - 清理 `var/` 会直接影响可追溯性、复现与运行稳定性，不纳入本次“仓库清理候选”的默认建议范围

### 历史参考（不自动清理）

- `legacy/`：历史参考实现/遗留入口（体积通常较小，但清理会影响对照与回退证据）
- `docs/archive/`：历史交接与归档文档（体积通常较小，但属于证据资产）

