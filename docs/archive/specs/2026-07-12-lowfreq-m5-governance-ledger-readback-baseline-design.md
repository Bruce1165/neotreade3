Status: active
Owner: lowfreq / governance
Scope: Narrow `M5 governance ledger/readback baseline` slice after artifact persistence baseline
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq M5 Governance Ledger Readback Baseline Design

Date: 2026-07-12

## 1. Goal

This slice advances `M5 governance` one narrow step beyond the already-landed artifact persistence baseline.

Current repository evidence shows:

- `M5` already has:
  - formal governance contracts in `neotrade3/governance/contracts.py`
  - formal `M4 -> M5` projection in `neotrade3/governance/handoff.py`
  - canonical artifact persistence in `neotrade3/governance/artifact_writer.py`
- `M5` still does not have:
  - a governance ledger record
  - a governance materialize entrypoint
  - artifact readback
  - ledger listing/readback
- `M4` already has the exact pattern this slice should mirror narrowly in `neotrade3/benchmark/run_ledger.py`

So the narrow problem is no longer how to build or persist one governance bundle.

It is:

- how to give that persisted artifact one stable ledger envelope
- how to read back one persisted governance run by `source_run_id`
- how to list completed governance runs without widening into CLI, API, or runtime ownership

Project-phase note:

