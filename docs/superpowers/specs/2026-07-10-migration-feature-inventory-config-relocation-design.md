# Migration Feature Inventory Config Relocation Design

Date: 2026-07-10

## 1. Goal

本切片只处理 NeoTrade2 特征清单 `v3` 的落位收口：将运行时应消费的清单基线显式落到 `config/migration/`，并让测试侧的单点常量路径与该落位保持一致，不扩展到 `docs/migration/` 目录内其他引用修正、映射文件改写或 `test_bootstrap_skeleton.py` 中无关新增用例。

目标是：

- 为运行期与测试期提供统一的 `config/migration/neotrade2_feature_inventory.v3.json`
- 让 [test_bootstrap_skeleton.py](file:///Users/mac/NeoTrade3/tests/unit/test_bootstrap_skeleton.py) 的 `FEATURE_INVENTORY_FILE` 常量与当前生产侧路径对齐
- 将当前剩余工作区中一条可独立解释的“迁移清单落位”主题从混合测试 diff 中切出来

本切片不是：

- `docs/migration/` 文档引用修正
- `config/migration/mappings/` 内容调整
- `apps/api/main.py` 行为改动
- `test_bootstrap_skeleton.py` 中 orchestration / worker / API / factor matrix 相关新增用例
- `lowfreq_engine_v16_advanced.py`

## 2. Scope

Included:

- `config/migration/neotrade2_feature_inventory.v3.json`
- `tests/unit/test_bootstrap_skeleton.py` 中 `FEATURE_INVENTORY_FILE` 常量路径切换

Excluded:

- `docs/migration/neotrade2_feature_inventory.v3.json`
- `docs/migration/**`
- `config/migration/mappings/**`
- `apps/api/main.py`
- `tests/unit/test_bootstrap_skeleton.py` 中除 `FEATURE_INVENTORY_FILE` 外的其他变更
- `lowfreq_engine_v16_advanced.py`

## 3. Existing Context

当前代码已给出可核验证据：

- [apps/api/main.py](file:///Users/mac/NeoTrade3/apps/api/main.py) 当前运行时路径已读取：
  - `config/migration/neotrade2_feature_inventory.v3.json`
- 工作区已新增 [config/migration/neotrade2_feature_inventory.v3.json](file:///Users/mac/NeoTrade3/config/migration/neotrade2_feature_inventory.v3.json)
- [docs/migration/neotrade2_feature_inventory.v3.json](file:///Users/mac/NeoTrade3/docs/migration/neotrade2_feature_inventory.v3.json) 仍保留在文档目录
- 两份 `v3` 清单文件当前内容完全一致
- [test_bootstrap_skeleton.py](file:///Users/mac/NeoTrade3/tests/unit/test_bootstrap_skeleton.py) 中当前只有一处直接消费该路径：
  - `FEATURE_INVENTORY_FILE = PROJECT_ROOT / "config/migration/neotrade2_feature_inventory.v3.json"`
- 但同一测试文件相对 `HEAD` 还混有多组无关主题：
  - orchestration status 聚合断言
  - worker run ledger status 断言
  - API key header 行为调整
  - v1 screener results 测试搬移
  - factor matrix / lab artifact 断言扩展

现状风险：

- 如果直接整体提交 `test_bootstrap_skeleton.py`，会把“路径常量收口”与多条测试行为主题混成脏切片
- 如果顺手去修 `docs/migration/**` 中所有引用，会从“运行期清单落位”扩大成文档同步主题
- 如果把 `apps/api/main.py` 一起带上，会把已存在的生产契约重新包装成实现主题，降低提交纯度

## 4. Approach Options

### Option A: 只提交 config 清单落位 + 测试常量路径切换（推荐）

仅处理：

- 新增 `config/migration/neotrade2_feature_inventory.v3.json`
- `FEATURE_INVENTORY_FILE` 常量从 `docs/migration/...` 切到 `config/migration/...`

Pros:

- 边界最窄，直接服务于当前运行期路径契约
- 生产侧与测试侧的唯一直接消费点都能闭环
- 不会卷入文档引用和其他测试主题

Cons:

- `docs/migration/**` 的历史引用仍需后续单独治理

### Option B: 同步修正文档与映射文件中的全部旧路径引用

Pros:

- 目录语义更统一

Cons:

- 明显扩大为文档/配置全面同步主题
- 无法保持当前切片原子性

### Option C: 只新增 config 清单文件，不动测试常量

Pros:

- 变更面更小

Cons:

- 测试侧继续指向旧路径，运行期与测试期不一致
- 切片无法完成最小闭环

Decision:

- choose Option A

## 5. Design

### 5.1 Responsibility Boundary

实施后职责应明确为：

- `config/migration/neotrade2_feature_inventory.v3.json`
  - 作为运行期与配置域的迁移清单基线副本
- `tests/unit/test_bootstrap_skeleton.py`
  - 通过 `FEATURE_INVENTORY_FILE` 常量消费 config 域清单
- `docs/migration/neotrade2_feature_inventory.v3.json`
  - 继续保留为历史/文档载体，不属于本轮治理对象

### 5.2 Contract Strategy

本切片只允许对以下点位做改动：

1. 新增 `config/migration/neotrade2_feature_inventory.v3.json`
2. 将 `FEATURE_INVENTORY_FILE` 切到 `config/migration/neotrade2_feature_inventory.v3.json`

本轮不允许顺手改动：

- `apps/api/main.py`
- `docs/migration/**`
- `config/migration/mappings/**`
- `test_bootstrap_skeleton.py` 中其他任何测试用例逻辑

### 5.3 Boundary Guardrails

实现时必须遵守：

- 不修改 `FEATURE_INVENTORY_FILE` 之外的测试逻辑
- 不删除 `docs/migration/neotrade2_feature_inventory.v3.json`
- 不做大范围路径替换
- 若无法从 `test_bootstrap_skeleton.py` 的混合 diff 中仅隔离常量路径切换，则应停止并报告边界问题，而不是扩大提交范围

## 6. Testing Design

验证优先采用：

1. 最近编辑文件的最小语法/结构检查
2. 与 `FEATURE_INVENTORY_FILE` 直接相关的最小测试验证

默认不要求：

- 跑整份 `test_bootstrap_skeleton.py`
- 扩大到 orchestration / worker / factor matrix 相关测试
- 修文档引用再做全量回归

原因：

- 本轮风险主要在边界纯度和路径契约一致性
- 当前测试文件混合主题过多，应避免为了路径常量切换误带入无关行为回归

## 7. Validation

预期验证方式：

- 确认 `config/migration/neotrade2_feature_inventory.v3.json` 存在且内容完整
- 确认 `FEATURE_INVENTORY_FILE` 指向 config 域路径
- 确认本轮 staged diff 不含 `test_bootstrap_skeleton.py` 的其他测试主题

## 8. Commit Boundary

目标提交应限制为：

- `config/migration/neotrade2_feature_inventory.v3.json`
- `tests/unit/test_bootstrap_skeleton.py` 中 `FEATURE_INVENTORY_FILE` 常量路径切换

必须排除：

- `docs/migration/**`
- `config/migration/mappings/**`
- `apps/api/main.py`
- `tests/unit/test_bootstrap_skeleton.py` 中其他 hunk
- `lowfreq_engine_v16_advanced.py`

若相对 `HEAD` 无法将测试文件中的单点路径常量切换与其他新增测试安全分离，本轮结论应明确为：

- “边界需要重新评估，不强行提交”
