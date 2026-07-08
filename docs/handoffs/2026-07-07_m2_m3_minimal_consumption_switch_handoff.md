# 2026-07-07 M2/M3 最小消费切换 Handoff

## 1. 这份文档的用途

本 handoff 只服务于 `M2/M3` 前半段最小正式消费切换的实现态续接。

目标：

- 让新会话直接恢复当前 `M2/M3` formal front 的真实实现状态
- 明确哪些内容已经落地到代码
- 明确哪些 formal-front 切片已经进入提交历史
- 明确当前 remaining working tree 不应再被笼统表述成“formal-front 尚未提交”

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

当前已进入提交历史的 formal front / related engine 切片包括：

- `4c416e6 refactor(engine): add lowfreq signal structure baseline`
- `3c9393b feat(engine): wire lowfreq formal front chain`
- `a160796 feat(engine): expose lowfreq execution result summary`
- `1ccb680 fix(engine): clamp invalid lowfreq annual return`
- `0c39ca6 fix(engine): honor strong leader soft release flag`
- `9ea8f33 feat(engine): enrich lowfreq execution audit events`

### 4.3 API 投影层

- `apps/api/main.py`

当前已进入提交历史的 API / workbench formal-front 切片包括：

- `05d5c46 fix(api): enforce formal priority in lowfreq workbench`
- `1b6e5ad feat(api): carry lowfreq formal front into hot sectors`
- `30723fa feat(api): persist lowfreq formal front in signal memory`
- `de8d08c feat(api): project lowfreq formal front into score pool`
- `7a097c5 fix(api): add lowfreq formal front status helpers`
- `8c36629 feat(api): project lowfreq formal front into next candidates`

### 4.4 report 脚本消费层

- `scripts/generate_lowfreq_top200_attribution_report.py`

当前与 report/formal-front 直接相关、已进入历史的切片包括：

- `753ede8 refactor(m3): extract shared lowfreq formal front projection`
- `fb0a629 refactor(report): split candidate and entry attribution flow`

当前 handoff 应以此为准：report 侧 formal-front 最小消费切换已在 `HEAD`，不再属于“working tree 待提交”事项。

### 4.5 测试层

- `tests/unit/test_m2_m3_contract_skeleton.py`
- `tests/unit/test_lowfreq_engine_v16_signal_convergence.py`
- `tests/unit/test_lowfreq_intent_conflicts.py`
- `tests/unit/test_lowfreq_formal_front_projection.py`
- `tests/unit/test_lowfreq_workbench_formal_consumption.py`
- `tests/unit/test_lowfreq_phase5_projection_sync.py`

## 5. git 现状

### 5.1 已提交部分

当前已确认进入历史的 formal-front 主线提交包括：

- `8ba2f84`
- `feat(m2-m3): add formal front contracts and assemblers`
- `4c416e6 refactor(engine): add lowfreq signal structure baseline`
- `3c9393b feat(engine): wire lowfreq formal front chain`
- `a160796 feat(engine): expose lowfreq execution result summary`
- `1ccb680 fix(engine): clamp invalid lowfreq annual return`
- `0c39ca6 fix(engine): honor strong leader soft release flag`
- `9ea8f33 feat(engine): enrich lowfreq execution audit events`
- `05d5c46 fix(api): enforce formal priority in lowfreq workbench`
- `1b6e5ad feat(api): carry lowfreq formal front into hot sectors`
- `30723fa feat(api): persist lowfreq formal front in signal memory`
- `de8d08c feat(api): project lowfreq formal front into score pool`
- `7a097c5 fix(api): add lowfreq formal front status helpers`
- `8c36629 feat(api): project lowfreq formal front into next candidates`
- `753ede8 refactor(m3): extract shared lowfreq formal front projection`
- `fb0a629 refactor(report): split candidate and entry attribution flow`

### 5.2 当前 remaining working tree 的正确表述

当前仍可能存在其他未审计脏改动，但不能再把它们笼统记为：

- “formal-front 主线仍只在 working tree”
- “Commit B / C 尚未提交”

更准确的口径应是：

1. formal-front 主线已经通过多段窄提交收口
2. 当前 working tree 的剩余内容需要按实时 diff 重新审计
3. 新会话不得继续沿用“API/report formal-front 尚未提交”的旧判断

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

当前已知验证证据分两类：

- formal-front 主线落地期的聚合验证：
  - `python3 -m pytest -q tests/unit/test_m2_m3_contract_skeleton.py tests/unit/test_lowfreq_engine_v16_signal_convergence.py tests/unit/test_lowfreq_intent_conflicts.py tests/unit/test_lowfreq_formal_front_projection.py tests/unit/test_lowfreq_workbench_formal_consumption.py tests/unit/test_lowfreq_phase5_projection_sync.py`
  - `73 passed`
- API 切片与后续 test-only 审计期的定向验证：
  - `python3 -m pytest -q tests/unit/test_lowfreq_intent_conflicts.py tests/unit/test_lowfreq_workbench_formal_consumption.py tests/unit/test_lowfreq_workbench_formal_priority.py tests/unit/test_lowfreq_score_pool_formal_front.py`
  - `30 passed`
- `python3 -m py_compile ...`
  - 已通过相关轮次涉及文件的最小语法校验

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
   - 先更新/核对 handoff 与 repo 实时状态
   - 再审计当前 dirty files 的真实边界与后续提交策略
4. 不要在未重新确认的情况下做以下动作：
   - 把旧 handoff 中“API/report formal-front 尚未提交”继续当成事实
   - 把 `hold/exit` 偷带进本轮
   - 把 workbench/report 的最小消费切换误表述成“已经完成全量迁移”

## 9. 一句话提醒

当前最重要的事实是：

- `M2/M3` 前半段 formal-front 主线已经在代码层面落地、验证，并通过多段窄提交进入历史
- 当前真正需要谨慎处理的是 remaining working tree 的实时边界，而不是重复处理已经落地的 API/report formal-front 切片
