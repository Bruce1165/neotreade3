Status: active
Owner: lowfreq / orchestration / governance
Scope: Narrow `M5 dynamic benchmark_run_id propagation` slice for benchmark-to-governance mainline chaining
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Dynamic Benchmark Run ID Propagation Design

Date: 2026-07-13

## 1. Goal

This slice is the next truthful step after:

- `M5 mainline benchmark task baseline`
- `M5 governance persisted-M4 consumption switch`

Current repository evidence shows:

- benchmark is now a first-class orchestrator task through:
  - `benchmark.materialize_run`
  - `run_benchmark_for_manifest(...)`
- governance already consumes persisted M4 truth through:
  - `run_governance_for_benchmark_run(...)`
- but governance orchestration is still not truthfully chained to benchmark:
  - config hard-codes `args_template.benchmark_run_id = "validation_seed_v1_batch"`
  - governance executor reads only `task.args_template["benchmark_run_id"]`
  - orchestrator execution tracks upstream `TaskResult` objects only for dependency status, not for downstream parameter resolution

So the narrow problem is not:

- how to run benchmark
- how to materialize benchmark artifact or ledger
- how governance reads a persisted benchmark run

It is:

- how to let one downstream governance task consume the real `run_id` produced by its upstream benchmark task inside the same orchestrator execution
- how to do that without widening into a generic templating language, artifact introspection, or governance domain rewrites

Project-phase note:

- domain: `M5 mainline bootstrap`
- change type: `mainline chaining baseline`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M4/M5 / G5`

## 2. Scope

Included:

- add one minimal runtime-visible dependency-result injection path inside orchestrator execution
- allow governance to consume benchmark `TaskResult.details["run_id"]` from its declared dependency
- replace the static governance `benchmark_run_id` orchestrator config with a narrow dynamic reference contract
- add focused tests that lock:
  - config planning shape
  - dependency-result resolution
  - governance executor consumption of upstream benchmark `run_id`

Excluded:

- no change to `neotrade3/governance/runtime.py`
- no change to `neotrade3/governance/cli.py`
- no change to governance handoff/ledger/artifact contracts
- no generic artifact-path or ledger-path lookup language
- no multi-hop dependency interpolation
- no arbitrary nested template rendering
- no `M5` closure objects
- no `M6`

## 3. Existing Evidence

### 3.1 Benchmark Already Emits The Needed Truth

Current repository evidence in:

- [main.py](file:///Users/mac/NeoTrade3/apps/worker/main.py#L261-L305)
- [test_m4_benchmark_orchestrator_fit.py](file:///Users/mac/NeoTrade3/tests/unit/test_m4_benchmark_orchestrator_fit.py#L102-L149)

shows that the benchmark executor already returns:

- `details["run_id"]`
- `details["status"]`
- `details["sample_count"]`
- benchmark artifact refs

So this slice must not invent a second benchmark completion object.

It should reuse `TaskResult.details["run_id"]` as the canonical upstream truth.

### 3.2 Governance Already Correctly Consumes A Run ID

Current repository evidence in:

- [runtime.py](file:///Users/mac/NeoTrade3/neotrade3/governance/runtime.py#L16-L51)
- [cli.py](file:///Users/mac/NeoTrade3/neotrade3/governance/cli.py#L17-L51)

shows that governance already has the right domain contract:

- input: one explicit `benchmark_run_id`
- behavior: read persisted benchmark artifact for that `run_id`

So this slice must not rewrite governance runtime or CLI.

The remaining gap is only how orchestrator execution supplies that argument.

### 3.3 Orchestrator Execution Does Not Yet Resolve Dependency Outputs

Current repository evidence in:

- [daily_master_orchestrator.py](file:///Users/mac/NeoTrade3/neotrade3/orchestration/daily_master_orchestrator.py#L127-L238)

shows:

- dependencies are checked for completion and `OK` status
- `completed_tasks` already contains full upstream `TaskResult` objects
- but no step resolves upstream result data into downstream task arguments

This is the real execution-layer gap.

### 3.4 Governance Config Is Still Static

Current repository evidence in:

- [daily_master_orchestrator.json](file:///Users/mac/NeoTrade3/config/orchestrator/daily_master_orchestrator.json#L115-L129)
- [test_m5_governance_orchestrator_fit.py](file:///Users/mac/NeoTrade3/tests/unit/test_m5_governance_orchestrator_fit.py#L108-L129)

shows that governance still plans with a static:

- `benchmark_run_id = validation_seed_v1_batch`

This is now the incorrect truth source once benchmark is already a real upstream task.

## 4. Approach Options

### Option A: Let Governance Executor Read Benchmark Ledger From Disk

Pros:

- avoids touching orchestrator execution logic

Cons:

- makes same-run dependency chaining depend on side effects instead of in-memory execution truth
- duplicates lookup policy that the orchestrator already knows through `completed_tasks`
- risks coupling execution semantics to persistence timing

### Option B: Inject Dependency `TaskResult` Objects Into Downstream Execution Context (Recommended)

Pros:

- uses already-available in-memory execution truth
- keeps the new contract narrow and explicit
- lets governance resolve the upstream benchmark `run_id` without changing governance runtime
- stays atomic: one new execution-layer bridge, one config switch

Cons:

- requires a small execution-context change inside orchestrator
- requires governance executor to prefer dependency-derived `run_id`

### Option C: Add A Generic Template Engine For `args_template`

Pros:

- future-flexible

Cons:

- far wider than the current need
- introduces ambiguity around expression syntax, nesting, and failure modes
- violates the required conservative scope

Decision:

- choose Option B

## 5. Design

### 5.1 Ownership Decision

This slice introduces one narrow execution bridge, not a new governance owner:

- `neotrade3/orchestration/daily_master_orchestrator.py`
- `apps/worker/main.py`
- `config/orchestrator/daily_master_orchestrator.json`
- supporting orchestration contract/test surface as needed

Files intentionally not modified in this slice:

- `neotrade3/governance/runtime.py`
- `neotrade3/governance/cli.py`
- `neotrade3/governance/handoff.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/benchmark/runtime.py`

### 5.2 Dynamic Reference Contract Freeze

This slice should support one narrow dynamic reference shape inside `args_template`:

```json
{
  "benchmark_run_id": {
    "from_task": "benchmark.materialize_run",
    "detail_key": "run_id"
  }
}
```

Meaning:

1. find the completed upstream task named by `from_task`
2. read its `TaskResult.details[detail_key]`
3. inject that resolved string into the task seen by the executor

Design rules:

- only support reading from dependency task `details`
- only support direct key lookup
- do not support nested paths
- do not support artifact refs
- do not support fallback expressions

### 5.3 Orchestrator Execution Freeze

`execute_run_plan(...)` should be extended to resolve task arguments after dependency checks pass and before executor invocation.

Behavior:

1. gather dependency `TaskResult` objects from `completed_tasks`
2. build a small per-task context bundle for executor use
3. resolve any dynamic arg references against those dependency results
4. call executor with a `PlannedTask` whose `args_template` already contains resolved scalar values

Design rule:

- executor signature stays unchanged: `executor(task, context)`
- resolved values must exist only after all dependencies are already `OK`
- resolution failure should surface as a task failure with a narrow error message, not as silent fallback

### 5.4 Worker Governance Executor Freeze

The governance executor should prefer the dependency-derived benchmark `run_id` resolved by orchestrator execution.

Practical effect:

- if `task.args_template["benchmark_run_id"]` is already a resolved string, current downstream runtime path stays unchanged
- if it is missing or blank after resolution, governance still fails explicitly

Design rule:

- do not make governance executor parse config reference objects itself
- keep reference resolution owned by orchestrator execution

### 5.5 Config Freeze

The governance task should become truthfully chained to benchmark.

Config changes:

- add `depends_on = ["benchmark.materialize_run"]`
- replace static `benchmark_run_id` literal with the narrow reference contract

Result:

- same-run governance handoff now consumes the real upstream benchmark `run_id`
- the orchestrator dependency graph truthfully reflects benchmark as a prerequisite

### 5.6 Failure Semantics Freeze

Failure handling must stay conservative:

- if benchmark does not run successfully, governance is blocked by dependency status before any resolution attempt
- if benchmark runs but does not provide `details["run_id"]`, governance fails with a narrow execution error
- no implicit fallback to `DEFAULT_GOVERNANCE_BENCHMARK_RUN_ID`

Reason:

- once benchmark is a real upstream dependency, a static fallback would reintroduce false truth

## 6. Testing Strategy

Focused tests should lock:

1. governance planning includes benchmark dependency and dynamic reference config shape
2. orchestrator execution resolves the benchmark `run_id` into governance before executor invocation
3. governance executor succeeds in dry-run mode when fed through benchmark dependency output
4. governance executor succeeds in write mode with dynamically injected `run_id`
5. governance task blocks when benchmark dependency is missing or non-`OK`

Testing rule:

- do not widen into CLI changes
- do not widen into governance domain contract changes
- do not widen into generic template-engine behavior beyond this one narrow reference contract

## 7. Risks And Guardrails

### 7.1 Scope Risk

The main risk is widening this slice into a generic orchestration templating system.

Guardrail:

- support only `from_task + detail_key`
- only for dependency task results already proven `OK`

### 7.2 Ownership Risk

Another risk is splitting resolution between orchestrator and governance executor.

Guardrail:

- orchestrator owns reference resolution
- governance executor remains a thin consumer of resolved scalar input

### 7.3 Truth Risk

Another risk is keeping a silent static fallback after dynamic chaining is introduced.

Guardrail:

- remove static orchestrator truth for `benchmark_run_id`
- fail explicitly if upstream `run_id` cannot be resolved

## 8. Acceptance Criteria

This slice is complete only when all of the following are true:

- governance task truthfully depends on `benchmark.materialize_run`
- governance no longer plans with a static benchmark run id literal
- orchestrator execution resolves benchmark `TaskResult.details["run_id"]` into governance args
- worker governance execution succeeds without changing governance runtime contract
- focused tests prove planning, resolution, and execution behavior

## 9. Out Of Scope Follow-Ups

This slice intentionally leaves for later:

- multi-key or nested dependency result extraction
- dynamic artifact-ref injection
- generic orchestration templating
- governance closure objects
- `M6`

## 10. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice spans `M4` and `M5` mainline execution truth, but only to bridge the already-existing benchmark result into the already-existing governance consumer
- `G1-G6` target mapping:
  - this is a `G5` mainline-connectivity step that removes the last false static handoff inside `M4 -> M5`
- new contract introduced:
  - narrow dynamic args reference shape: `from_task + detail_key`
  - dependency-result resolution inside orchestrator execution
- boundaries not touched:
  - no governance runtime rewrite
  - no CLI rewrite
  - no generic template language
  - no `M6`