- domain: `M5 governance minimal formal loop`
- change type: `artifact persistence baseline -> ledger/readback baseline`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G5`

## 2. Scope

Included:

- add one bounded ledger/readback owner under `neotrade3/governance/`
- add one stable ledger record contract for persisted governance runs
- add one materialize entrypoint that composes:
  - existing artifact writer
  - new governance ledger writer
- add readback helpers for:
  - one ledger by `source_run_id`
  - one artifact by `source_run_id`
  - all ledger records ordered latest-first
- add focused tests for:
  - real materialize
  - `dry_run`
  - ledger readback
  - artifact readback
  - latest-first listing

Excluded:

- no governance CLI
- no API routes
- no worker/orchestrator registration
- no `M6` delivery/UI projection
- no mutation of `GovernanceHandoffBundle`
- no change to existing artifact path contract
- no extra index file beyond scanning persisted ledger files
- no validation/promotion workflow runtime

## 3. Existing Evidence

### 3.1 M5 Already Has The Canonical Artifact Surface

Current persisted anchor already exists:

- `write_governance_handoff_artifact(...)` in `neotrade3/governance/artifact_writer.py`
- canonical artifact path:
  - `var/artifacts/governance_handoffs/<source_run_id>/governance_handoff_bundle.json`

That means this slice should treat the artifact writer as an upstream dependency and not redesign storage identity.

### 3.2 M4 Already Freezes The Ledger/Readback Pattern

Current production precedent already exists in `neotrade3/benchmark/run_ledger.py`:

- `BenchmarkRunLedgerRecord`
- `write_benchmark_run_ledger(...)`
- `materialize_benchmark_batch_run(...)`
- `read_benchmark_run_ledger(...)`
- `read_benchmark_run_artifact(...)`
- `list_benchmark_run_ledgers(...)`

Important proven choices:

- artifact writer and ledger writer stay separate
- `materialize_*` composes the two side effects
- single-run readback returns `None` when the file does not exist
- listing scans persisted ledger files instead of maintaining a second index file
- listing sorts by `(written_at, run_id)` descending

The safest `M5` next step is to mirror this pattern narrowly with governance names and paths.

### 3.3 Existing M5 Specs Explicitly Leave This Slice Open

The already-landed `artifact persistence baseline` spec and plan explicitly exclude:

- governance ledger
- governance readback
- governance CLI
- runtime surfaces

So this slice is the direct next step the current specs leave behind, rather than a new theme.

## 4. Approach Options

### Option A: Ledger Writer Only

Pros:

- smallest code delta

Cons:

- no readback means no closed persisted access path
- downstream callers still need to reconstruct file paths manually

### Option B: Ledger + Readback Baseline (Recommended)

- add one ledger owner
- add one materialize entrypoint
- add one single-run readback path
- add one latest-first listing path

Pros:

- mirrors the already-proven `M4` pattern exactly where evidence exists
- creates the smallest closed persistence loop after artifact writing
- still avoids widening into CLI/API/runtime

Cons:

- adds one new persistence layer beyond artifact-only storage

### Option C: Ledger + Readback + CLI

Pros:

- closer to operator visibility

Cons:

- widens immediately into output wording and runtime responsibility
- claims a governance entry surface before query semantics have aged

Decision:

- choose Option B

## 5. Design

### 5.1 Ownership Decision

This slice introduces one new bounded owner dedicated to governance ledger/readback only.

Recommended file:

- `neotrade3/governance/run_ledger.py`

Responsibilities:

- derive the canonical ledger path from `bundle.source_run_id`
- persist one ledger JSON file for a completed governance run
- compose artifact write + ledger write in one `materialize` entrypoint
- read one ledger by `source_run_id`
- read one artifact by `source_run_id`
- list all persisted governance ledger records latest-first

This owner must not:

- build governance objects
- change the artifact writer payload
- expose CLI or API behavior
- know about worker/orchestrator/delivery consumers

### 5.2 Ledger Record Contract

This slice should freeze one stable ledger record, recommended as:

- `GovernanceRunLedgerRecord`

Minimum fields:

- `source_run_id`
- `status`
- `written_at`
- `artifact_path`
- `ledger_path`
- `source_layer`
- `projected_assessment_count`
- `projected_issue_count`

Recommended collection fields:

- `diagnostic_count`
- `change_request_count`
- `experiment_request_count`
- `promotion_blocker_count`

Design rule:

- the ledger record is a persisted side-effect summary for lookup/listing
- it is not the canonical governance business payload
- the canonical governance business payload remains the artifact produced from `bundle.to_payload()`

### 5.3 Canonical File Layout

Artifact path remains unchanged:

- `var/artifacts/governance_handoffs/<source_run_id>/governance_handoff_bundle.json`

Recommended ledger path:

- `var/ledgers/governance_handoffs/<source_run_id>/governance_handoff_run.json`

Layout rule:

- exactly one artifact file and one ledger file per `source_run_id`
- no separate aggregate index file in this slice
- listing is derived by scanning persisted ledger files

Reason:

- `M4` already proves that ledger-file scanning is enough for the baseline
- adding a second index file now would widen write semantics without repository evidence

### 5.4 Writer Entrypoints

Recommended new entrypoints:

- `write_governance_run_ledger(...)`
- `materialize_governance_handoff(...)`

`write_governance_run_ledger(...)` input:

- `project_root`
- `bundle: GovernanceHandoffBundle`
- `artifact_record: GovernanceArtifactRecord`
- `dry_run: bool = False`

Behavior:

1. normalize `project_root`
2. reuse normalized `bundle.source_run_id`
3. derive canonical ledger file path
4. build ledger payload from:
   - `source_run_id`
   - `status="completed"`
   - `written_at=artifact_record.written_at`
   - `artifact_path=artifact_record.artifact_path`
   - `ledger_path`
   - `source_layer`
   - projected counts
   - collection counts
5. if `dry_run` is false:
   - create parent directory
   - write deterministic JSON
6. return `GovernanceRunLedgerRecord`

`materialize_governance_handoff(...)` behavior:

1. call existing `write_governance_handoff_artifact(...)`
2. call `write_governance_run_ledger(...)`
3. return `GovernanceRunLedgerRecord`

### 5.5 Readback Entrypoints

Recommended read/list helpers:

- `read_governance_run_ledger(...)`
- `read_governance_handoff_artifact(...)`
- `list_governance_run_ledgers(...)`

Behavior rules:

- single-run readback returns `None` if the target file does not exist
- single-run readback accepts only JSON object roots; non-object payloads return `None`
- listing returns `[]` if the ledger root does not exist
- listing skips unreadable or invalid JSON ledger files
- listing sorts by `(written_at, source_run_id)` descending

This mirrors the existing `M4` benchmark baseline and avoids inventing a new read policy.

### 5.6 JSON Formatting Rule

Use the same deterministic JSON rule already frozen by `M4` and current `M5` artifact writing:

- `indent=2`
- `sort_keys=True`
- `ensure_ascii=False`
- newline-terminated file

### 5.7 Export Boundary

Default recommendation:

- update `neotrade3/governance/__init__.py` only if the new tests or immediate production consumers require package-root imports

Current evidence:

- existing governance tests already import package-root handoff builders
- `M4` benchmark root export includes its ledger/readback surface

So package-root export is allowed in this slice only for the new ledger/readback contracts and helpers, not for unrelated widening.

## 6. Testing Strategy

Add one focused unit test file:

- `tests/unit/test_m5_governance_run_ledger.py`

Tests should lock:

1. real materialize persists both artifact and ledger
2. materialize returns a stable `GovernanceRunLedgerRecord`
3. `dry_run=True` creates neither artifact nor ledger file
4. ledger readback returns the same persisted summary
5. artifact readback returns the persisted governance payload object
6. listing returns latest run first

Fixture rule:

- build bundles through the real `build_governance_handoff_from_assessment(...)` path where practical
- prefer real `B4` governance evidence over fake dict payloads
- only construct direct `GovernanceHandoffBundle(...)` instances when testing boundary conditions not reachable from current upstream builders

## 7. Risks And Guardrails

Risk 1:

- widening into CLI or API because readback now exists

Guardrail:

- keep all entrypoints file-local to the governance package
- add no user-facing command or HTTP surface

Risk 2:

- drifting from the already-frozen artifact path contract

Guardrail:

- read artifact files only through the existing canonical artifact location
- do not rename or version the artifact filename in this slice

Risk 3:

- over-designing listing with an extra index file

Guardrail:

- derive listing from ledger file scan only
- postpone aggregate index semantics until a real consumer appears

Risk 4:

- claiming governance runtime closure too early

Guardrail:

- claim only `artifact + ledger + readback baseline`
- do not claim approval workflow, promotion automation, API querying, or `M6` delivery

## 8. Success Criteria

This slice is complete when:

- `neotrade3/governance/run_ledger.py` exists as a production owner
- one real `GovernanceHandoffBundle` can be materialized into:
  - the canonical artifact path
  - the canonical ledger path
- readback can recover one persisted ledger and one persisted artifact by `source_run_id`
- listing returns persisted ledger records latest-first
- focused tests lock the ledger/readback behavior independently of CLI/API/runtime concerns

## 9. Dual-Axis Audit Target

Architecture:

- primary layer: `M5`
- upstream dependency consumed but not modified: `M5 artifact persistence baseline`
- pattern reference only, not dependency: `M4 benchmark run_ledger`

Goal mapping:

- `G5`: convert the already-persisted governance artifact into the first queryable governance persistence baseline
- not yet `G6`: no delivery, UI, API, or runtime exposure is added here

Not claimed in this slice:

- no governance CLI
- no governance API
- no orchestrator/worker integration
- no automated validation or promotion runtime
- no `M6` delivery surface
