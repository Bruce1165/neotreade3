# Lowfreq Formal Front Attachment Plan

Date: 2026-07-10
Design:

- `docs/superpowers/specs/2026-07-10-lowfreq-formal-front-attachment-design.md`

## 1. Goal

本计划只处理 `E3: formal front attachment isolation` 的实现步骤。

本轮目标是：

- 新增一个 `decision_engine` 侧的 formal front 模块
- 把 engine 当前直接持有的 formal front payload assembly / signal attachment 迁移到该模块
- 保持 `generate_buy_signals()` 的对外结果形状、`formal` payload 结构与 candidate 附着行为不变
- 不触碰 `E2` 的 `M1` adapter、`M3 nucleus` 主链、projection consumers

本轮不做：

- `load_formal_m1_inputs()` 的实现与返回结构调整
- `build_small_cycle_from_m1()` 与各类 `build_*_state_from_formal_inputs()` 的语义调整
- `project_lowfreq_formal_front()` 的 projection 改写
- `apps/api/main.py` 与 report scripts 的 consumer 逻辑改造
- `M2/M3/M6` 的其他逻辑清理

## 2. Starting Point

当前 formal front 链路分散在三处：

- `data_control.formal_input_adapter`
  - 已负责 `M1` formal 输入读取
- `decision_engine.assembler` / `decision_engine.projections`
  - 已负责 formal state builders 与 formal-front projection
- `lowfreq_engine_v16_advanced.py`
  - 仍直接持有：
    - `_build_formal_front_chain_payload()`
    - `_attach_formal_front_payloads()`

根据已批准 design，本轮只移动最后这一段“decision-facing formal front assembly / attachment”。

## 3. Implementation Strategy

采用以下策略：

- 新增文件：
  - `neotrade3/decision_engine/formal_front.py`
- 在该文件中收口：
  - code 提取与规范化
  - `load_formal_m1_inputs(...)` 的消费
  - per-code formal raw item 组装
  - payload summary 汇总
  - signal attachment
- `lowfreq_engine_v16_advanced.py` 只做三类改动：
  - 引入新 facade
  - 用 facade 替换两个本地 helper 的调用
  - 删除已被替代的两个 helper

## 4. Execution Steps

### E3-R1：冻结文件边界与输出面

