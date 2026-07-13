Status: active
Owner: lowfreq / governance
Scope: Implementation plan for the narrow `M5 governance status transition baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Governance Status Transition Baseline Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-governance-status-transition-baseline-design.md`

## 1. Goal

This slice only introduces the minimum reject-driven effective-state projection inside `M5 governance`.

This slice must:

- read one persisted governance handoff bundle by `source_run_id`
- require one persisted reject execution proof by `validation_id`
- deterministically backtrack from `validation_id` to:
  - one `PromotionBlocker`
  - one `AttentionItem`
- materialize one independent status transition artifact and ledger under `validation_id`
- persist effective state with:
  - `AttentionItem.status = "resolved"`
  - `PromotionBlocker.active = true`

This slice explicitly does not:

- overwrite `governance_handoff` artifacts
- rerun reject execution
- change worker, CLI, or orchestration behavior
- implement promotion approval
- introduce a broader governance workflow engine
- touch `M6`

## 2. File Boundary

Spec files:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-governance-status-transition-baseline-design.md`
- `docs/superpowers/specs/2026-07-13-lowfreq-m5-governance-status-transition-baseline-plan.md`

Production files:

- `neotrade3/governance/contracts.py`
- `neotrade3/governance/artifact_writer.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/runtime.py`
- `neotrade3/governance/__init__.py`

Focused test file:

- `tests/unit/test_m5_governance_status_transition.py`

Files intentionally not modified:

- `neotrade3/governance/handoff.py`
- `neotrade3/governance/cli.py`
- `apps/worker/main.py`
- `neotrade3/orchestration/*`
- `M6`

## 3. Execution Steps

### M5ST-S1: Add transition artifact writer

Modify:

- `neotrade3/governance/artifact_writer.py`

Implementation:

1. add one narrow artifact metadata record for status transitions
2. add one writer for:
   - `var/artifacts/governance_status_transitions/<validation_id>/governance_status_transition.json`
3. artifact payload must include:
   - `source_run_id`
   - `validation_id`
   - `decision_id`
   - `baseline_run_id`
   - `candidate_run_id`
   - `trigger_artifact_path`
   - `effective_attention_item`
   - `effective_promotion_blocker`
   - `written_at`

Implementation rules:

- `effective_attention_item` is a copied payload with effective `status="resolved"`
- `effective_promotion_blocker` is a copied payload with effective `active=true`
- do not mutate or rewrite the original persisted handoff payload

### M5ST-S2: Add transition ledger helpers

Modify:

- `neotrade3/governance/run_ledger.py`

Implementation:

1. add one `GovernanceStatusTransitionRecord`
2. add read/materialize helpers for:
   - `var/ledgers/governance_status_transitions/<validation_id>/governance_status_transition_run.json`
3. keep all existing handoff and reject execution helpers unchanged

Ledger payload must include:

- `validation_id`
- `source_run_id`
- `decision_id`
- `status`
- `written_at`
- `artifact_path`
- `ledger_path`
- `baseline_run_id`
- `candidate_run_id`
- `effective_attention_id`
- `effective_attention_status`
- `effective_blocker_id`
- `effective_blocker_active`

Implementation rules:

- keep the record keyed by `validation_id`
- do not infer values from directory names alone
- do not widen the existing reject execution ledger schema

### M5ST-S3: Add runtime owner

Modify:

- `neotrade3/governance/runtime.py`

Implementation:

1. add one runtime entrypoint:
   - `run_governance_status_transition(...)`
2. runtime flow:
   - read typed handoff bundle by `source_run_id`
   - require persisted reject execution proof by `validation_id`
   - locate one matching `ValidationResult`
   - backtrack through:
     - `experiment_id`
     - `cr_id`
     - `diagnostic_id`
     - `blocker_id`
     - `attention_id`
   - locate exactly one matching blocker and attention item in the handoff bundle
   - materialize the independent transition artifact and ledger

Implementation rules:

- fail if reject execution proof does not exist
- fail if the mapped blocker or attention item does not exist
- fail if duplicate matches make the mapping ambiguous
- do not patch `governance_handoff`
- do not call `run_governance_reject_execution(...)`

### M5ST-S4: Export the new owner surface

Modify:

- `neotrade3/governance/__init__.py`
- `neotrade3/governance/contracts.py`

Implementation:

1. export the new typed transition record and helpers that belong on the public `governance` package surface
2. keep the export change minimal and aligned with current `M5` style

Implementation rule:

- do not introduce a new top-level namespace or package directory in this slice

### M5ST-S5: Add focused tests

Create:

- `tests/unit/test_m5_governance_status_transition.py`

Test carrier pattern:

- materialize a real governance handoff under a temp project root
- inject one rejected validation result into the persisted handoff artifact
- run the existing reject execution runtime
- run the new status transition runtime
- assert transition artifact and ledger behavior against persisted truth

Required coverage:

1. one persisted reject execution materializes one independent status transition artifact
2. one persisted reject execution materializes one independent status transition ledger
3. the original handoff artifact remains unchanged after transition execution
4. the effective attention payload is persisted with `status="resolved"`
5. the effective blocker payload is persisted with `active=true`
6. dry-run writes nothing
7. missing reject execution proof fails deterministically
8. missing mapped blocker fails deterministically
9. missing mapped attention item fails deterministically

Testing rules:

- do not widen into worker or CLI assertions
- do not retest reject runtime semantics beyond what is needed to seed the transition proof

### M5ST-S6: Minimum verification

Run at minimum:

- `python3 -m py_compile neotrade3/governance/contracts.py neotrade3/governance/artifact_writer.py neotrade3/governance/run_ledger.py neotrade3/governance/runtime.py neotrade3/governance/__init__.py tests/unit/test_m5_governance_status_transition.py`
- `python3 -m pytest tests/unit/test_m5_governance_status_transition.py tests/unit/test_m5_governance_reject_execution.py`
- `git diff --check`

## 4. Risks And Guardrails

- **Risk: accidentally overwrite baseline truth**
  - Guardrail: use only `governance_status_transitions/<validation_id>` namespace
- **Risk: infer status transitions without persisted reject proof**
  - Guardrail: require an existing reject execution artifact or ledger before transition runtime succeeds
- **Risk: break deterministic ID-chain mapping**
  - Guardrail: fail directly on missing or ambiguous blocker/attention lookup
- **Risk: widen into operational adoption too early**
  - Guardrail: keep all changes inside `governance` plus one focused test file

## 5. Done Criteria

- independent status transition artifact exists
- independent status transition ledger exists
- runtime owner exists
- persisted handoff artifact remains unchanged
- effective attention state is `resolved`
- effective blocker state remains `active=true`
- focused tests pass
- no `worker/CLI/orchestrator/M6` file changes appear in the diff

## 6. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays entirely inside `M5` reject-driven effective-state projection
- `G1-G6` target mapping:
  - this is the minimum `G5` step that makes post-reject effective state explicit and persisted
- new runtime contract introduced:
  - independent transition artifact and ledger keyed by `validation_id`
  - effective attention projection with `status="resolved"`
  - effective blocker projection with `active=true`
- boundaries not touched:
  - no handoff overwrite
  - no promotion approval
  - no worker/CLI/orchestrator adoption
  - no `M6`
