# 2026-07-07 M2/M3 最小消费切换 Handoff

## 1. 这份文档的用途

本 handoff 只服务于 `M2/M3` 前半段最小正式消费切换的实现态续接。

目标：

- 让新会话直接恢复当前 `M2/M3` formal front 的真实实现状态
- 明确哪些内容已经落地到代码
- 明确哪些内容只存在于 working tree，尚未提交
- 明确当前为什么不能继续假装把 `Commit B` 切成纯净窄提交

## 2. 当前工作范围

当前已经落地并完成最小验证的范围仅限：

- `M2 small_cycle`
- `M3 identify_state`
- `M3 tracking_state`
- `M3 entry_state`
- lowfreq 引擎并行输出 `legacy + formal`
- lowfreq API formal 压缩投影
- workbench `formal_front` 优先消费
- top200 attribution report 快照层 `formal` 优先、旧字段兜底

当前明确不在本轮范围内：

- `M3 hold_state`
- `M3 exit_state`
- `mid_cycle / large_cycle / super_long_cycle`
- workbench / report 全量重构
- 仓库清理、退役治理与入口瘦身工程

## 3. 已确认边界

以下边界已经确认，不应在新会话里重新漂移：

1. 本轮只做前半段，不碰 `hold/exit`
2. 正式对象必须由引擎生成，`API` 只做投影
3. 旧字段保留兼容，但正式对象优先
4. `small_cycle` 只允许消费正式 `M1`
5. `identify/tracking/entry` 只允许消费 `small_cycle + M1 constraints`
6. `theme_momentum`、candidate tags、研究层临时标签不能重新回流影响正式前半段对象

## 4. 已落地代码位置

### 4.1 正式承载包

- `neotrade3/cycle_intelligence/contracts.py`
- `neotrade3/cycle_intelligence/assembler.py`
- `neotrade3/cycle_intelligence/__init__.py`
- `neotrade3/decision_engine/contracts.py`
- `neotrade3/decision_engine/assembler.py`
- `neotrade3/decision_engine/__init__.py`

### 4.2 引擎接线层

- `lowfreq_engine_v16_advanced.py`

当前已落地但尚未提交的 formal front 接线包括：

- formal `M1 -> M2/M3` 构建入口导入
- `generate_buy_signals()` 增加 `formal`
- 单个 candidate 增加 `formal`
- formal 构建失败显式暴露 `status=error`

### 4.3 API 投影层

- `apps/api/main.py`

当前已落地但尚未提交的投影包括：

- `_lowfreq_formal_front_projection(...)`
- `signal_memory` 写入 `formal_front`
- `lowfreq_score_sync_state()` 写入 `formal_front`
- `next_candidates` 写入 `formal_front`
- workbench 在可用时优先消费 `formal_front`
- hot sectors snapshot 透传已有 `formal_front`

### 4.4 report 脚本消费层

- `scripts/generate_lowfreq_top200_attribution_report.py`

当前已落地但尚未提交的 report 消费切换包括：

- `_signal_layer_snapshot(...)` 增加 `formal` 优先兼容翻译
- 在存在 formal 时优先回填：
  - `candidate_tier`
  - `entry_ready`
- 同时保留 `formal_front` 给后续章节读取

### 4.5 测试层

- `tests/unit/test_m2_m3_contract_skeleton.py`
- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `tests/unit/test_lowfreq_intent_conflicts.py`
- `tests/unit/test_lowfreq_formal_front_projection.py`
- `tests/unit/test_lowfreq_workbench_formal_consumption.py`
- `tests/unit/test_lowfreq_phase5_projection_sync.py`

## 5. git 现状

### 5.1 已提交部分

当前唯一已提交的本轮代码提交是：

- `8ba2f84`
- `feat(m2-m3): add formal front contracts and assemblers`

该提交只包含：

- `neotrade3/cycle_intelligence/*`
- `neotrade3/decision_engine/*`
- `tests/unit/test_m2_m3_contract_skeleton.py`

### 5.2 尚未提交但已实现的部分

当前 working tree 中已完成但未提交的内容包括：

