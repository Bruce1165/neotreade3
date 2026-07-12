Status: active
Owner: lowfreq / governance
Scope: Narrow `M5 governance persisted M4 consumption switch` slice after the M4 typed readback baseline and before M5 governance closure
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Governance Persisted M4 Consumption Switch Design

Date: 2026-07-13

## 1. Goal

This slice advances `M5 governance` one narrow step beyond the already-landed:

- `M4 benchmark artifact typed readback baseline`
- `M5 governance orchestrator-fit baseline`

Current repository evidence shows:

- `M4` already has a canonical typed persisted-artifact readback helper:
  - `read_benchmark_batch_run_result(...)` in `neotrade3/benchmark/run_ledger.py`
- that helper already reconstructs a truthful `BenchmarkBatchRunResult` from persisted JSON
- `M5` runtime still uses manifest-backed recomputation:
  - `load_benchmark_run_manifest(...)`
  - `run_benchmark_manifest(...)`
- `M5` handoff still truthfully consumes `BenchmarkBatchRunResult`
  - `build_governance_handoff_from_batch_run(...)`
- worker/orchestrator governance execution is already real:
  - `OrchestrationPhase.GOVERNANCE` exists
  - worker executor already dispatches governance tasks
  - task-level `args_template` already survives into execution

So the narrow problem is no longer:

- how to reconstruct typed `M4` benchmark artifacts
- how to run governance manually or from the orchestrator
- how to persist governance outputs

It is:

- how to remove the duplicate benchmark recomputation path inside `M5`
- how to make governance consume one persisted `M4` run truthfully
- how to do that without widening into governance closure, `M6`, API, version unification, or scheduler changes

Project-phase note:

