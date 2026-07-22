# Lowfreq Formal Front Attachment Design

Date: 2026-07-10

## 1. Goal

本设计只处理 `E3: formal front attachment isolation` 的实现设计。

目标是：

- 把 `lowfreq_engine_v16_advanced.py` 中“消费 formal inputs、组装 formal front payload、附着到 candidate signals”的接线职责，从 engine 文件中剥离出来
- 明确这一层属于 `decision_engine` 侧的 formal front assembly / attachment，而不是 `M1` 读取或 `M3 nucleus` 本体
- 保持 `generate_buy_signals()` 的对外结果形状不变
- 为后续 `E4: M2 legacy recognition zone` 留下更纯净的 engine 主链

本设计不是：

- `M1` read-side adapter 设计
- `M3 nucleus` 状态机重组设计
- `project_lowfreq_formal_front()` 的 projection contract 改写
- `apps/api/main.py` 或 report scripts 的 formal front 消费改造

## 2. Scope

Included:

- [_build_formal_front_chain_payload](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2827-L2914) 的职责认账与剥离设计
- [_attach_formal_front_payloads](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2813-L2825) 的职责认账与剥离设计
- `generate_buy_signals()` 中 formal front 的接线调用关系
- `decision_engine` 中已存在的 formal state builders 与 formal-front projection 的 owner 证据
- 现有 formal front focused tests 的承载边界

Excluded:

- `load_formal_m1_inputs()` 的实现与返回结构调整
- `build_small_cycle_from_m1()`、`build_identify_state_from_formal_inputs()`、`build_tracking_state_from_formal_inputs()`、`build_entry_state_from_formal_inputs()` 的语义调整
- `project_lowfreq_formal_front()` 输出字段调整
- `generate_buy_signals()` 中去重、排序、entry 过滤等 `M3` 主链逻辑
- `apps/api/main.py` 与 `scripts/generate_lowfreq_top200_attribution_report.py` 的消费者逻辑

## 3. Existing Context

当前仓库已经给出四组直接证据：

- engine 当前仍直接拥有 formal front 接线：
  - [_build_formal_front_chain_payload](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2827-L2914) 负责：
    - 遍历 candidate codes
    - 调用 `load_formal_m1_inputs(...)`
    - 组织 `small_cycle / m1_constraints_ref / identify_state / tracking_state / entry_state`
    - 汇总 `items_by_code`
    - 输出 `status / summary / items_by_code`
  - [_attach_formal_front_payloads](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2813-L2825) 负责把 `formal` payload 附着到 `candidate_signals`
