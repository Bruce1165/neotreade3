Status: active
Owner: lowfreq / governance
Scope: Implementation plan for the narrow `M5 governance AttentionItem nucleus` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 AttentionItem Nucleus Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-attention-item-nucleus-design.md`

## 1. Goal

This slice only introduces the formal `M5 AttentionItem` object nucleus.

This slice must:

- add `ATTENTION_ITEM_OBJECT_TYPE`
- add `AttentionItem`
- add `build_attention_item(...)`
- export them through `governance.__init__`
- lock the contract with focused tests

This slice explicitly does not:

- add runtime generation helpers
- add handoff integration
- add artifact or ledger persistence
- add CLI output
- touch `M6`

## 2. Starting Point

Repository evidence before implementation:

- `Attention Item` is already frozen in architecture and `M5` design docs
- `governance` code still lacks any attention contract/builder
- `M1AttentionItem` exists but is a different owner and a different field surface
- current closure baseline explicitly excludes attention runtime

So the correct narrow move is:

- land the canonical `M5` contract and builder first
- keep the slice strictly inside the contract nucleus layer

## 3. File Boundary

Production files:

- `neotrade3/governance/contracts.py`
- `neotrade3/governance/assembler.py`
- `neotrade3/governance/__init__.py`

Focused test file:

- `tests/unit/test_m5_governance_contract_nucleus.py`

Files intentionally not modified:

- `neotrade3/governance/handoff.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/cli.py`
- `neotrade3/orchestration/*`
- `M6`

## 4. Execution Steps

### M5AI-S1: Add AttentionItem contract

Modify:

- `neotrade3/governance/contracts.py`

Implementation:

1. add `ATTENTION_ITEM_OBJECT_TYPE`
2. add `AttentionItem` dataclass with:
   - `attention_id`
   - `created_at`
   - `source`
   - `target_layer`
   - `issue_type`
   - `severity`
   - `automation_class`
   - `evidence_refs`
   - `recommended_action`
   - `human_action_required`
   - `status`
   - `owner`
   - `blocking_scope`
3. implement `to_payload()` using the same defensive copy pattern as other governance contracts

Implementation rule:

- keep `evidence_refs` as list-of-dict payloads
- do not add runtime-only fields

### M5AI-S2: Add pure builder

Modify:

- `neotrade3/governance/assembler.py`

Implementation:

1. add `build_attention_item(...)`
2. require all text fields to be non-empty
3. normalize `evidence_refs` with the same helper used by other governance builders
4. coerce `human_action_required` to bool

Implementation rule:

- do not add builder-from-diagnostic or builder-from-blocker helpers in this slice

### M5AI-S3: Export the new nucleus

Modify:

- `neotrade3/governance/__init__.py`

Implementation:

1. export `ATTENTION_ITEM_OBJECT_TYPE`
2. export `AttentionItem`
3. export `build_attention_item`

### M5AI-S4: Lock with focused contract tests

Modify:

- `tests/unit/test_m5_governance_contract_nucleus.py`

Required coverage:

1. payload is stable and defensively copied
2. builder preserves all fields
3. empty required fields are rejected
4. `human_action_required` is stored as bool
5. `evidence_refs` normalization matches existing governance builder behavior

Testing rule:

- do not widen into runtime, handoff, ledger, or CLI tests

### M5AI-S5: Minimum verification

Run at minimum:

- `python3 -m py_compile neotrade3/governance/contracts.py neotrade3/governance/assembler.py neotrade3/governance/__init__.py tests/unit/test_m5_governance_contract_nucleus.py`
- `python3 -m pytest tests/unit/test_m5_governance_contract_nucleus.py`
- `git diff --check`

## 5. Risks And Guardrails

- **Risk: alias M1AttentionItem into M5**
  - Guardrail: define a new `M5` contract locally in `governance`
- **Risk: premature taxonomy freeze**
  - Guardrail: classification fields are required text only, no enum system yet
- **Risk: runtime creep**
  - Guardrail: no changes outside `contracts/assembler/__init__/contract test`

## 6. Done Criteria

This slice is done only when all of the following are true:

- `AttentionItem` exists in `governance.contracts`
- `build_attention_item(...)` exists in `governance.assembler`
- package exports include the new object and builder
- focused contract tests pass
- no runtime, handoff, ledger, or CLI files are modified

## 7. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays entirely in `M5` object nucleus and does not cross into runtime or delivery layers
- `G1-G6` target mapping:
  - this is the minimum `G2` contract-definition step before any truthful attention runtime can exist
- new contract introduced:
  - `ATTENTION_ITEM_OBJECT_TYPE`
  - `AttentionItem`
  - `build_attention_item(...)`
- boundaries not touched:
  - no runtime generation
  - no persistence
  - no `M6`
