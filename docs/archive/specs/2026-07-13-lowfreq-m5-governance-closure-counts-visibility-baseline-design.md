Status: active
Owner: lowfreq / governance / worker / api
Scope: Narrow `M5 governance closure counts visibility baseline` slice for worker-to-API summary projection
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Governance Closure Counts Visibility Baseline Design

Date: 2026-07-13

## 1. Goal

Current repository evidence shows:

- `GovernanceRunLedgerRecord` already persists `validation_result_count`
- `GovernanceRunLedgerRecord` already persists `decision_record_count`
- governance CLI already exposes both counts
- but the worker governance executor still omits both counts from `TaskResult.details`
- API orchestration payloads only reflect what the worker snapshot already carries

So the narrow next problem is:

- surface the two existing closure counts through the worker governance handoff result
- prove that orchestration API wrapper payloads preserve those fields
- stop before any candidate validation, promotion, reject state transition, or blocker/attention status work

Project-phase note:

- domain: `M5 governance`
- change type: `closure visibility baseline`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G2`

## 2. Scope

Included:

- add `validation_result_count` to governance handoff `TaskResult.details`
- add `decision_record_count` to governance handoff `TaskResult.details`
- add focused worker/orchestrator test coverage for those two fields
- add one API wrapper test proving orchestration payload persistence preserves those fields

Excluded:

- no new governance contract
- no new ledger field
- no CLI changes
- no candidate benchmark comparison
- no final validation materialization
- no promotion or reject state transition work
- no `M6`

## 3. Existing Evidence

### 3.1 Closure Counts Already Exist In The Governance Ledger

Current repository evidence in:

- [run_ledger.py](file:///Users/mac/NeoTrade3/neotrade3/governance/run_ledger.py#L20-L79)

shows that:

- `GovernanceRunLedgerRecord` already has `validation_result_count`
- `GovernanceRunLedgerRecord` already has `decision_record_count`
- both counts are already serialized and hydrated

So this slice does not need new persistence design.

### 3.2 CLI Already Treats Them As Real Runtime Summary Fields

Current repository evidence in:

- [cli.py](file:///Users/mac/NeoTrade3/neotrade3/governance/cli.py#L81-L103)

shows that CLI `handoff` output already includes:

- `validation_result_count`
- `decision_record_count`

So the missing owner is not CLI visibility.

### 3.3 Worker Governance Details Still Omit Them

Current repository evidence in:

- [main.py](file:///Users/mac/NeoTrade3/apps/worker/main.py#L359-L384)

shows that current governance handoff `TaskResult.details` only carries:

- `source_run_id`
- `status`
- `source_layer`
- `projected_assessment_count`
- `projected_issue_count`
- `diagnostic_count`
- `change_request_count`
- `experiment_request_count`
- `promotion_blocker_count`
- `attention_item_count`
- `dry_run`
- `benchmark_run_id`

It does not carry:

- `validation_result_count`
- `decision_record_count`

So the true missing production owner is the worker governance executor summary projection.

### 3.4 API Orchestration Payloads Are Thin Wrappers

Current repository evidence in:

- [main.py](file:///Users/mac/NeoTrade3/apps/api/main.py#L1374-L1411)

shows that API orchestration payloads:

- collect task results from the worker snapshot
- persist them as `tasks`
- do not compute governance-specific counts independently

So API does not need new behavior; it only needs a regression anchor proving the worker-provided fields survive wrapper persistence.

### 3.5 Existing Tests Stop One Layer Too Early

Current repository evidence in:

- [test_m5_governance_orchestrator_fit.py](file:///Users/mac/NeoTrade3/tests/unit/test_m5_governance_orchestrator_fit.py#L317-L413)
- [test_bootstrap_skeleton.py](file:///Users/mac/NeoTrade3/tests/unit/test_bootstrap_skeleton.py#L1223-L1309)

shows that:

- worker/orchestrator tests assert `attention_item_count`, but not validation/decision counts
- API wrapper tests assert mode/task identity, but not closure count preservation

So the real test gap is exactly the same visibility gap as production.

## 4. Approach Options

### Option A: Worker Summary Projection Only

Pros:

- smallest production change
- fixes the real missing owner

Cons:

- leaves API wrapper preservation implicit unless another layer regresses later

### Option B: Worker Summary Projection Plus API Wrapper Regression (Recommended)

Pros:

- keeps production change minimal
- adds one extra proof that orchestration API preserves worker-provided closure counts
- directly matches the user-approved boundary of `worker -> orchestration API`

Cons:

- slightly wider test surface than worker-only

### Option C: Jump To Full Closure Runtime

Pros:

- larger end-state progress

Cons:

- crosses into candidate validation, promotion, and reject workflow design
- violates the currently frozen narrow boundary

Decision:

- choose Option B

## 5. Design

### 5.1 Ownership Freeze

Primary production owner:

- `apps/worker/main.py`

Focused test owners:

- `tests/unit/test_m5_governance_orchestrator_fit.py`
- `tests/unit/test_bootstrap_skeleton.py`

Files intentionally not modified:

- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/cli.py`
- `apps/api/main.py`
- `neotrade3/governance/runtime.py`
- `M6`