- `lowfreq_engine_v16_advanced.py` 中的 formal front 接线
- `apps/api/main.py` 中的 formal front 压缩投影
- `apps/api/main.py` 中的 workbench / hot sectors formal front 优先消费
- `scripts/generate_lowfreq_top200_attribution_report.py` 中的 formal 优先快照层
- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py` 中的 formal 引擎测试
- `tests/unit/test_lowfreq_intent_conflicts.py` 中的 formal score 投影测试
- `tests/unit/test_lowfreq_formal_front_projection.py`
- `tests/unit/test_lowfreq_workbench_formal_consumption.py`
- `tests/unit/test_lowfreq_phase5_projection_sync.py`

### 5.3 为什么没有继续提交 `Commit B / C`

原因不是“忘了提交”，而是已经核实出真实耦合：

1. `lowfreq_engine_v16_advanced.py` 当前 diff 不只包含 formal front
2. 关键 hunk 已与既有未提交的信号结构改造发生真实耦合
3. 若继续强拆，会把本轮之外的改动误带入提交
4. 因此当前已经明确冻结策略：
   - 保留 `Commit A`
   - 不再假装把 `Commit B` 切成纯净窄提交

## 6. 当前运行语义

### 6.1 formal front 的引擎输出

当前实现态下，lowfreq 引擎的 `generate_buy_signals()` 已可并行挂出：

- `formal.small_cycle`
- `formal.identify_state`
- `formal.tracking_state`
- `formal.entry_state`
- `formal.m1_constraints_ref`

失败时返回：

- `formal.status = error`
- `formal.error_type = formal_projection_failed`
- `formal.message = ...`

### 6.2 API 当前做的事

当前 API 不二次生成 formal 语义，只做压缩投影：

- 成功态压缩出：
  - `small_cycle.cycle_state`
  - `small_cycle.state_stability_level`
  - `identify_state.status/reason`
  - `tracking_state.status/maturity/transition_reason`
  - `entry_state.status/decision/actionable/blocking_reasons`
  - `m1_constraints.blocked/blocking_reasons/profile_window_ready`
- 失败态保留：
  - `status`
  - `error_type`
  - `message`

### 6.3 workbench 当前做的事

当前 workbench 相关消费面已经切到：

- `formal_front` 可用时优先
- 旧字段兜底

当前已切到 `formal_front` 优先的直接消费点包括：

- 热点板块代表股状态
- `tracking_list` 的 `tracking_stage / tracking_status`

### 6.4 report 当前做的事

当前 top200 attribution report 不重写章节结构，只在快照层切换：

- `formal` 可用时优先回填兼容字段
- `candidate_tier / entry_ready` 不再只依赖旧字段
- 无 formal 时继续按旧字段兜底

## 7. 已有验证

当前最近一次最小验证结果：

- `python3 -m pytest -q tests/unit/test_m2_m3_contract_skeleton.py tests/unit/test_lowfreq_engine_v16_signal_convergence.py tests/unit/test_lowfreq_intent_conflicts.py tests/unit/test_lowfreq_formal_front_projection.py tests/unit/test_lowfreq_workbench_formal_consumption.py tests/unit/test_lowfreq_phase5_projection_sync.py`
  - `73 passed`
- `python3 -m py_compile ...`
  - 已通过本轮涉及文件的最小语法校验

## 8. 新会话续接建议

如果新会话继续推进本条实现链，建议顺序如下：

1. 先读：
   - `CLAUDE.md`
   - `PROJECT_STATUS.md`
   - 本文件
2. 再读：
   - `docs/superpowers/specs/2026-07-07-m2-m3-minimal-consumption-switch-design.md`
   - `docs/superpowers/specs/2026-07-07-m2-m3-minimal-consumption-switch-plan.md`
   - `docs/handoffs/2026-07-07_m1_phase1_formal_objects_handoff.md`
3. 接着先确认当前目标是：
   - 继续基于 working tree 推进
   - 还是先处理 dirty files 的边界与后续提交策略
4. 不要在未重新确认的情况下做以下动作：
   - 强拆 `Commit B`
   - 把 `hold/exit` 偷带进本轮
   - 把 workbench/report 的最小消费切换误表述成“已经完成全量迁移”

## 9. 一句话提醒

当前最重要的事实不是“已经提交完”，而是：

- `M2/M3` 前半段 formal 消费切换已经在代码层面落地并验证通过
- 但 git 提交态只停在 `Commit A`
- 后续继续时，必须始终区分“已提交对象层”和“working tree 中的引擎/API 接线层”
