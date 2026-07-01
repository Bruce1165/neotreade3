# NeoTrade3 Python 3.10 与统一解释器收口（设计定稿）

日期：2026-06-16  
范围：全项目 Python 版本约束、正式运行入口解释器、正式运行文档

## 1. 背景

- 当前项目主配置口径已经围绕 Python 3.10：
  - `pyproject.toml` 的 `requires-python`
  - Black `py310`
  - Mypy `3.10`
  - CI `3.10`
- 但仓库内仍存在 `python` / `python3` / `python3.10` / `./.venv/bin/python` 并存的运行方式。
- 自动任务的 LaunchAgent 在安装时会把解释器路径固化进 plist；如果安装时与后续实际运行环境不一致，就会产生运行态漂移。
- 本轮真实验收中已经出现过：代码和环境静态检查通过，但运行中的 API 进程没有重载到当前目标解释器状态，导致 `Tushare` 运行结果与预期不一致。

## 2. 目标

- 全项目正式支持版本统一为 Python `3.10`。
- 全项目正式本地运行解释器统一为 `PROJECT_ROOT/.venv/bin/python`。
- 所有正式运行入口在启动时都明确打印当前解释器路径与 Python 版本，并在版本不符合时直接失败。
- 所有正式文档不再混用 `python` / `python3` / `python3.10` 口径。

## 3. 非目标

- 本轮不升级到 Python `3.11+`。
- 本轮不重构历史 archive 脚本的 shebang。
- 本轮不处理与 Python 版本无关的第三方依赖治理议题。

## 4. 单一口径

### 4.1 版本口径

- `pyproject.toml` 收紧为 `>=3.10,<3.11`。
- 所有正式运行入口都按“必须是 Python 3.10.x”执行，而不是“只要不低于 3.10 即可”。

### 4.2 解释器口径

- 本地正式运行、运维命令、LaunchAgent 安装与校验统一使用：
  - `./.venv/bin/python`
- 不再把 `python` / `python3` / `python3.10` 作为正式运行命令写入正式文档。

## 5. 实施范围

### 5.1 配置层

- 更新 `pyproject.toml`：
  - `requires-python = ">=3.10,<3.11"`

### 5.2 正式运行入口

- 对以下入口增加统一版本守卫与运行时解释器信息输出：
  - `apps/api/main.py`
  - `apps/api/main_modular.py`
  - `apps/worker/main.py`
  - `neotrade3/scheduler/task_scheduler.py`
- 守卫策略：
  - 若当前 Python 不是 `3.10.x`，直接失败并输出清晰错误。
  - 启动时输出 `entrypoint`、`sys.executable`、`sys.version`。

### 5.3 启动脚本

- 更新 `scripts/start-server.sh`：
  - 默认解释器不再回退到 PATH 中的 `python3`
  - 默认使用 `PROJECT_DIR/.venv/bin/python`

### 5.4 正式文档

- 统一以下正式文档中的运行命令到 `./.venv/bin/python`：
  - `docs/operations/bootstrap_runbook.md`
  - `docs/operations/production_task_registry.md`（如需补强口径）
  - `docs/user_manual.md`
  - `tests/README.md`
  - `apps/api/README_MODULAR.md`
  - `PROJECT_STATUS.md` 中仍作为当前事实暴露的运行/回归命令

## 6. 历史材料处理规则

- 对历史交接文档、历史设计文档、archive 脚本：
  - 不按“当前正式口径”重写历史事实
  - 仅在必要时补充归档说明
- 本轮不做全仓 shebang 机械替换。

## 7. 验收标准

1. `pyproject.toml` 的版本口径收紧为 `>=3.10,<3.11`。
2. 正式运行入口在 Python 非 `3.10.x` 时会直接失败。
3. API / Worker / Scheduler 启动日志能看到当前解释器路径与 Python 版本。
4. `scripts/start-server.sh` 默认解释器为 `PROJECT_ROOT/.venv/bin/python`。
5. 正式文档不再把 `python` / `python3` / `python3.10` 当作当前正式运行命令。
6. 重新验证 `POST /api/data/update` 时，运行结果与当前 `.venv` 环境一致。

## 8. 实施后继续动作

- 完成版本统一后，回到本轮 `100%` 收口验收。
- 重点复核：
  - API 正式入口
  - LaunchAgent 实际解释器
  - `Tushare` 主源真实运行结果
