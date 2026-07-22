Status: Approved
Owner: tests
Scope: Prevent screener config writeback to repo config/ during tests
Canonical: /Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-15-lowfreq-test-isolation-screener-config-writeback-design.md
Supersedes:
Superseded_by:
Last_reviewed: 2026-07-15

# Test Isolation: Screener Config Writeback

## 背景

`tests/unit/test_bootstrap_skeleton.py::test_bootstrap_api_handler_accepts_screener_run_post` 会对：

- `POST /api/screeners/config/<screener_id>`

发起写请求。服务端路径：

- `BootstrapApiService.screener_config_update_view(...)`
- `neotrade3.screeners.storage.write_screener_config(...)`

该写入会刷新 `config/screeners/<screener_id>.json` 的 `updated_at/updated_by`，从而污染 repo 工作区。

## 目标

- 测试中 `screener config update` 的写入落到 `tmp_path/config/screeners` 的副本
- repo `config/` 不再被测试写脏

## 非目标

- 不改 API 运行时行为（不加环境变量开关）
- 不改 `write_screener_config` 逻辑
- 不重构 screeners 模块

## 方案（只改测试）

在 `test_bootstrap_api_handler_accepts_screener_run_post` 中：

1. 构造 `tmp_path/config/screeners` 作为隔离目录
2. 从 repo `config/screeners/` 复制：
   - `screeners_registry.json`
   - `cup_handle_v4.json`
3. 将 `BootstrapApiService` 的下列字段指向隔离目录：
   - `_screeners_config_dir`
   - `_screeners_registry_config`

确保：

- `GET /api/screeners/config/cup_handle_v4` 读的是副本
- `POST /api/screeners/config/cup_handle_v4` 写的是副本

## 验证

- 定点运行该测试用例
- 测试结束后 `git status --short` 应保持干净（不再出现 `config/screeners/cup_handle_v4.json` 变更）

## M/G 双轴审计

### M 轴

- 只影响测试隔离，不改模型、筛选器语义或 runtime

### G 轴

- 不触及治理、调度与写路径，只避免测试污染 repo 配置
