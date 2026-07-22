# Cup Handle Lab Runtime Artifact Contract Design

Date: 2026-07-10

## 1. Goal

本切片只处理 `tests/unit/test_bootstrap_skeleton.py` 中 `test_factor_matrix_daily_output_supports_live_and_stored_modes` 里与 `cup_handle_lab` runtime artifact contract 直接相关的活跃契约对齐，目标是把当前仍在 NeoTrade3 新体系中生效的 `cup_handle_lab` 上游输入、运行结果状态和 artifact 读取链路，从同一个大测试中的其他主题里单独切出来。

目标是：

- 明确 `cup_handle_lab` 当前会真实读取 `screener_cup_handle_v4_result.json`，不再是固定 `pending_implementation`
- 明确 `lab_run.status == "ok"` 对应的是当前 runtime 正常执行结果，而不是测试侧的随意改写
- 明确 `cup_handle_daily_report` 的 `status` 与 `candidates` 是当前正式 artifact contract 的一部分
- 为当前 API 读取 `cup_handle_lab` 运行结果与 artifact 的链路保留最小直接测试覆盖

本切片不是：

- `paper_simulation_lab` artifact 结构对齐
- `factor_matrix` 中 `signals.source == "lab"` 断言的删除或保留判断
- `apps/api/main.py`、`neotrade3/labs/runtime.py`、`neotrade3/labs/contracts.py` 的生产逻辑改造
- `v1` compatibility 或 `screeners` API handler 主题

## 2. Scope

Included:

- `tests/unit/test_bootstrap_skeleton.py` 中 `test_factor_matrix_daily_output_supports_live_and_stored_modes` 里以下点位：
  - 预置 `screener_cup_handle_v4_result.json`
  - `cup_handle_lab` 的 `lab_run.status == "ok"`
  - `cup_handle_daily_report.status`
  - `cup_handle_daily_report.candidates`
  - 对应 `var/artifacts/labs/cup_handle_lab` cleanup

Excluded:

- `tests/unit/test_bootstrap_skeleton.py` 中 `paper_simulation_lab` 的 `positions/portfolio` 断言
- `tests/unit/test_bootstrap_skeleton.py` 中删除 `signals.source == "lab"` 的旧断言
- `tests/unit/test_bootstrap_skeleton.py` 中 `v1` endpoint 搬移主题
- `apps/api/main.py`
- `neotrade3/labs/runtime.py`
- `neotrade3/labs/contracts.py`
- `config/labs/labs_registry.json`
- 其他任何生产文件、测试文件和文档

## 3. Existing Context

当前代码已经给出直接证据：

