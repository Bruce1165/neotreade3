# Cup Handle Lab Runtime Artifact Contract 实施计划

日期：2026-07-10  
对应设计：`docs/superpowers/specs/2026-07-10-cup-handle-lab-runtime-artifact-contract-design.md`

## 1. 目标

本计划只覆盖 `tests/unit/test_bootstrap_skeleton.py` 中 `test_factor_matrix_daily_output_supports_live_and_stored_modes` 里与 `cup_handle_lab` runtime artifact contract 直接相关的测试对齐：在不修改 `apps/api/main.py`、`neotrade3/labs/runtime.py` 与 `neotrade3/labs/contracts.py` 生产逻辑的前提下，隔离并提交这条测试里的最小变化，用来让测试准确描述当前仍在 NeoTrade3 新体系中生效的 `cup_handle_lab` 上游 artifact 输入、运行状态与 artifact 读取链路。

本轮目标只有四个：

1. 让测试显式预置 `screener_cup_handle_v4_result.json`，与 `cup_handle_lab` 的当前上游输入对齐。
2. 让 `POST /api/labs/run` 后 `cup_handle_lab` 的状态断言与现行 runtime 结果对齐为 `"ok"`。
3. 让 `GET /api/labs/runs/<date>/cup_handle_lab` 后的 `cup_handle_daily_report` 断言与现行 artifact contract 对齐。
4. 在不卷入 `paper_simulation_lab`、`factor_matrix lab signal` 或 `v1` 相邻主题的前提下，形成一个可独立解释的 `cup_handle_lab` contract 切片。

本轮必须产出的核心结果：

- `tests/unit/test_bootstrap_skeleton.py` 中 `cup_handle_lab` 相关点位完成最小契约对齐
- 提交中不包含 `apps/api/main.py`
- 提交中不包含 `neotrade3/labs/runtime.py`
- 提交中不包含 `neotrade3/labs/contracts.py`
- 提交中不包含 `paper_simulation_lab` 的 `positions/portfolio`
- 提交中不包含删除 `signals.source == "lab"` 的 hunk
- staged diff 只表达 `cup_handle_lab` runtime artifact contract

## 2. 不在本轮完成

- `apps/api/main.py` 生产逻辑修改
- `neotrade3/labs/runtime.py` 生产逻辑修改
- `neotrade3/labs/contracts.py` 生产逻辑修改
- `paper_simulation_lab` 的 artifact 结构对齐
- `factor_matrix` 中 `signals.source == "lab"` 断言的删除或保留判断
- `v1` compatibility 相邻主题
- 其他文档、配置或前端文件

## 3. 当前实施起点

### 3.1 已有现实基础

