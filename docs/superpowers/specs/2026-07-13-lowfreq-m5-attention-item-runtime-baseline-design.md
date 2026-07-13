Status: active
Owner: lowfreq / governance
Scope: Narrow `M5 governance AttentionItem runtime baseline` slice for handoff, ledger, runtime, and CLI projection
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 AttentionItem Runtime Baseline Design

Date: 2026-07-13

## 1. Goal

This slice is the next truthful step after:

- `M5 governance pending closure baseline`
- `M5 governance AttentionItem nucleus`

Current repository evidence shows:

- `AttentionItem` now exists as a formal `M5` contract and pure builder
- the `M5` runtime mainline still does not carry any `attention_items`
- current handoff, persisted artifact, ledger summary, worker task details, and CLI output all omit that object
- the just-finished nucleus slice explicitly stopped before runtime adoption

So the narrow problem is not:

- how to invent a full attention queue runtime
- how to freeze taxonomy enums for issue classes and statuses
- how to execute promotion or reject actions
- how to expose attention delivery in `M6`

It is:

- how to let the already-defined `AttentionItem` truthfully enter the `M5` runtime mainline
- how to do so through the existing `handoff -> artifact/ledger -> runtime/CLI` chain
- how to keep the source mapping narrow enough that later routing remains truthful

Project-phase note:

- domain: `M5 governance runtime mainline`
- change type: `runtime/handoff materialization baseline`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G2`

## 2. Scope

Included:

- add `attention_items` to `GovernanceHandoffBundle`
- project one minimal `AttentionItem` for each active `PromotionBlocker`
- persist `attention_items` through the governance handoff artifact
- add `attention_item_count` to governance ledger, worker task details, and CLI output
- add focused handoff/ledger/runtime/CLI tests

Excluded:

- no new `AttentionItem` contract or builder work
- no diagnostic-to-attention routing matrix beyond the minimal blocker projection
- no approval or reject execution path
- no orchestrator contract expansion
- no `M6`

## 3. Existing Evidence

### 3.1 Attention Item Is Already An M5 Architecture Object

Current repository evidence in:

- [2026-07-06-quant-model-top-level-architecture-design.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-06-quant-model-top-level-architecture-design.md#L397-L449)
- [2026-07-07-m5-evolution-controller-design.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-07-m5-evolution-controller-design.md#L178-L240)

shows that:

- `Attention Item` is already frozen as a first-class governance object
- it belongs to `M5` governance, not `M6`
- it is part of the same governance object family as diagnostics, change requests, validation results, and blockers

### 3.2 Nucleus Exists, But Runtime Projection Does Not

Current repository evidence in:

- [contracts.py](file:///Users/mac/NeoTrade3/neotrade3/governance/contracts.py#L162-L197)
- [assembler.py](file:///Users/mac/NeoTrade3/neotrade3/governance/assembler.py#L170-L200)
- [__init__.py](file:///Users/mac/NeoTrade3/neotrade3/governance/__init__.py#L1-L57)
- [test_m5_governance_contract_nucleus.py](file:///Users/mac/NeoTrade3/tests/unit/test_m5_governance_contract_nucleus.py#L168-L250)

shows that `AttentionItem` now has:

- object constant
- dataclass
- pure builder
- package export
- focused contract test coverage

But current runtime chain still has no `attention_items`.

### 3.3 Handoff Is The Real Missing Owner

Current repository evidence in:

- [handoff.py](file:///Users/mac/NeoTrade3/neotrade3/governance/handoff.py#L38-L169)

shows that current `GovernanceHandoffBundle` carries:

- `diagnostics`
- `change_requests`
- `experiment_requests`
- `validation_results`
- `promotion_blockers`
- `decision_records`

There is no `attention_items` field, so downstream layers cannot truthfully emit or count them.

### 3.4 Ledger, Runtime, Worker, And CLI Still Omit Attention Counts

Current repository evidence in:

- [run_ledger.py](file:///Users/mac/NeoTrade3/neotrade3/governance/run_ledger.py#L17-L138)
- [runtime.py](file:///Users/mac/NeoTrade3/neotrade3/governance/runtime.py#L26-L51)
- [main.py](file:///Users/mac/NeoTrade3/apps/worker/main.py#L307-L345)
- [cli.py](file:///Users/mac/NeoTrade3/neotrade3/governance/cli.py#L39-L76)

shows that:

- ledger counts stop at `decision_record_count`
- runtime only materializes what the handoff bundle already contains
- worker task details omit `attention_item_count`
- CLI output omits `attention_item_count`

So the actual next gap is not contract definition, but mainline projection.

### 3.5 Previous Slices Explicitly Froze This Boundary

Current repository evidence in:

- [2026-07-13-lowfreq-m5-governance-closure-baseline-design.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-13-lowfreq-m5-governance-closure-baseline-design.md#L57-L76)
- [2026-07-13-lowfreq-m5-attention-item-nucleus-design.md](file:///Users/mac/NeoTrade3/docs/superpowers/specs/2026-07-13-lowfreq-m5-attention-item-nucleus-design.md#L62-L69)

freezes that:

- closure baseline did not add attention runtime
- nucleus did not add handoff, persistence, ledger, or CLI adoption

So the next truthful step is runtime baseline, not a larger workflow expansion.

## 4. Approach Options

### Option A: Jump To Full Attention Queue Runtime

Pros:

- more visible end-state progress

Cons:

- requires routing and taxonomy decisions not frozen in current code
- risks coupling `AttentionItem` generation to guessed future workflow

### Option B: Add Minimal Runtime Baseline Through Existing Mainline (Recommended)

Pros:

- reuses the existing `handoff -> materialize -> worker/CLI` chain
- keeps the slice narrow and testable
- introduces no new architecture concept beyond projection of an existing object

Cons:

- does not yet create a rich attention workflow

### Option C: Skip Attention And Move Straight To Promotion/Reject

Pros:

- pushes governance toward execution sooner

Cons:

- leaves an already-frozen object family absent from the mainline
- would make promotion/reject runtime skip an intermediate governance truth source

Decision:

- choose Option B

## 5. Design

### 5.1 Ownership Freeze

This slice introduces minimal `AttentionItem` runtime projection only.

Primary production owners:

- `neotrade3/governance/handoff.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/cli.py`
- `apps/worker/main.py`

Focused test owners:

- `tests/unit/test_m5_governance_handoff_adapter.py`
- `tests/unit/test_m5_governance_run_ledger.py`
- `tests/unit/test_m5_governance_cli.py`
- `tests/unit/test_m5_governance_orchestrator_fit.py`

Files intentionally not modified:

- `neotrade3/governance/contracts.py`
- `neotrade3/governance/assembler.py` except for one thin projection helper if needed
- `neotrade3/governance/runtime.py`
- `neotrade3/orchestration/models.py`
- `M6`

### 5.2 Projection Source Freeze

This slice needs one stable source for `AttentionItem`.

Chosen source:

- project one `AttentionItem` from each active `PromotionBlocker`

Reasons:

- `PromotionBlocker` already exists in the same handoff path
- a blocker is already a governance-level signal that something requires sustained attention
- using blocker-to-attention projection avoids guessing how every diagnostic or change request should map to attention

Design rules:

- one active `PromotionBlocker` yields one `AttentionItem`
- no blocker means no attention item
- the projection is additive and does not change blocker or decision semantics

### 5.3 Attention Projection Freeze

The runtime projection should be thin and deterministic.

Recommended `PromotionBlocker -> AttentionItem` mapping:

- `attention_id` = `"{blocker.blocker_id}:attention"`
- `created_at` = benchmark `trade_date` from the corresponding diagnostic when available; otherwise use the blocker-linked diagnostic trade date already carried in handoff construction
- `source` = `"governance"`
- `target_layer` = `"M5"`
- `issue_type` = `"promotion_blocker"`
- `severity` = blocker severity
- `automation_class` = `"human_review_required"`
- `evidence_refs` = blocker evidence refs
- `recommended_action` = blocker required clearance
- `human_action_required` = `True`
- `status` = `"open"`
- `owner` = `"system_governance"`
- `blocking_scope` = `"promotion"`

This slice intentionally does not freeze a broader taxonomy beyond these concrete values.

### 5.4 Handoff And Persistence Freeze

`GovernanceHandoffBundle` should add:

- `attention_items: tuple[AttentionItem, ...] = ()`

`to_payload()` should include:

- `"attention_items": _copy_payload_list(self.attention_items)`

`build_governance_handoff_from_assessment(...)` should:

- build the diagnostic, change request, experiment request, validation result, promotion blocker, and decision record exactly as before
- additionally build one `AttentionItem` from the same blocker

`build_governance_handoff_from_batch_run(...)` should:

- aggregate `attention_items` in the same stable order as the rest of the object chain

`GovernanceRunLedgerRecord` should add:

- `attention_item_count: int = 0`

and persist it from the handoff bundle object count.

### 5.5 Runtime And Output Freeze

`runtime.py` should stay a thin caller.

No new runtime branch is needed because:

- runtime already materializes whatever the handoff bundle contains

So the user-visible changes happen only in:

- persisted artifact payload
- persisted ledger summary
- worker task `details`
- CLI JSON output

This slice should only add:

- `attention_item_count`

It should not add raw `attention_items` to worker or CLI output, because count is enough for this baseline and avoids widening the external surface too early.

## 6. Testing Strategy

Focused tests should lock:

1. `handoff` projects one `attention_item` for each failing B4 blocker path
2. clean assessments still project zero `attention_items`
3. batch handoff preserves deterministic `attention_items` order
4. ledger persists `attention_item_count`
5. CLI output includes `attention_item_count`
6. worker governance executor details include `attention_item_count`

Testing rule:

- do not widen into approval execution tests
- do not widen into `M6` delivery tests
- do not add taxonomy matrix tests

## 7. Risks And Guardrails

### 7.1 Over-Design Risk

The main risk is trying to design a full attention workflow inside this baseline slice.

Guardrail:

- only project from existing `PromotionBlocker`
- only emit count downstream

### 7.2 Cross-Layer Drift Risk

Another risk is reusing `M1AttentionItem` or pretending the `M5` taxonomy is already frozen.

Guardrail:

- only use `M5 AttentionItem`
- keep classification fields concrete and minimal for this projection

### 7.3 Runtime Creep Risk

Another risk is expanding into execution approval or `M6`.

Guardrail:

- stop at handoff, ledger, worker details, and CLI summary

## 8. Acceptance Criteria

This slice is complete only when all of the following are true:

- `GovernanceHandoffBundle` includes `attention_items`
- failing governance handoff paths project one attention item per blocker
- persisted artifact includes `attention_items`
- ledger, worker details, and CLI output include `attention_item_count`
- focused runtime-chain tests pass
- no promotion/reject execution logic is added
- no `M6` code is changed

## 9. Out Of Scope Follow-Ups

This slice intentionally leaves for later:

- diagnostic-to-attention routing beyond blocker projection
- attention queue runtime and dequeue policy
- promotion/reject execution path
- `M6` delivery projection of attention items
- controlled vocabularies for attention status and issue taxonomy

## 10. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays inside `M5` runtime projection and persistence and does not cross into `M6`
- `G1-G6` target mapping:
  - this is the minimum `G2` runtime-adoption step required after the `AttentionItem` nucleus already exists
- new runtime contract introduced:
  - `GovernanceHandoffBundle.attention_items`
  - `GovernanceRunLedgerRecord.attention_item_count`
  - worker/CLI `attention_item_count` summary projection
- boundaries not touched:
  - no execution approval flow
  - no taxonomy freeze
  - no `M6`
