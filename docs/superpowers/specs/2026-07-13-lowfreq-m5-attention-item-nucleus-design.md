Status: active
Owner: lowfreq / governance
Scope: Narrow `M5 governance AttentionItem nucleus` slice for formal contract and builder introduction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 AttentionItem Nucleus Design

Date: 2026-07-13

## 1. Goal

This slice is the next truthful step after:

- `M5 governance contract nucleus`
- `M5 governance pending closure baseline`

Current repository evidence shows:

- `Attention Item` is already frozen in architecture as a first-class governance object
- `M5 evolution controller` design explicitly lists it as `G2`
- current `governance` code still has no:
  - object constant
  - dataclass
  - pure builder
  - package export
  - contract-focused tests
- the just-finished `M5 closure baseline` explicitly excluded attention runtime

So the narrow problem is not:

- how to build attention queue runtime
- how to project attention items into handoff or ledger
- how to build promotion approval logic
- how to add `M6` delivery projections

It is:

- how to introduce `AttentionItem` as a formal `M5` governance contract
- how to do that in the same code style as existing `M5` objects
- how to keep the slice small enough that later runtime adoption stays truthful

Project-phase note:

- domain: `M5 governance object nucleus`
- change type: `contract/builder nucleus`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G2`

## 2. Scope

Included:

- add `ATTENTION_ITEM_OBJECT_TYPE`
- add `AttentionItem` dataclass
- add `build_attention_item(...)`
- export the new object and builder from `governance.__init__`
- add focused contract/builder tests

Excluded:

- no handoff integration
- no artifact persistence
- no ledger count
- no CLI output
- no orchestrator changes
- no `M6`

## 3. Existing Evidence

### 3.1 Attention Item Is Already Architecturally Frozen

Current repository evidence in:

- [2026-07-07-m5-evolution-controller-design.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-07-m5-evolution-controller-design.md#L178-L240)
- [2026-07-06-quant-model-top-level-architecture-design.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-06-quant-model-top-level-architecture-design.md#L401-L449)

shows that:

- `Attention Item` is a formal governance object
- `M5` is its primary generator
- top-level minimum field set is already defined

### 3.2 Governance Code Still Lacks Any AttentionItem Implementation

Current repository evidence in:

- [contracts.py](file:///Users/mac/NeoTrade3/neotrade3/governance/contracts.py#L9-L248)
- [assembler.py](file:///Users/mac/NeoTrade3/neotrade3/governance/assembler.py)
- [__init__.py](file:///Users/mac/NeoTrade3/neotrade3/governance/__init__.py#L1-L95)

shows that current `M5` code only implements:

- `DiagnosticChain`
- `ChangeRequest`
- `ExperimentRequest`
- `ValidationResult`
- `PromotionBlocker`
- `GovernanceDecisionRecord`

There is no `AttentionItem` code yet.

### 3.3 M1 AttentionItem Exists But Is Not The Same Object

Current repository evidence in:

- [quality.py](file:///Users/mac/NeoTrade3/neotrade3/data_control/quality.py#L57-L108)

shows that `M1AttentionItem` already exists, but it is:

- owned by `data_control`
- much smaller in field surface
- not the same contract as `M5 governance AttentionItem`

So this slice must not alias `M1AttentionItem` into `M5`.

### 3.4 Current Closure Baseline Explicitly Excludes Attention Runtime

Current repository evidence in:

- [2026-07-13-lowfreq-m5-governance-closure-baseline-design.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-13-lowfreq-m5-governance-closure-baseline-design.md#L57-L76)

freezes that current closure baseline does not add attention runtime.

So the next truthful step is nucleus only, not runtime adoption.

## 4. Approach Options

### Option A: Jump Straight To Attention Runtime

Pros:

- faster visible closure

Cons:

- introduces new runtime shape before a formal contract exists
- risks coupling handoff/ledger/CLI to an undefined object

### Option B: Add AttentionItem Nucleus First (Recommended)

Pros:

- matches how `M5` object family was built so far
- keeps the slice narrow and testable
- gives later runtime adoption one canonical owner

Cons:

- does not yet expose attention items in artifacts or CLI

### Option C: Reuse M1AttentionItem Inside Governance

Pros:

- smaller code diff

Cons:

- wrong owner
- wrong field surface
- creates cross-layer semantic drift

Decision:

- choose Option B

## 5. Design

### 5.1 Ownership Freeze

This slice introduces the formal `M5` attention object only.

Primary owners:

- `neotrade3/governance/contracts.py`
- `neotrade3/governance/assembler.py`
- `neotrade3/governance/__init__.py`

Focused test owner:

- `tests/unit/test_m5_governance_contract_nucleus.py`

Files intentionally not modified:

- `neotrade3/governance/handoff.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/cli.py`
- `neotrade3/orchestration/*`
- `M6`

### 5.2 Field Freeze

To match current `M5` naming style while honoring top-level architecture minimum fields, `AttentionItem` should use:

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

Plus standard `M5` envelope fields:

- `object_type`
- `object_version`

Design rules:

- use `attention_id`, not bare `id`, to align with current governance naming style such as `diagnostic_id`, `cr_id`, `experiment_id`
- map architecture field `evidence` onto current codebase convention `evidence_refs`
- use text fields for `source`, `status`, `owner`, and `blocking_scope`

### 5.3 Builder Freeze

Introduce one pure builder:

- `build_attention_item(...)`

Validation rules:

- all text fields above are required and non-empty
- `human_action_required` is coerced to bool
- `evidence_refs` uses the same list-of-dict normalization pattern as other governance builders

This slice intentionally does not add:

- builder-from-diagnostic helper
- builder-from-blocker helper
- runtime creation helper

Reason:

- those helpers imply ownership over runtime routing that is not yet frozen

### 5.4 Status And Classification Freeze

This slice does not introduce enums or hardcoded category matrices.

Contract rules:

- `issue_type`
- `severity`
- `automation_class`
- `status`
- `blocking_scope`

are treated as required text, but their controlled vocabulary remains a later slice.

Reason:

- current architecture defines categories conceptually, but current codebase does not yet freeze the exact runtime taxonomy for `M5 AttentionItem`
- forcing enums now would create guesswork

## 6. Testing Strategy

Focused tests should lock:

1. `AttentionItem.to_payload()` is stable and defensively copied
2. `build_attention_item(...)` preserves all fields
3. empty required ids/text fields are rejected
4. `evidence_refs` is normalized the same way as other governance builders

Testing rule:

- do not widen into runtime tests
- do not widen into handoff/ledger/CLI tests in this slice

## 7. Risks And Guardrails

### 7.1 Cross-Layer Aliasing Risk

The main risk is reusing `M1AttentionItem` as if it were the `M5` governance object.

Guardrail:

- `M5` gets its own contract and builder
- no imports from `data_control.quality` into `governance`

### 7.2 Premature Taxonomy Freeze Risk

Another risk is hardcoding category enums without enough evidence.

Guardrail:

- current nucleus only requires non-empty text
- later slices can freeze controlled vocabularies once runtime routing is designed

### 7.3 Runtime Drift Risk

Another risk is introducing handoff/runtime coupling in the same slice.

Guardrail:

- this slice stops at contract/builder/export/test

## 8. Acceptance Criteria

This slice is complete only when all of the following are true:

- `AttentionItem` exists as a formal governance contract
- `build_attention_item(...)` exists as a pure builder
- package exports include the new object and builder
- focused contract tests pass
- no runtime, handoff, ledger, or CLI code is changed

## 9. Out Of Scope Follow-Ups

This slice intentionally leaves for later:

- attention item runtime generation from diagnostics/blockers
- attention item inclusion in handoff bundle
- attention item persistence and ledger counts
- attention queue delivery in `M6`
- promotion approval runtime

## 10. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays entirely in `M5` object nucleus and does not project into runtime or delivery layers
- `G1-G6` target mapping:
  - this is the minimum `G2` object-definition step required before any truthful attention runtime can exist
- new contract introduced:
  - `AttentionItem`
  - `ATTENTION_ITEM_OBJECT_TYPE`
  - `build_attention_item(...)`
- boundaries not touched:
  - no runtime adoption
  - no persistence
  - no `M6`