### 5.2 Worker Projection Freeze

For the governance handoff branch in `_create_governance_executor()`:

- keep existing detail fields unchanged
- additionally project:
  - `validation_result_count`
  - `decision_record_count`

Source of truth:

- use the already-materialized `GovernanceRunLedgerRecord` returned by `run_governance_for_benchmark_run(...)`

This slice must not:

- recompute counts from the artifact
- infer missing values
- change any reject execution branch payload

### 5.3 API Visibility Freeze

No production API code change is required.

Reason:

- `BootstrapApiService.orchestration_run_view(...)` already persists `task_results` from the worker snapshot as-is
- once the worker task detail includes the two counts, the orchestration wrapper artifact will expose them automatically

So the API part of this slice is verification only:

- add a regression test that supplies a worker snapshot carrying the two counts
- assert the wrapper artifact preserves them verbatim

### 5.4 Test Freeze

Worker/orchestrator test should prove:

- governance executor dry-run details include `validation_result_count`
- governance executor dry-run details include `decision_record_count`
- materialized governance executor details include the same two counts

API wrapper test should prove:

- when worker snapshot task details carry the two counts, orchestration wrapper artifact keeps them in `tasks[0].details`

This slice intentionally does not add:

- candidate validation tests
- promotion/reject execution tests
- integration HTTP smoke changes

## 6. Testing Strategy

Run:

- `python3 -m py_compile apps/worker/main.py tests/unit/test_m5_governance_orchestrator_fit.py tests/unit/test_bootstrap_skeleton.py`
- `python3 -m pytest tests/unit/test_m5_governance_orchestrator_fit.py tests/unit/test_bootstrap_skeleton.py -k "governance_executor or orchestration_run_view_uses_worker_runtime_and_writes_wrapper_files"`
- `git diff --check`

## 7. Acceptance Criteria

- worker governance handoff `TaskResult.details` includes `validation_result_count`
- worker governance handoff `TaskResult.details` includes `decision_record_count`
- focused worker/orchestrator tests lock both fields
- focused API wrapper test proves wrapper artifact preserves both fields
- no ledger, CLI, runtime, or `M6` production file changes are introduced

## 8. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays inside `M5` worker/API summary projection and does not cross into runtime workflow expansion
- `G1-G6` target mapping:
  - this strengthens `G2` by making already-existing closure objects visible on the operational `worker -> orchestration API` chain
- new runtime contract introduced:
  - governance handoff worker details now carry `validation_result_count`
  - governance handoff worker details now carry `decision_record_count`
- boundaries not touched:
  - no candidate comparison
  - no final validation materialization
  - no blocker/attention state transition
  - no promotion/reject workflow expansion
  - no `M6`