实现前先锁定本轮允许改动的文件：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/formal_front.py`
- `tests/unit/test_lowfreq_engine_v16_formal_front.py`
- 如确有必要，新模块对应的 focused tests

同时冻结 formal front 对 engine 的输出面：

- payload 继续返回：
  - `status`
  - `summary`
  - `items_by_code`
- signal attachment 后，candidate 继续携带：
  - `candidate["formal"]`

完成判定：

- 本轮不会改动 `formal` 的字段形状

### E3-R2：实现 `formal_front.py`

在新模块中实现：

- 私有 code 提取 helper
- `build_lowfreq_formal_front_payload(...)`
- `attach_lowfreq_formal_front_payloads(...)`

其中 `build_lowfreq_formal_front_payload(...)` 负责：

- 从 `candidate_signals` 提取 code 列表
- 调用 `load_formal_m1_inputs(...)`
- 复用：
  - `build_m1_constraints_ref()`
  - `build_small_cycle_from_m1()`
  - `build_identify_state_from_formal_inputs()`
  - `build_tracking_state_from_formal_inputs()`
  - `build_entry_state_from_formal_inputs()`
- 生成每个 code 的 raw item
- 汇总 `status / summary / items_by_code`

`attach_lowfreq_formal_front_payloads(...)` 负责：

- 对每个 signal 附着 `formal`
- 缺失时继续给 `{"status": "unavailable"}`

实现要求：

- 输入仍沿用 engine 当前调用面
- 错误返回体继续保持 `formal_projection_failed`
- 不在模块中引入 projection consumer 逻辑

完成判定：

- formal front assembly / attachment 能在新模块中独立表达

### E3-R3：切换 engine 到 facade

在 `lowfreq_engine_v16_advanced.py` 中：

- 引入：
  - `build_lowfreq_formal_front_payload(...)`
  - `attach_lowfreq_formal_front_payloads(...)`
- 在 `generate_buy_signals()` 中用新 facade 替换：
  - `_build_formal_front_chain_payload(...)`
  - `_attach_formal_front_payloads(...)`
- 删除 engine 中已被替代的两个 helper

明确禁止：

- 不修改 `generate_buy_signals()` 的主链编排顺序
- 不修改 `signal_payload["formal"]` 的写入位置
- 不顺手改 `entry_signals` / `buy_signals` 过滤逻辑

完成判定：

- engine 不再直接拥有 formal front assembly / attachment 细节

### E3-R4：补 focused tests

优先复用已有测试文件：

- `tests/unit/test_lowfreq_engine_v16_formal_front.py`
- `tests/unit/test_lowfreq_formal_front_projection.py`

最小要求：

- formal inputs 不可用时，`formal.status = error`
- formal inputs 可用时，`formal.summary` 与 candidate `formal` 的核心字段保持不变
- projection 侧消费 contract 不回归

如确有必要，允许新增：

- `tests/unit/test_lowfreq_formal_front_attachment.py`

但只有在现有 carrier 无法清晰保护模块边界时才新增。

完成判定：

- `E3` 复用现有正式 carrier 就能建立护栏，避免测试主题膨胀

### E3-R5：最小验证

至少运行：

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_formal_front.py`
- `python3 -m pytest tests/unit/test_lowfreq_formal_front_projection.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_formal_input_adapter.py`

并补充：

- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/decision_engine/formal_front.py`

完成判定：

- engine formal front 链路无回归
- projection consumer 无回归
- `E2` adapter 边界无回归
- 生产代码语法通过

### E3-R6：窄提交

提交前只允许暂存：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/formal_front.py`
- `tests/unit/test_lowfreq_engine_v16_formal_front.py`
- 如确有必要，本轮新增的 formal front focused tests

必须排除：

- `neotrade3/data_control/formal_input_adapter.py`
- `neotrade3/decision_engine/assembler.py`
- `neotrade3/decision_engine/projections.py`
- `apps/api/main.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- 其他任何既有工作区改动

## 5. Risks and Guards

风险 1：

- 新模块顺手吸入 projection 或 consumer 逻辑，变成 decision_engine 大杂烩

保护：

- 新模块只承接 raw payload assembly / attachment，不承接 projection

风险 2：

- `generate_buy_signals()` 主链顺序被误改，导致 entry filtering 或 formal 写回时机漂移

保护：

- engine 侧只替换 helper 调用，不改 orchestration 顺序

风险 3：

- `E2` adapter 再次被拉回 engine 或被 decision 模块重写

保护：

- 继续通过 `load_formal_m1_inputs(...)` 消费 `M1` 输入，不复制任何 `M1` query/projection 细节

风险 4：

- 测试面不必要膨胀

保护：

- 优先复用 `test_lowfreq_engine_v16_formal_front.py` 与 `test_lowfreq_formal_front_projection.py`

## 6. Success Criteria

本轮完成后，应满足：

- engine 不再直接拥有 formal front assembly / attachment 细节
- formal front assembly / attachment 的 owner 明确落在 `decision_engine`
- `formal` payload 结果形状与 candidate 附着行为保持不变
- `E4` 可以在更纯净的 engine 主链上继续推进

## 7. Commit Boundary

本轮 plan 提交应只包含：

- `docs/superpowers/specs/2026-07-10-lowfreq-formal-front-attachment-plan.md`

必须排除：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/*`
- `neotrade3/data_control/*`
- `apps/api/main.py`
- `scripts/*`
- `tests/unit/*`
- 其他任何工作区改动