- [runtime.py](file:///Users/mac/NeoTrade3/neotrade3/labs/runtime.py#L117-L185) 已明确 `LabRuntimeAdapter._run_cup_handle_lab()` 会读取：
  - `var/artifacts/screener_runs/<date>/screener_cup_handle_v4_result.json`
- 同一函数在读取到有效 `picks` 后会返回：
  - `status: "ok"`
  - `candidates`
  - `candidates_count`
  - `raw_candidates_count`
- [contracts.py](file:///Users/mac/NeoTrade3/neotrade3/labs/contracts.py#L38-L84) 已明确 `cup_handle_lab` 的正式 artifact：
  - `artifact_id = cup_handle_daily_report`
  - `status`
  - `candidates`
  - `candidate_details`
- [labs_registry.json](file:///Users/mac/NeoTrade3/config/labs/labs_registry.json#L6-L32) 已声明 artifact 路径：
  - `var/artifacts/labs/cup_handle_lab/daily_report.json`
- [main.py](file:///Users/mac/NeoTrade3/apps/api/main.py#L3088-L3099) 的读取侧会直接消费 `cup_handle_daily_report.candidates`
- [test_bootstrap_skeleton.py](file:///Users/mac/NeoTrade3/tests/unit/test_bootstrap_skeleton.py#L3444-L3540) 中当前剩余 diff 已集中到五处对齐点：
  - 预置 `screener_artifact_path`
  - `lab_run["lab_id"] == "cup_handle_lab"`
  - `lab_run["status"] == "ok"`
  - `report["status"] == "ok"`
  - `"000001" in report["candidates"]`

### 3.2 结构性风险

- 最大风险不是测试内容本身，而是从同一个大测试中误带入 `paper_simulation_lab` 或 `factor_matrix lab signal` 主题
- 如果顺手修改 `runtime.py` 或 `contracts.py`，会把“测试契约收口”扩大成实现主题
- 如果把 cleanup 扩大到其他实验室目录，会让提交目的变得混杂

## 4. 实施原则

- 只改 `tests/unit/test_bootstrap_skeleton.py`
- 只保留 `cup_handle_lab` runtime artifact contract 直接相关的 hunk
- 不改 `apps/api/main.py`
- 不改 `neotrade3/labs/runtime.py`
- 不改 `neotrade3/labs/contracts.py`
- 不改 `paper_simulation_lab` 相邻断言
- 不改删除 `signals.source == "lab"` 的相邻 hunk
- 若无法安全隔离目标 hunk，则停止提交判断，不静默扩大范围

## 5. 建议改动边界

建议改动仅限：

- `tests/unit/test_bootstrap_skeleton.py`

允许的逻辑：

- 预置 `var/artifacts/screener_runs/2026-05-19/screener_cup_handle_v4_result.json`
- 将 `cup_handle_lab` 的运行状态断言对齐为 `"ok"`
- 为 `cup_handle_daily_report` 增加 `status` 与 `candidates` 的最小契约断言
- 仅清理 `var/artifacts/labs/cup_handle_lab`

明确不改：

- `apps/api/main.py`
- `neotrade3/labs/runtime.py`
- `neotrade3/labs/contracts.py`
- `paper_simulation_lab` 的 `positions/portfolio`
- `signals.source == "lab"` 断言
- `v1` compatibility 相邻改动

## 6. 总体分段

本计划建议分为四段执行：

- `CHL-R1`：冻结 `cup_handle_lab` contract 测试的精确边界
- `CHL-R2`：只保留 `cup_handle_lab` 相关 hunk
- `CHL-R3`：做最小验证
- `CHL-R4`：隔离目标 hunk 并提交

## 7. 分段实施计划

### CHL-R1：冻结 `cup_handle_lab` contract 测试的精确边界

目标：

- 明确 `test_factor_matrix_daily_output_supports_live_and_stored_modes` 中哪些改动属于 `cup_handle_lab` runtime artifact contract，哪些相邻改动必须排除。

任务：

- 读取该测试完整区块
- 对照 `HEAD` 检查测试周围的剩余 diff
- 只标记以下目标点位：
  - `screener_artifact_path`
  - `cup_handle_lab` 的 `lab_run.status`
  - `cup_handle_daily_report.status`
  - `cup_handle_daily_report.candidates`
  - `cup_handle_lab` cleanup
- 显式排除：
  - `paper_simulation_lab` 的 `positions/portfolio`
  - 删除 `signals.source == "lab"` 的 hunk
  - `v1` compatibility 相邻主题

完成判定：

- include / exclude 列表明确
- `cup_handle_lab` 主题与同测试其他主题边界清楚分开

### CHL-R2：只保留 `cup_handle_lab` 相关 hunk

目标：

- 在不改变现有生产代码与相邻测试语义的前提下，只保留 `cup_handle_lab` runtime artifact contract 相关断言。

任务：

- 确认 `screener_artifact_path` 只预置当前 runtime 所需最小输入
- 确认 `POST /api/labs/run` 后只对齐：
  - `lab_id == "cup_handle_lab"`
  - `status == "ok"`
- 确认 `GET /api/labs/runs/<date>/cup_handle_lab` 后只对齐：
  - `report["status"] == "ok"`
  - 候选代码进入 `report["candidates"]`
- 确认 cleanup 仅覆盖：
  - `screener_artifact_path`
  - `var/artifacts/labs/cup_handle_lab`
- 若当前工作区测试文件同时混有其他主题，优先采用仅隔离目标 hunk 的方式处理

关键约束：

- 不修改 `apps/api/main.py`
- 不修改 `runtime.py`
- 不修改 `contracts.py`
- 不扩展到 `paper_simulation_lab`
- 不删除 `signals.source == "lab"` 断言

完成判定：

- 目标测试只表达 `cup_handle_lab` runtime artifact contract
- 相邻既有测试与其他主题保持原状

### CHL-R3：做最小验证

目标：

- 证明该测试在当前生产契约下成立，并且无需扩大到更大范围回归。

任务：

- 运行：
  - `python3 -m pytest tests/unit/test_bootstrap_skeleton.py -k factor_matrix_daily_output_supports_live_and_stored_modes`
- 若验证失败，先判断是：
  - 边界隔离问题
  - 测试断言问题
  - 还是生产契约与设计证据不一致
- 只有在证据明确要求时才重新评估边界，不能自动扩大范围

完成判定：

- 目标测试通过
- 无需修改 `apps/api/main.py`、`runtime.py` 或 `contracts.py`

### CHL-R4：隔离目标 hunk 并提交

目标：

- 生成一个单一目的的测试提交，只表达 `cup_handle_lab` runtime artifact contract 对齐。

任务：

- 检查 `git diff HEAD -- tests/unit/test_bootstrap_skeleton.py`
- 只暂存 `cup_handle_lab` 相关目标 hunk
- 排除同测试中的 `paper_simulation_lab`、`signals.source == "lab"` 与 `v1` 相邻主题
- 仅在 hunk 可安全隔离时提交

完成判定：

- staged diff 只包含该主题相关 hunk
- staged diff 不含 `apps/api/main.py`
- staged diff 不含 `runtime.py`
- staged diff 不含 `contracts.py`
- staged diff 不含同测试其他主题

If isolation fails:

- 停止提交
- 报告边界需要重新评估
- 不静默扩大范围

## 8. 文件级实施顺序

建议按以下顺序推进：

1. 先读目标测试完整区块
2. 对照 `HEAD` 确认目标 hunk 的精确范围
3. 只保留 `cup_handle_lab` 相关断言与 cleanup
4. 跑最小 pytest 验证
5. 再检查 `HEAD`-relative diff
6. 只暂存目标 hunk

原因：

- 先冻结边界，再做隔离，能避免把 `paper_simulation_lab` 与 `factor_matrix lab signal` 主题一起带入
- 先跑最小测试，再决定是否提交，能把风险控制在单一 `cup_handle_lab` contract 上

## 9. 建议提交切分

建议单一提交：

### Commit CHL：cup handle lab runtime artifact contract

范围：

- `tests/unit/test_bootstrap_skeleton.py` 中 `cup_handle_lab` 相关最小契约对齐

目的：

- 让测试准确描述当前仍在运行期生效的 `cup_handle_lab` runtime artifact contract

如果提交不能保持这个纯度，正确结果是“不提交”，而不是扩大成“cup_handle_lab + paper_simulation_lab + factor_matrix signal”的混合提交。

## 10. 最小验收口径

本轮完成后，必须同时满足：

1. `cup_handle_lab` 上游 `screener` artifact 预置已对齐
2. `lab_run.status == "ok"` 已对齐
3. `cup_handle_daily_report.status/candidates` 已对齐
4. 目标测试通过
5. `apps/api/main.py` 不改
6. `runtime.py` 不改
7. `contracts.py` 不改
8. 同测试其他主题不进入提交
9. 提交能被单独解释为 `cup_handle_lab runtime artifact contract`

## 11. 风险提示

- 最大风险是同一个大测试里的混合 diff 过宽，导致目标 hunk 难以隔离
- 第二风险是把 `cup_handle_lab` 的 `ok` 状态误解成所有实验室都已迁正
- 第三风险是为了顺手清理相邻断言而扩大到 `paper_simulation_lab` 或 `factor_matrix lab signal`

## 12. 结论

本计划的核心不是“整理整段 factor matrix 测试”，而是完成一条可独立解释的 `cup_handle_lab` 活跃 contract 测试线：

- 只保留 `cup_handle_lab` 的上游输入、运行状态、artifact 断言与 cleanup
- 只做最小 pytest 验证
- 只在相对 `HEAD` 能保持原子性的前提下提交

这样后续如需处理 `paper_simulation_lab` 或 `factor_matrix lab signal` 主题，仍可作为独立切片继续推进。
