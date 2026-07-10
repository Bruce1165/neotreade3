# Migration Feature Inventory Config Relocation 实施计划

日期：2026-07-10  
对应设计：`docs/superpowers/specs/2026-07-10-migration-feature-inventory-config-relocation-design.md`

## 1. 目标

本计划只覆盖 NeoTrade2 特征清单 `v3` 的配置域落位收口：保留 `config/migration/neotrade2_feature_inventory.v3.json` 作为运行期应消费的迁移清单副本，并让 `tests/unit/test_bootstrap_skeleton.py` 中唯一直接消费该清单的 `FEATURE_INVENTORY_FILE` 常量切换到 config 域路径，不扩展到 `docs/migration/**`、映射文件、`apps/api/main.py` 或测试文件中的其他新增主题。

本轮目标只有三个：

1. 保持 `config/migration/neotrade2_feature_inventory.v3.json` 作为当前运行期契约对应的配置清单载体。
2. 将 `FEATURE_INVENTORY_FILE` 与生产侧已存在的 config 域路径对齐。
3. 在不卷入 `test_bootstrap_skeleton.py` 其他测试主题的前提下，形成一个可独立解释的“迁移清单落位”切片。

本轮必须产出的核心结果：

- `config/migration/neotrade2_feature_inventory.v3.json` 保持在提交边界内
- `FEATURE_INVENTORY_FILE` 指向 `config/migration/neotrade2_feature_inventory.v3.json`
- staged diff 不包含 `test_bootstrap_skeleton.py` 里除路径常量外的其他 hunk
- staged diff 不包含 `docs/migration/**`、`config/migration/mappings/**`、`apps/api/main.py`

## 2. 不在本轮完成

- `docs/migration/neotrade2_feature_inventory.v3.json` 的历史定位或引用清理
- `docs/migration/**` 的批量路径修正
- `config/migration/mappings/**` 调整
- `apps/api/main.py` 行为改动
- `tests/unit/test_bootstrap_skeleton.py` 中 orchestration / worker / API / factor matrix 相关新增测试
- `lowfreq_engine_v16_advanced.py`

## 3. 当前实施起点

### 3.1 已有现实基础