- [runtime.py](file:///Users/mac/NeoTrade3/neotrade3/labs/runtime.py#L117-L185) 中 `LabRuntimeAdapter._run_cup_handle_lab()` 会读取：
  - `var/artifacts/screener_runs/<date>/screener_cup_handle_v4_result.json`
- 同一函数在读取到有效 `picks` 且成功执行时返回：
  - `status: "ok"`
  - `candidates`
  - `candidates_count`
  - `raw_candidates_count`
  - `analysis_version`
- [contracts.py](file:///Users/mac/NeoTrade3/neotrade3/labs/contracts.py#L38-L84) 中 `build_lab_runtime_artifacts_payload()` 对 `cup_handle_lab` 生成正式 artifact：
  - `artifact_id = cup_handle_daily_report`
  - `status`
  - `candidates`
  - `candidate_details`
  - `candidates_count`
  - `raw_candidates_count`
- [labs_registry.json](file:///Users/mac/NeoTrade3/config/labs/labs_registry.json#L6-L32) 已声明 `cup_handle_lab` 的正式 artifact 路径：
  - `var/artifacts/labs/cup_handle_lab/daily_report.json`
- [test_bootstrap_skeleton.py](file:///Users/mac/NeoTrade3/tests/unit/test_bootstrap_skeleton.py#L3444-L3540) 当前新增测试点位与上述现行契约直接对应：
  - 预置 `screener_artifact_path`
  - 触发 `POST /api/labs/run`
  - 断言 `payload["lab_run"]["status"] == "ok"`
  - 断言 `payload["lab_result"]["artifacts"]["cup_handle_daily_report"]`
  - 断言 `"000001" in report["candidates"]`
- [main.py](file:///Users/mac/NeoTrade3/apps/api/main.py#L3088-L3099) 的 tracking 侧也直接读取 `cup_handle_daily_report.candidates`

现状风险：

- 如果把这条线与 `paper_simulation_lab` 一起提交，会把两个不同 artifact contract 混成一刀
- 如果把“删除 `lab` signal 断言”一起带上，会把已闭合的 `cup_handle_lab` contract 和尚未完成价值判断的 `factor_matrix signal` 主题混在一起
- 如果顺手改动 runtime 或 contracts 生产文件，会把“测试契约收口”扩大成实现主题

## 4. Approach Options

### Option A: 只提交 `cup_handle_lab` runtime artifact contract 测试对齐（推荐）

仅处理：

- 上游 `screener` artifact 预置
- `cup_handle_lab` 返回 `ok`
- `cup_handle_daily_report` 的 `status/candidates`
- 对应 cleanup

Pros:

- 边界最窄，证据链完整闭合
- 每个改动点都有直接生产代码证据
- 不需要改生产代码

Cons:

- `paper_simulation_lab` 与 `factor_matrix lab signal` 仍需后续独立治理

### Option B: 同时处理 `cup_handle_lab` + `paper_simulation_lab`

Pros:

- 一次性减少更多 diff

Cons:

- 会把两个不同实验室 contract 混在同一条线里
- 难以单独解释 commit 意图

### Option C: 同时处理 `cup_handle_lab` + `factor_matrix lab signal` 断言删除

Pros:

- 表面上更“完整”

Cons:

- `lab signal` 删除的合理性当前证据还不闭合
- 会把已确认主题和待确认主题混在一起

Decision:

- choose Option A

## 5. Design

### 5.1 Responsibility Boundary

实施后职责应明确为：

- `neotrade3/labs/runtime.py`
  - 继续保留从 `screener_cup_handle_v4_result.json` 读取候选并返回 `status: "ok"` 的现有语义
- `neotrade3/labs/contracts.py`
  - 继续保留 `cup_handle_daily_report` 的现行 artifact contract
- `tests/unit/test_bootstrap_skeleton.py`
  - 为这条已存在的 runtime -> artifact -> API 读取链路保留直接测试证据

### 5.2 Contract Strategy

本切片只允许对以下点位做改动：

1. 预置 `screener_artifact_path`
   - 路径必须是 `var/artifacts/screener_runs/2026-05-19/screener_cup_handle_v4_result.json`
   - 内容至少包含 `status: "ok"` 与一条可被解析的 `picks`
2. `POST /api/labs/run` 之后：
   - 断言 `payload["lab_run"]["lab_id"] == "cup_handle_lab"`
   - 断言 `payload["lab_run"]["status"] == "ok"`
3. `GET /api/labs/runs/2026-05-19/cup_handle_lab` 之后：
   - 断言 `payload["lab_result"]["artifacts"]["cup_handle_daily_report"]["status"] == "ok"`
   - 断言候选代码进入 `report["candidates"]`
4. cleanup：
   - 恢复 `screener_artifact_path`
   - 清理 `var/artifacts/labs/cup_handle_lab`

本轮不允许顺手改动：

- `paper_simulation_lab` 的 `positions/portfolio`
- `signals.source == "lab"` 的旧断言
- 任何 `apps/api/main.py` / `runtime.py` / `contracts.py` 生产代码

### 5.3 Boundary Guardrails

实现时必须遵守：

- 不修改生产代码
- 不把 `cup_handle_lab` 的 `ok` 扩大解释为“所有 lab 都已从 placeholder 迁正”
- 不扩大到 `paper_simulation_lab`
- 不扩大到 `factor_matrix lab signal` 断言删除
- 若无法从 `test_factor_matrix_daily_output_supports_live_and_stored_modes` 的混合 diff 中只隔离该主题，应停止并报告边界问题

## 6. Testing Design

验证优先采用：

1. 针对 `test_factor_matrix_daily_output_supports_live_and_stored_modes` 的最小 pytest 选择执行
2. 复核该测试中 `cup_handle_lab` 相关断言与 `paper_simulation_lab` / `lab signal` 主题物理分开
3. 确认本轮 staged diff 不包含生产文件

默认不要求：

- 跑整份 `test_bootstrap_skeleton.py`
- 处理 `paper_simulation_lab`
- 处理 `factor_matrix lab signal` 断言删除
- 修改 runtime 或 contracts 实现后再回归

原因：

- 当前风险主要在边界纯度，而不是实现缺失
- 现行行为已有明确生产代码证据

## 7. Validation

预期验证方式：

- 运行 `tests/unit/test_bootstrap_skeleton.py -k factor_matrix_daily_output_supports_live_and_stored_modes`
- 复核 staged diff 只包含 `cup_handle_lab` runtime artifact contract 相关 hunk
- 确认 `neotrade3/labs/runtime.py`、`neotrade3/labs/contracts.py`、`apps/api/main.py` 不进入提交

## 8. Commit Boundary

目标提交应限制为：

- `tests/unit/test_bootstrap_skeleton.py` 中 `cup_handle_lab` runtime artifact contract 的最小测试对齐

必须排除：

- `paper_simulation_lab` 相邻 hunk
- 删除 `signals.source == "lab"` 的 hunk
- `v1` compatibility 相邻 hunk
- 所有生产文件与其他文档

若相对 `HEAD` 无法将该主题与相邻主题安全分离，本轮结论应明确为：

- “边界需要重新评估，不强行提交”