- domain: `M5 governance minimal formal loop`
- change type: `upstream truth switch`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G5`, reducing truth split before later `M5 -> M6`

## 2. Scope

Included:

- switch the canonical governance runtime path from manifest rerun to persisted `M4` typed artifact consumption
- add one runtime-level resolver for the benchmark source run id
- keep CLI and worker/orchestrator using the same shared governance runtime owner
- add focused tests that lock:
  - source run-id resolution
  - missing-artifact behavior
  - dry-run and materialization behavior with persisted `M4` input

Excluded:

- no change to `M4` artifact payload shape
- no change to `M4` ledger payload shape
- no change to governance handoff object semantics
- no addition of `AttentionItem`, `ValidationResult`, or `GovernanceDecisionRecord` runtime closure
- no `M6` delivery, report, UI, or API work
- no version-unification work
- no generic source-selector framework for all orchestrator tasks
- no support for mixing manifest and persisted artifact as equal runtime truth sources

## 3. Existing Evidence

### 3.1 M4 Typed Readback Already Exists

Current repository evidence in `neotrade3/benchmark/run_ledger.py` shows:

- `read_benchmark_batch_run_result(...)` already exists
- it returns `BenchmarkBatchRunResult | None`
- it reconstructs the typed batch result from persisted artifact JSON

This means the missing capability is not typed readback itself.

The missing capability is governance runtime adoption of that typed readback.

### 3.2 M5 Runtime Still Recomputes Benchmark Runs

Current repository evidence in `neotrade3/governance/runtime.py` shows:

1. resolve manifest path
2. `load_benchmark_run_manifest(...)`
3. `run_benchmark_manifest(...)`
4. `build_governance_handoff_from_batch_run(...)`
5. `materialize_governance_handoff(...)`

So governance currently has its own upstream execution path instead of consuming a persisted `M4` run.

That creates a truth split:

- one persisted benchmark run may exist
- governance can still regenerate a different batch result from the manifest path

This is the first hard boundary of the slice:

- remove duplicated benchmark recomputation from governance runtime
- do not keep two equal-status upstream truths

### 3.3 Handoff Ownership Is Already Correct

Current repository evidence in `neotrade3/governance/handoff.py` shows:

- `build_governance_handoff_from_batch_run(...)` already accepts `BenchmarkBatchRunResult`
- it already owns the `M4 -> M5` projection semantics

So this slice does not need:

- a new governance-specific JSON parser
- a new handoff input object
- mutation of governance contracts

The missing change belongs in runtime input selection only.

### 3.4 Orchestrator-Fit Is Already Ready For Task-Scoped Input

Current repository evidence in:

- `neotrade3/orchestration/models.py`
- `neotrade3/orchestration/daily_master_orchestrator.py`
- `apps/worker/main.py`

shows:

- `PlannedTask.args_template` already exists
- worker governance executor already reads task-level args
- governance phase is already registered

So this slice does not need another orchestrator model expansion.

It only needs one truthful runtime input contract that can be supplied by both:

- CLI
- worker governance executor

### 3.5 Repository Status Truth Is Stale

Current repository evidence in `PROJECT_STATUS.md` shows:

- `Last Updated` is still `2026-07-11`
- it does not yet record:
  - `M4 mainline runner path`
  - `M5 governance contract/handoff/persistence/ledger/runtime/orchestrator-fit`
  - `M4 typed readback`

So this slice must also update the project truth source before further implementation continues.

This is not extra scope expansion.

It is required hygiene so later execution and audit do not rely on stale state.

## 4. Approach Options

### Option A: Keep Manifest Rerun And Add Persisted Mode As Optional

- keep current `manifest_path` runtime
- add an optional `run_id` path beside it

Pros:

- minimal short-term code disruption

Cons:

- preserves two equal-status upstream truths
- leaves worker and CLI semantics ambiguous
- weakens later semantic audit because governance may still bypass persisted `M4`

### Option B: Make Persisted M4 The Only Runtime Truth (Recommended)

- switch governance runtime to require one `benchmark_run_id`
- read typed `M4` artifact via `read_benchmark_batch_run_result(...)`
- project governance from that typed batch result only

Pros:

- removes duplicated benchmark recomputation
- makes runtime semantics auditable
- keeps `M4 -> M5` contract typed and stable
- aligns governance with already-landed `M4` persistence/readback work

Cons:

- requires CLI and worker task input contract changes
- requires clear missing-artifact behavior

### Option C: Rebuild Only The Minimal Governance Subset From Raw JSON

- keep governance independent from `BenchmarkBatchRunResult`
- parse only currently needed JSON fields

Pros:

- avoids touching runtime input contract

Cons:

- duplicates `M4` serialization knowledge inside `M5`
- bypasses the just-landed typed readback baseline
- makes future audit and reuse worse

Decision:

- choose Option B

## 5. Design

### 5.1 Ownership Decision

This slice should modify only the minimum owners required for the runtime truth switch:

- `neotrade3/governance/runtime.py`
  - replace manifest-backed recomputation with persisted-artifact typed consumption
  - add one source-run-id resolver
- `neotrade3/governance/cli.py`
  - change operator-facing input from manifest path to benchmark run id
- `apps/worker/main.py`
  - change governance executor task args consumption from manifest input to benchmark run id input
- `config/orchestrator/daily_master_orchestrator.json`
  - update the governance task config to carry benchmark run id instead of manifest path
- focused tests around governance runtime / CLI / orchestrator-fit

Files intentionally not modified in this slice:

- `neotrade3/benchmark/contracts.py`
- `neotrade3/benchmark/batch_runner.py`
- `neotrade3/benchmark/run_ledger.py`
- `neotrade3/governance/handoff.py`
- `neotrade3/governance/contracts.py`
- `neotrade3/governance/run_ledger.py`
- `apps/api/*`

### 5.2 New Runtime Contract

The shared runtime entry should become benchmark-run-id based.

Recommended runtime signature:

- `run_governance_for_benchmark_run(*, project_root, benchmark_run_id, dry_run=False) -> GovernanceRunLedgerRecord`

Supporting helper:

- `resolve_governance_benchmark_run_id(...)`

Behavior:

1. normalize and validate `benchmark_run_id`
2. read typed batch result via `read_benchmark_batch_run_result(...)`
3. if missing, raise a narrow runtime error
4. build governance handoff from the typed batch result
5. materialize governance handoff

Removed from shared runtime ownership:

- manifest-path resolution
- benchmark manifest loading
- benchmark manifest execution

### 5.3 Missing-Artifact Semantics

The missing upstream behavior must be explicit.

Recommended rule:

- if the requested `benchmark_run_id` has no persisted typed `M4` artifact, raise `FileNotFoundError`

Reason:

- returning a synthetic empty governance run would be false
- silently falling back to manifest rerun would reintroduce truth split
- returning `None` from the main runtime would weaken CLI/worker error handling

So the runtime should fail loudly when the persisted upstream truth is absent.

### 5.4 CLI Contract

The governance CLI should stop accepting `--manifest`.

Recommended parser contract:

- `--project-root`
- `--benchmark-run-id`
- `--dry-run`

Defaulting rule:

- do not invent a default benchmark run id

Reason:

- a default manifest path made sense when governance owned upstream execution
- a persisted run id is an execution fact, not a static config default

So `--benchmark-run-id` should be required.

### 5.5 Worker/Orchestrator Task Contract

The governance task args should switch from:

- `args_template["manifest"]`

to:

- `args_template["benchmark_run_id"]`

Reason:

- governance should now consume a completed benchmark run, not describe how to recompute one

This keeps orchestration semantics clean:

- `M4` owns benchmark execution
- `M5` owns governance projection from completed `M4`

### 5.6 Config Baseline Decision

This slice should keep the existing governance task registered in the orchestrator config, but its input contract must reflect the truth switch.

Recommended minimal config shape:

- governance task remains in the `GOVERNANCE` phase
- `args_template` carries one explicit `benchmark_run_id`

This is only a baseline config carrier.

It does not claim that the daily orchestrator already knows how to dynamically discover the latest benchmark run id.

That later automation belongs to a different slice.

### 5.7 Testing Strategy

Focused tests should lock only the truth switch boundary.

Required coverage:

1. runtime can materialize governance from a persisted benchmark artifact
2. runtime raises `FileNotFoundError` for a missing run id
3. CLI parser requires `--benchmark-run-id`
4. CLI end-to-end path reads persisted `M4` instead of rerunning manifests
5. worker governance executor reads `benchmark_run_id` from task args
6. orchestrator config survives with the renamed task arg contract

Testing rule:

- do not re-test benchmark grading semantics
- do not widen into `M5` governance closure semantics
- do not widen into `M6` delivery assertions

## 6. Risks And Guardrails

### 6.1 Main Risk

The main implementation risk is accidental widening into:

- dynamic benchmark-run discovery
- governance closure objects
- version unification
- `M6`

Guardrail:

- this slice switches only the runtime truth source
- no new lifecycle automation is added

### 6.2 Semantic Risk

Changing CLI/task inputs from manifest to run id may break current tests and config assumptions.

Guardrail:

- update all first-party governance callers in the same slice
- keep error semantics explicit and narrow

### 6.3 Audit Risk

If `PROJECT_STATUS.md` is not updated together with this slice, later work may continue from stale assumptions.

Guardrail:

- update project truth source in the same slice before implementation proceeds

## 7. Acceptance Criteria

This slice is complete only when all of the following are true:

- shared governance runtime no longer loads or runs benchmark manifests
- shared governance runtime consumes persisted typed `M4` benchmark artifacts by run id
- missing benchmark run id artifacts fail loudly with a narrow error
- CLI input contract is benchmark-run-id based
- worker/orchestrator governance task input contract is benchmark-run-id based
- focused tests lock the new runtime truth source without widening scope
- `PROJECT_STATUS.md` records the latest `M4/M5` completed facts and the new next step truthfully

## 8. Out Of Scope Follow-Ups

This slice intentionally leaves the following for later:

- dynamic discovery of the latest successful benchmark run id
- `M3 backhalf` formal completion
- `M4` expansion beyond the current validation-seed benchmark layer
- `M5` governance closure objects and promotion/reject runtime
- version unification
- `M6 Delivery Ready`

## 9. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice belongs to `M5`, but it depends on the already-landed `M4` typed readback truth
- `G1-G6` target mapping:
  - this slice is a `G5` truth-convergence step before later `G6` delivery
- new contract introduced:
  - governance shared runtime and its callers consume `benchmark_run_id` instead of `manifest`
- boundaries not touched:
  - no `M4` scoring changes
  - no `M5` closure expansion
  - no `M6`
  - no version unification
