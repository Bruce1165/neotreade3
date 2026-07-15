Status: Approved
Owner: tests
Scope: Extract reusable screener config isolation helper under tests/_support
Canonical: /Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-15-lowfreq-tests-support-screeners-config-helper-design.md
Supersedes:
Superseded_by:
Last_reviewed: 2026-07-15

# Tests Support: Screeners Config Isolation Helper

## 背景

部分测试会通过 API 写回 `config/screeners/<screener_id>.json`，导致 repo 工作区被写脏。

我们已在 `test_bootstrap_skeleton.py` 中用 `tmp_path/config/screeners` 副本进行隔离，但目前逻辑是内联复制，未来在其他测试复用会产生重复代码与不一致风险。

## 目标

- 抽出 tests-only helper，复用“复制 screeners registry + 指定 screener configs 到 tmp_path”的逻辑
- helper 只存在于 `tests/`，不影响 runtime

## 非目标

- 不改变 API / screeners runtime 行为
- 不引入环境变量或运行时开关
- 不一次性改造所有测试，只先替换已有用例

## 方案

新增 `tests/_support/screeners_config.py`：

- `prepare_screeners_config_root(*, tmp_path: Path, screener_ids: list[str]) -> tuple[Path, Path]`
  - 创建 `tmp_path/config/screeners`
  - 复制 `PROJECT_ROOT/config/screeners/screeners_registry.json` 到隔离目录
  - 复制 `PROJECT_ROOT/config/screeners/<id>.json` 到隔离目录（每个 id）
  - 返回 `(isolated_screeners_config_dir, isolated_registry_path)`

在测试中用该 helper 替换内联复制代码，并把 service 的路径指向隔离目录：

- `service._screeners_config_dir = isolated_dir`
- `service._screeners_registry_config = isolated_registry_path`

## 验证

- 定点运行 `test_bootstrap_api_handler_accepts_screener_run_post`
- `git status --short` 应保持干净

## M/G 双轴审计

### M 轴

- 仅测试支撑工具，不改模型/筛选语义

### G 轴

- 不触及治理/调度/生产写路径
