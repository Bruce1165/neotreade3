# Paper Simulation Lab Artifact Shape Contract Design

Date: 2026-07-10

## 1. Goal

本切片只处理 `tests/unit/test_bootstrap_skeleton.py` 中 `test_factor_matrix_daily_output_supports_live_and_stored_modes` 里与 `paper_simulation_lab` artifact shape contract 直接相关的活跃契约对齐，目标是把当前仍在 NeoTrade3 新体系中生效的 `paper_simulation_lab` artifact 结构，从同一个大测试中的其他主题里单独切出来。

目标是：

- 明确 `paper_simulation_lab` 当前正式 artifact contract 已经是 `cash_yuan + positions + portfolio + trades + analytics`
- 明确旧的 `universe_snapshot["candidate_count"]` 不再是当前 contract 的稳定结构
- 为当前 API 读取 `paper_simulation_positions` 的链路保留最小直接测试覆盖

本切片不是：

- `cup_handle_lab` runtime artifact contract
- `factor_matrix` 中 `signals.source == "lab"` 断言的删除或保留判断
- `apps/api/main.py`、`neotrade3/labs/runtime.py`、`neotrade3/labs/contracts.py` 的生产逻辑改造
- `v1` compatibility 或 `screeners` API handler 主题

## 2. Scope

Included:

- `tests/unit/test_bootstrap_skeleton.py` 中 `test_factor_matrix_daily_output_supports_live_and_stored_modes` 里以下点位：
  - `paper_simulation_lab` 的 `lab_result["lab_id"]`
  - `paper_simulation_positions["cash_yuan"]`
  - `paper_simulation_positions["positions"]`
  - `paper_simulation_positions["portfolio"]`
  - 对应 `var/artifacts/labs/paper_simulation_lab` cleanup

Excluded:

- `tests/unit/test_bootstrap_skeleton.py` 中 `cup_handle_lab` 相关 hunk
- `tests/unit/test_bootstrap_skeleton.py` 中删除 `signals.source == "lab"` 的旧断言
- `tests/unit/test_bootstrap_skeleton.py` 中 `v1` endpoint 搬移主题
- `apps/api/main.py`
- `neotrade3/labs/runtime.py`
- `neotrade3/labs/contracts.py`
- `config/labs/labs_registry.json`
- 其他任何生产文件、测试文件和文档

## 3. Existing Context

当前代码已经给出直接证据：