- [main.py](file:///Users/mac/NeoTrade3/apps/api/main.py#L260-L262) 已明确将运行期清单路径指向 `config/migration/neotrade2_feature_inventory.v3.json`
- [neotrade2_feature_inventory.v3.json](file:///Users/mac/NeoTrade3/config/migration/neotrade2_feature_inventory.v3.json) 已存在于工作区
- `config/migration/...` 与 `docs/migration/...` 两份 `v3` 清单当前内容一致
- [test_bootstrap_skeleton.py](file:///Users/mac/NeoTrade3/tests/unit/test_bootstrap_skeleton.py#L59-L61) 中只有 `FEATURE_INVENTORY_FILE` 这一处直接消费该清单路径
- `git diff -- tests/unit/test_bootstrap_skeleton.py config/migration/neotrade2_feature_inventory.v3.json` 显示：测试文件除路径常量切换外，还混有多组无关新增与断言调整

### 3.2 结构性风险

- 最大风险不是路径切换本身，而是把 `test_bootstrap_skeleton.py` 中其他测试主题一起带进提交
- 如果顺手处理 `docs/migration/**`，本轮会从“运行期配置落位”扩大成文档同步主题
- 如果把 `apps/api/main.py` 一起带上，会把已存在生产契约误包装成新实现
- 如果无法从混合 diff 中隔离单点路径常量，本轮就不具备安全提交条件

## 4. 实施原则

- 只围绕 `config/migration/neotrade2_feature_inventory.v3.json` 与 `FEATURE_INVENTORY_FILE` 常量路径切换实施
- 不修改 `FEATURE_INVENTORY_FILE` 之外的测试逻辑
- 不删除 `docs/migration/neotrade2_feature_inventory.v3.json`
- 不做批量路径替换
- 不因验证失败自动扩大到其他测试主题；先回到边界判断
- 若无法安全隔离单点常量切换，则停止提交判断，不静默扩大范围

## 5. 建议改动边界

建议改动仅限：

- `config/migration/neotrade2_feature_inventory.v3.json`
- `tests/unit/test_bootstrap_skeleton.py`

允许的逻辑：

- 保留 `config/migration/neotrade2_feature_inventory.v3.json` 进入提交边界
- 将 `FEATURE_INVENTORY_FILE` 从 `docs/migration/...` 切到 `config/migration/...`

明确不改：

- `docs/migration/**`
- `config/migration/mappings/**`
- `apps/api/main.py`
- `tests/unit/test_bootstrap_skeleton.py` 中除 `FEATURE_INVENTORY_FILE` 外的任何 hunk
- 其他 Python 模块、文档和配置

## 6. 总体分段

本计划建议分为四段执行：

- `MFI-R1`：冻结“迁移清单落位”精确边界
- `MFI-R2`：只保留 config 清单文件与测试常量路径切换
- `MFI-R3`：做最小语法/结构与针对性验证
- `MFI-R4`：隔离目标 hunk 并提交

## 7. 分段实施计划

### MFI-R1：冻结“迁移清单落位”精确边界

目标：

- 明确哪些改动属于运行期清单落位，哪些相邻改动必须排除。

任务：

- 读取 [test_bootstrap_skeleton.py](file:///Users/mac/NeoTrade3/tests/unit/test_bootstrap_skeleton.py) 当前常量定义区
- 对照 `HEAD` 检查 `test_bootstrap_skeleton.py` 与 `config/migration/neotrade2_feature_inventory.v3.json` 的剩余 diff
- 只标记以下目标点位：
  - `config/migration/neotrade2_feature_inventory.v3.json`
  - `FEATURE_INVENTORY_FILE` 常量路径
- 显式排除：
  - orchestration / worker / API / factor matrix 相关测试 hunk
  - `docs/migration/**`
  - `config/migration/mappings/**`
  - `apps/api/main.py`

完成判定：

- include / exclude 列表明确
- `FEATURE_INVENTORY_FILE` 与同文件其他测试主题边界清楚分开

### MFI-R2：只保留 config 清单文件与测试常量路径切换

目标：

- 在不改变其他测试行为的前提下，完成运行期与测试期对同一 config 清单路径的对齐。

任务：

- 确认 `config/migration/neotrade2_feature_inventory.v3.json` 内容完整且未引入额外改写
- 将 `FEATURE_INVENTORY_FILE` 保持为 `PROJECT_ROOT / "config/migration/neotrade2_feature_inventory.v3.json"`
- 若工作区中 `test_bootstrap_skeleton.py` 同时混有其他主题，优先采用仅隔离目标 hunk 的方式处理

关键约束：

- 不改测试函数主体
- 不增删测试断言
- 不调整 import
- 不修改 `apps/api/main.py`
- 不删除 `docs/migration/neotrade2_feature_inventory.v3.json`

完成判定：

- 运行期路径与测试常量路径一致
- `test_bootstrap_skeleton.py` 其他逻辑保持原状

### MFI-R3：做最小语法/结构与针对性验证

目标：

- 证明本轮路径对齐不引入明显语法问题，并在最小范围内验证目标契约。

任务：

- 对最近编辑文件做最小语法/结构检查
- 运行与 `FEATURE_INVENTORY_FILE` 直接相关的最小验证，优先精确选择对应测试而非整份文件
- 若没有合适的单测入口，至少完成文件存在性、路径常量和 staged diff 结构核对

完成判定：

- 目标文件无明显语法或结构错误
- 验证结果仅覆盖本轮路径契约，不扩大到无关主题

### MFI-R4：隔离目标 hunk 并提交

目标：

- 生成一个单一目的的提交，只表达 NeoTrade2 feature inventory `v3` 的 config 域落位与测试常量对齐。

任务：

- 检查 `git diff HEAD -- tests/unit/test_bootstrap_skeleton.py config/migration/neotrade2_feature_inventory.v3.json`
- 只暂存：
  - `config/migration/neotrade2_feature_inventory.v3.json`
  - `FEATURE_INVENTORY_FILE` 常量路径切换
- 排除测试文件中其他新增或调整
- 仅在 hunk 可安全隔离时提交

完成判定：

- staged diff 只包含 config 清单文件与单点路径常量
- staged diff 不含 `test_bootstrap_skeleton.py` 其他测试主题
- staged diff 不含 `docs/migration/**`、`config/migration/mappings/**`、`apps/api/main.py`

If isolation fails:

- 停止提交
- 报告边界需要重新评估
- 不静默扩大范围

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先读 `test_bootstrap_skeleton.py` 常量定义区与 `HEAD` 对比
2. 确认 `config/migration/neotrade2_feature_inventory.v3.json` 内容完整且无需额外改写
3. 只处理 `FEATURE_INVENTORY_FILE` 单点路径
4. 做最小验证
5. 再检查 `HEAD`-relative diff
6. 只暂存目标 hunk

原因：

- 先冻结边界，再做隔离，能避免把测试文件中相邻主题一起带入
- 先做最小验证，再决定是否提交，能把风险控制在“路径契约一致性”这一单一问题上

## 9. 建议提交切分

建议单一提交：

### Commit MFI：feature inventory config relocation

范围：

- `config/migration/neotrade2_feature_inventory.v3.json`
- `tests/unit/test_bootstrap_skeleton.py` 中 `FEATURE_INVENTORY_FILE` 的单点路径切换

目的：

- 让运行期与测试期统一消费 config 域的 NeoTrade2 feature inventory `v3`

如果提交不能保持这个纯度，正确结果是“不提交”，而不是扩大成“迁移清单落位 + 测试行为调整 + 文档同步”的混合提交。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. `config/migration/neotrade2_feature_inventory.v3.json` 在提交边界内
2. `FEATURE_INVENTORY_FILE` 指向 `config/migration/neotrade2_feature_inventory.v3.json`
3. `tests/unit/test_bootstrap_skeleton.py` 其他逻辑不进入提交
4. 不修改 `docs/migration/**`
5. 不修改 `config/migration/mappings/**`
6. 不修改 `apps/api/main.py`
7. staged diff 能被单独解释为“迁移清单落位到 config/migration”

## 11. 风险提示

- 最大风险是 `test_bootstrap_skeleton.py` 的混合 diff 过宽，导致单点路径常量难以隔离
- 第二风险是把“已有生产路径事实”误当成本轮必须改动的实现点，从而带入 `apps/api/main.py`
- 第三风险是为了追求“目录统一”而顺手清理 `docs/migration/**`，把窄切片扩大成多主题提交

## 12. 结论

本计划的核心不是“统一所有迁移清单引用”，而是完成一条可独立解释的运行期配置落位线：

- 只保留 `config/migration/neotrade2_feature_inventory.v3.json`
- 只切 `FEATURE_INVENTORY_FILE` 的单点路径常量
- 只在相对 `HEAD` 能保持原子性的前提下提交

这样后续如需处理文档目录历史引用或测试文件中的其他行为主题，仍可作为独立切片继续治理。
