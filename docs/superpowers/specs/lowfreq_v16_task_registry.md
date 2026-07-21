Status: Active
Owner: TBD
Scope: lowfreq_v16_model_rulebook
Canonical: Yes
Supersedes:
Superseded_by:
Last_reviewed: 2026-07-19

# LowFreq v16 Task Registry（任务注册表）

本文件用于同步“开发计划/进度”与 rulebook 的契约注册表（RB.*）。

规则：

- 每条任务必须包含：`id`、`status`、`rb_ids`、`evidence`
- `status` ∈ todo / doing / done
- done：evidence 路径必须存在，且任务关联的 rb_ids 中至少包含一个 `status=implemented` 的条目
- todo/doing：允许 evidence 指向设计文档或 rulebook（说明），但不得宣称已完成

条目：

- TASK.LF16.STEP1.WAVE_PHASE status=done rb_ids=RB.M2.STEP1.WAVE_PHASE.001,RB.M2.STEP1.WAVE_CONFIDENCE.001,RB.M2.STEP1.EVIDENCE_BUNDLE.001 evidence=tests/unit/test_lowfreq_rulebook_step1_step2_step3_contracts.py
- TASK.LF16.STEP2.CERTAINTY_PATTERN status=done rb_ids=RB.M2.STEP2.CERTAINTY_SCORE.001,RB.M2.STEP2.CERTAINTY_HORIZON.001,RB.M2.STEP2.CERTAINTY_TARGET_RETURN.001,RB.M2.STEP2.PATTERN_EVIDENCE.001,RB.M2.STEP2.EVIDENCE_BUNDLE.001 evidence=tests/unit/test_lowfreq_rulebook_step1_step2_step3_contracts.py
- TASK.LF16.STEP3.TRACKING_POOL status=done rb_ids=RB.M2.STEP3.TRACKING_POOL_CANDIDATES.001 evidence=tests/unit/test_lowfreq_engine_v16_signal_convergence.py
- TASK.LF16.STEP4.ENTRY_WINDOW status=done rb_ids=RB.M3.STEP4.ENTRY_WINDOW.001 evidence=tests/unit/test_lowfreq_formal_front_projection.py
- TASK.LF16.M3.HAZARD_SCORE_STATE status=done rb_ids=RB.M3.HAZARD.PREDICTOR_V0.001,RB.M3.HAZARD.SNAPSHOT.001,RB.M3.HAZARD.SCORE_FIELDS.001,RB.M3.HAZARD.STATE_FIELD.001 evidence=tests/unit/test_hazard_predictor_v0_t2.py
- TASK.LF16.STEP5_HOLD_EXIT_CORE status=done rb_ids=RB.M3.STEP5.HOLD_NOISE_FILTER_STATE.001,RB.M3.STEP5.EXIT_SIGNAL.001,RB.M3.STEP6.RISK_ACTION.001,RB.M3.STEP6.STOP_LOSS.001 evidence=tests/unit/test_lowfreq_engine_v16_sell_logic.py,tests/unit/test_lowfreq_engine_v16_position_contract_snapshot.py
- TASK.LF16.STEP7.DISCIPLINE status=done rb_ids=RB.M3.STEP7.TRADE_DISCIPLINE_METRICS.001,RB.M3.STEP7.DISCIPLINE_GUARD.001,RB.M3.STEP7.DISCIPLINE_AUDIT.001 evidence=tests/unit/test_lowfreq_engine_v16_trade_discipline.py
- TASK.LF16.STEP8.EVAL_GOVERNANCE status=done rb_ids=RB.M4.STEP8.QUALITY_REPORT.001,RB.M5.STEP8.ADJUSTMENT_PROPOSAL.001,RB.M5.STEP8.GOVERNANCE_DECISION_LOG.001,RB.M4.CH4.EVAL_TRIGGER_INPUTS.001,RB.M4.CH4.EVAL_OUTPUTS.001,RB.M5.CH4.PROPOSAL_CONTRACT.001,RB.M5.CH4.GOVERNANCE_VERDICT.001,RB.M5.CH4.ADJUSTMENT_APPLICATION_RECORD.001 evidence=tests/unit/test_step8_eval_governance_v0.py
- TASK.LF16.M3.CHAOS_SNAPSHOT status=todo rb_ids=RB.M3.CHAOS.SNAPSHOT.001 evidence=docs/superpowers/specs/2026-07-20-chaos-model-design.md,docs/superpowers/specs/2026-07-20-chaos-model-implementation-plan.md,docs/superpowers/specs/2026-07-20-chaos-model-task-list.md
- TASK.LF16.M4.CHAOS_EVAL_MONITOR status=todo rb_ids=RB.M4.CHAOS.EVAL_MONITOR.001 evidence=docs/superpowers/specs/2026-07-20-chaos-model-design.md,docs/superpowers/specs/2026-07-20-chaos-model-implementation-plan.md,docs/superpowers/specs/2026-07-20-chaos-model-task-list.md
- TASK.LF16.M5.CHAOS_GOVERNANCE status=todo rb_ids=RB.M5.CHAOS.GOVERNANCE.001 evidence=docs/superpowers/specs/2026-07-20-chaos-model-design.md,docs/superpowers/specs/2026-07-20-chaos-model-implementation-plan.md,docs/superpowers/specs/2026-07-20-chaos-model-task-list.md