- [runtime.py](file:///Users/mac/NeoTrade3/neotrade3/labs/runtime.py#L624-L689) 中 `_run_paper_simulation_lab()` 返回：
  - `status: "ok"`
  - `portfolio`
  - `positions`
  - `trades`
  - `analytics`
  - `analysis_version`
- [contracts.py](file:///Users/mac/NeoTrade3/neotrade3/labs/contracts.py#L85-L122) 中 `build_lab_runtime_artifacts_payload()` 对 `paper_simulation_lab` 生成正式 artifact：
  - `artifact_id = paper_simulation_positions`
  - `cash_yuan`
  - `positions`
  - `portfolio`
  - `trades`
  - `analytics`
- [test_bootstrap_skeleton.py](file:///Users/mac/NeoTrade3/tests/unit/test_bootstrap_skeleton.py#L3596-L3605) 当前剩余测试点位与上述现行契约直接对应：
  - 读取 `paper_simulation_positions`
  - 断言 `cash_yuan > 0`
  - 断言 `positions` 为列表
  - 断言 `portfolio` 为字典
- 当前工作区 diff 表明旧断言仍停留在：
  - `positions["universe_snapshot"]["candidate_count"] >= 1`
  但该字段并不在当前正式 contract 中
- `paper_simulation_lab` 也有对应正式 artifact 落盘目录：
  - [test_bootstrap_skeleton.py](file:///Users/mac/NeoTrade3/tests/unit/test_bootstrap_skeleton.py#L3776-L3782) 已出现 `var/artifacts/labs/paper_simulation_lab` cleanup

现状风险：

- 如果继续沿用 `universe_snapshot` 旧断言，会把历史结构误描述成现行 contract
- 如果把这条线与 `cup_handle_lab` 或 `lab signal` 主题一起提交，会形成多主题混杂
- 如果顺手改动 runtime 或 contracts 生产文件，会把“测试契约收口”扩大成实现主题

## 4. Approach Options

### Option A: 只提交 `paper_simulation_lab` artifact shape 测试对齐（推荐）

仅处理：

- `cash_yuan`
- `positions`
- `portfolio`
- 对应 cleanup

Pros:

- 边界最窄，证据链清楚
- 每个改动点都有直接生产代码依据
- 不需要改生产代码

Cons:

- `lab signal` 主题仍需后续独立治理

### Option B: 同时处理 `paper_simulation_lab` + `cup_handle_lab`

Pros:

- 一次性减少更多 diff

Cons:

- 会把两个不同实验室 contract 混在同一条线里
- 当前 `cup_handle_lab` 已单独闭环，没必要回并

### Option C: 同时处理 `paper_simulation_lab` + `lab signal` 断言删除

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
  - 继续保留 `paper_simulation_lab` 返回 `portfolio/positions/trades/analytics` 的现有语义
- `neotrade3/labs/contracts.py`
  - 继续保留 `paper_simulation_positions` 的现行 artifact contract
- `tests/unit/test_bootstrap_skeleton.py`
  - 为这条已存在的 runtime -> artifact -> API 读取链路保留直接测试证据

### 5.2 Contract Strategy

本切片只允许对以下点位做改动：

1. `GET /api/labs/runs/2026-05-19/paper_simulation_lab` 之后：
   - 断言 `payload["lab_result"]["lab_id"] == "paper_simulation_lab"`
   - 读取 `positions = payload["lab_result"]["artifacts"]["paper_simulation_positions"]`
2. 断言 `paper_simulation_positions` 的最小 contract：
   - `positions["cash_yuan"] > 0`
   - `isinstance(positions["positions"], list)`
   - `isinstance(positions["portfolio"], dict)`
3. cleanup：
   - 清理 `var/artifacts/labs/paper_simulation_lab`

本轮不允许顺手改动：

- `cup_handle_lab` 相关断言
- `signals.source == "lab"` 的旧断言
- 任何 `apps/api/main.py` / `runtime.py` / `contracts.py` 生产代码

### 5.3 Boundary Guardrails

实现时必须遵守：

- 不修改生产代码
- 不把 `paper_simulation_lab` 的 contract 扩大解释为所有 labs 的统一 contract
- 不扩大到 `cup_handle_lab`
- 不扩大到 `factor_matrix lab signal` 断言删除
- 若无法从 `test_factor_matrix_daily_output_supports_live_and_stored_modes` 的混合 diff 中只隔离该主题，应停止并报告边界问题

## 6. Testing Design

验证优先采用：

1. 针对 `test_factor_matrix_daily_output_supports_live_and_stored_modes` 的最小 pytest 选择执行
2. 复核该测试中 `paper_simulation_lab` 相关断言与 `cup_handle_lab` / `lab signal` 主题物理分开
3. 确认本轮 staged diff 不包含生产文件

默认不要求：

- 跑整份 `test_bootstrap_skeleton.py`
- 处理 `cup_handle_lab`
- 处理 `factor_matrix lab signal` 断言删除
- 修改 runtime 或 contracts 实现后再回归

原因：

- 当前风险主要在边界纯度，而不是实现缺失
- 现行行为已有明确生产代码证据

## 7. Validation

预期验证方式：

- 运行 `tests/unit/test_bootstrap_skeleton.py -k factor_matrix_daily_output_supports_live_and_stored_modes`
- 复核 staged diff 只包含 `paper_simulation_lab` artifact shape 相关 hunk
- 确认 `neotrade3/labs/runtime.py`、`neotrade3/labs/contracts.py`、`apps/api/main.py` 不进入提交

## 8. Commit Boundary

目标提交应限制为：

- `tests/unit/test_bootstrap_skeleton.py` 中 `paper_simulation_lab` artifact shape contract 的最小测试对齐

必须排除：

- `cup_handle_lab` 相邻 hunk
- 删除 `signals.source == "lab"` 的 hunk
- `v1` compatibility 相邻 hunk
- 所有生产文件与其他文档

若相对 `HEAD` 无法将该主题与相邻主题安全分离，本轮结论应明确为：

- “边界需要重新评估，不强行提交”