- `decision_engine` 已拥有 formal state 组装 owner：
  - [assembler.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/assembler.py#L47-L198) 已正式承载：
    - `build_m1_constraints_ref()`
    - `build_identify_state_from_formal_inputs()`
    - `build_tracking_state_from_formal_inputs()`
    - `build_entry_state_from_formal_inputs()`
- `decision_engine` 还已拥有 formal-front projection owner：
  - [project_lowfreq_formal_front](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/projections.py#L8-L61) 从 signal payload 的 `formal` 字段投影 compact snapshot
- formal front 现有 focused tests 已存在：
  - [test_lowfreq_engine_v16_formal_front.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_formal_front.py#L126-L188) 已保护：
    - `M1` 不可用时 `formal.status = error`
    - `M1` 可用时 `formal.summary` 与 `candidate["formal"]` 的 `small_cycle / identify_state / tracking_state / entry_state`
  - [test_lowfreq_formal_front_projection.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_formal_front_projection.py) 已保护 projection 侧消费 contract

现状问题不是 formal front 不存在，而是 owner 分散：

- `M1` 读取已在 `data_control`
- formal state builders 与 projection 已在 `decision_engine`
- 但 engine 文件仍自己做 formal front 的总装配和附着

这导致：

- `E2` 和 `E3` 的边界虽然已概念分开，但还没有物理分开
- engine 文件仍混入 decision-facing assembly
- 后续 `E4` 很难只看 `M2/M3` 主链

## 4. Approach Options

### Option A: 提取到 `decision_engine` 的 formal front 模块（推荐）

- 在 `neotrade3/decision_engine/` 下新增 formal front 专用模块
- 把 payload 组装与 signal attachment 都移到该模块
- engine 只保留调用 facade

Pros:

- 与现有 owner 证据最一致：state builders 与 projection 都已经在 `decision_engine`
- 物理上把 `M1` 读取、formal front 接线、`M3` 主核进一步分账
- 可直接复用现有 formal front focused tests

Cons:

- 需要新增一个 decision_engine 模块
- 必须克制范围，不能顺手改 projection 或 API consumers

### Option B: 提取到 engine 邻近的私有 helper 模块

- 新增 lowfreq engine 私有模块，只把 `_build_formal_front_chain_payload()` 与 `_attach_formal_front_payloads()` 从大文件移走

Pros:

- 改动路径直观

Cons:

- 只是文件瘦身，不是 owner 收口
- formal front 仍停留在 engine 语义边界附近

### Option C: 保留在 engine，只做局部重排

- 不新增模块，只重命名或缩短函数

Pros:

- 变更最小

Cons:

- 不满足 `E3` 目标
- 无法为 `E4` 提供更纯净的主链边界

Decision:

- 采用 Option A

## 5. Design

### 5.1 Ownership Decision

`E3` 要剥离的职责是：

- 从 `candidate_signals` 提取 code 集
- 消费 `load_formal_m1_inputs(...)` 的输入底座
- 生成每个 code 的 formal front raw item
- 汇总出 `status / summary / items_by_code`
- 把 raw item 附着回 `candidate_signals[*]["formal"]`

这些职责应定义为：

- `decision-facing formal front assembly`

而不是：

- `M1 read adapter`
- `M3 nucleus`
- `API projection`

### 5.2 Recommended File Boundary

推荐新增：

- `neotrade3/decision_engine/formal_front.py`

该文件只承接：

- formal front payload assembly
- formal front signal attachment

不承接：

- `M1` SQL 读取
- API view projection
- report formatting
- buy/sell runtime 状态机

推荐原因：

- `assembler.py` 已拥有 formal state builders
- `projections.py` 已拥有 formal-front projection
- 把 assembly/attachment 放到同层目录，owner 表达最一致

### 5.3 Adapter Surface

推荐在新模块中暴露两个 facade：

- `build_lowfreq_formal_front_payload(...)`
- `attach_lowfreq_formal_front_payloads(...)`

其中：

- `build_lowfreq_formal_front_payload(...)` 接收：
  - `cursor`
  - `target_date`
  - `candidate_signals`
  - 可选 `history_limit`
- 它内部负责调用 `load_formal_m1_inputs(...)`，并生成当前 engine 所需的整个 formal payload：
  - `status`
  - `summary`
  - `items_by_code`
- `attach_lowfreq_formal_front_payloads(...)` 只负责把 `items_by_code` 附着回 `candidate_signals`

设计意图：

- 保持 `generate_buy_signals()` 当前调用面与结果形状不变
- 同时把 formal front 接线从 engine 中整体挪出，而不是只拆一半

### 5.4 Error Boundary

本轮不改变 formal front 的对外错误语义。

仍需保持：

- 当 `load_formal_m1_inputs(...)` 或 formal state assembly 抛错时，返回：
  - `formal_payload["status"] = "error"`
  - `formal_payload["error_type"] = "formal_projection_failed"`
  - `formal_payload["message"] = 原始异常文本`
- `attach_lowfreq_formal_front_payloads(...)` 在缺失 code 对应 item 时，仍给 candidate 附：
  - `{"status": "unavailable"}`

### 5.5 What Stays In Engine

以下职责在 `E3` 后仍留在 engine：

- `generate_buy_signals()` 里的：
  - signal 去重
  - `_build_signal_structure_payload()`
  - entry-ready 过滤
  - `signal_payload["formal"] = formal_payload`
- `generate_buy_signals()` 对 formal front 的消费顺序

原因：

- 这些仍属于 lowfreq engine 主链 orchestration
- `E3` 只去掉 formal front 组装细节，不改主链编排

### 5.6 Testing Strategy

本轮不新增全新主题测试文件，优先复用已有 focused carriers：

- [test_lowfreq_engine_v16_formal_front.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_formal_front.py)
  - 继续作为 engine formal front 链路护栏
- [test_lowfreq_formal_front_projection.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_formal_front_projection.py)
  - 继续作为 projection 消费护栏

如需要补强，只允许增加：

- 新模块 `formal_front.py` 的 unit-level focused tests

明确不需要：

- 扩张到 `generate_buy_signals()` 的 omnibus 回归
- 改写 API consumers 的 formal front 测试

### 5.7 Validation Baseline

`E3` 完成后，至少验证：

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_formal_front.py`
- `python3 -m pytest tests/unit/test_lowfreq_formal_front_projection.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_formal_input_adapter.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/decision_engine/formal_front.py`

验证重点：

- formal front raw payload 形状没变
- candidate `formal` 附着行为没变
- `E2` 的 `M1` adapter 边界没有被重新拉回 engine

## 6. Commit Boundary

本轮 design 提交应只包含：

- `docs/superpowers/specs/2026-07-10-lowfreq-formal-front-attachment-design.md`

后续 implementation 若按本设计推进，推荐最小文件边界为：

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/formal_front.py`
- 如确有必要，对应 focused tests

必须排除：

- `neotrade3/data_control/formal_input_adapter.py`
- `neotrade3/decision_engine/projections.py`
- `neotrade3/decision_engine/assembler.py`
- `apps/api/main.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- 其他任何工作区既有改动

## 7. Success Criteria

本设计完成后，应达到：

- engine 不再直接拥有 formal front assembly / attachment 细节
- formal front 接线的 owner 明确落到 `decision_engine`
- `generate_buy_signals()` 的 `formal` 输出与 candidate 附着行为保持不变
- `E4` 可以在更纯净的 engine 主链上继续审计 `M2 legacy recognition zone`
