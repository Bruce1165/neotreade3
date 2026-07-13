Status: active
Owner: lowfreq / governance
Scope: Narrow `M5 governance status transition CLI baseline` slice for the formal CLI trigger of the persisted status-transition runtime
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Governance Status Transition CLI Baseline Design

Date: 2026-07-13

## 1. Goal

This slice continues the current `M5 governance` closure mainline after:

- persisted governance handoff baseline
- typed handoff readback baseline
- reject execution persistence/runtime baseline
- closure counts visibility baseline
- status transition persistence/runtime baseline

Current repository evidence shows:

- `run_governance_status_transition(...)` already exists as a formal runtime owner
- `governance_status_transitions/<validation_id>/...` artifact and ledger persistence already exist
- `neotrade3/governance/cli.py` still exposes only:
  - `handoff`
  - `reject`
- `tests/unit/test_m5_governance_cli.py` covers only:
  - parser acceptance for `handoff`
  - parser acceptance for `reject`
  - `handoff` runtime CLI execution
  - `reject` runtime CLI execution

So the narrow problem is not:

- how to redesign status transition semantics
- how to change transition artifact or ledger persistence
- how to add worker/on-demand trigger adoption
- how to add API/orchestrator scheduling

It is:

- how to give the existing status-transition runtime one formal governance CLI entry
- how to make CLI callers stop relying on ad-hoc Python imports or private module access
- how to keep the new formal surface aligned with the already-established `handoff` and `reject` CLI pattern

Project-phase note:

- domain: `M5 governance`
- change type: `closure / formal CLI surface baseline`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G5`

## 2. Scope

Included:

- add one new governance CLI subcommand for status transition materialization
- wire the new subcommand to the existing `run_governance_status_transition(...)` owner
- expose the minimal argument surface required by the runtime:
  - `--project-root`
  - `--source-run-id`
  - `--validation-id`
  - `--dry-run`
- print one JSON payload summarizing the typed transition record
- add focused CLI tests for parser acceptance, dry-run behavior, persisted writes, and deterministic error paths

Excluded:

- no runtime semantic changes
- no artifact or ledger schema changes
- no worker changes
- no API changes
- no orchestrator config changes
- no promotion approval path
- no downstream consumer migration
- no `M6`

## 3. Boundary Decisions

Frozen boundary decisions for this slice:

- the new formal surface is `governance CLI`, not `worker`
- the new formal surface is `governance CLI`, not `API`
- the new formal surface is `governance CLI`, not `orchestrator`
- the runtime owner remains `run_governance_status_transition(...)`
- the new subcommand stays narrow and only mirrors the existing runtime contract

Naming freeze:

- CLI subcommand name: `status-transition`

Why hyphenated naming is preferred:

- current CLI already uses human-facing subcommand names rather than Python identifiers
- `status-transition` matches the existing operator-facing CLI style better than `status_transition`
- it keeps the CLI surface decoupled from internal Python function names

## 4. Existing Evidence

### 4.1 Status Transition Runtime Already Exists

Current repository evidence in:

- [runtime.py](file:///Users/mac/NeoTrade3/neotrade3/governance/runtime.py)
- [__init__.py](file:///Users/mac/NeoTrade3/neotrade3/governance/__init__.py)
- [test_m5_governance_status_transition.py](file:///Users/mac/NeoTrade3/tests/unit/test_m5_governance_status_transition.py)

shows that:

- `run_governance_status_transition(...)` is already implemented
- the runtime already enforces persisted reject-proof consumption
- the runtime already writes independent transition artifact and ledger outputs
- the runtime already has focused regression coverage

So the current gap is not the runtime owner itself.

### 4.2 Governance CLI Still Exposes Only Two Formal Commands

Current repository evidence in:

- [cli.py](file:///Users/mac/NeoTrade3/neotrade3/governance/cli.py#L20-L125)

shows that:

- `build_parser()` currently registers only:
  - `handoff`
  - `reject`
- `main()` only branches between:
  - `run_governance_for_benchmark_run(...)`
  - `run_governance_reject_execution(...)`

So status transition is currently runtime-addressable but not CLI-addressable.

### 4.3 Existing CLI Tests Do Not Cover Status Transition

Current repository evidence in:

- [test_m5_governance_cli.py](file:///Users/mac/NeoTrade3/tests/unit/test_m5_governance_cli.py#L91-L393)

shows that:

- parser tests exist for `handoff`
- parser tests exist for `reject`
- execution tests exist for `handoff`
- execution tests exist for `reject`
- no parser or execution test exists for `status-transition`

So the narrow owner-aligned test carrier is already obvious:

- extend `tests/unit/test_m5_governance_cli.py`

### 4.4 Worker And Orchestrator Adoption Would Be Wider Than Necessary

Current repository evidence in:

- [main.py](file:///Users/mac/NeoTrade3/apps/worker/main.py)
- [daily_master_orchestrator.json](file:///Users/mac/NeoTrade3/config/orchestrator/daily_master_orchestrator.json)

shows that:

- worker formalization already exists for reject on-demand execution
- orchestrator config currently exposes only the governance handoff stage
- adding status transition there would require a wider trigger and scheduling decision

So the next truthful owner is the CLI surface, not the worker or orchestrator.

## 5. Approach Options

### Option A: Add A Formal Governance CLI Subcommand (Recommended)

- add `status-transition` to `build_parser()`
- dispatch to `run_governance_status_transition(...)` from `main()`
- print one narrow JSON summary payload
- extend CLI-focused tests only

Pros:

- smallest truthful owner for the current gap
- matches existing `handoff` and `reject` operator pattern
- keeps runtime semantics untouched
- creates a formal shell-facing trigger without widening orchestration surface

Cons:

- still leaves worker/API/orchestrator adoption for later slices

### Option B: Add Worker Governance Executor Adoption First

- wire transition execution into worker governance modes before CLI support

Pros:

- could support async trigger flows later

Cons:

- wider than the current missing owner
- duplicates the pattern already used to over-widen earlier slices
- still leaves the direct governance CLI surface incomplete

### Option C: Add API Or Orchestrator Adoption First

- expose transition through HTTP or scheduled orchestration before CLI formalization

Pros:

- useful later for system integration

Cons:

- requires broader trigger semantics and lifecycle decisions
- introduces more surface area than the current narrow gap justifies
- violates the current “smallest owner first” principle

Decision:

- choose Option A

## 6. Design

### 6.1 Ownership Freeze

Production file:

- `neotrade3/governance/cli.py`

Focused test file:

- `tests/unit/test_m5_governance_cli.py`

Files intentionally not modified:

- `neotrade3/governance/runtime.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/artifact_writer.py`
- `apps/worker/main.py`
- `apps/api/*`
- `config/orchestrator/*`

### 6.2 Parser Surface Freeze

Recommended parser addition:

- subcommand: `status-transition`

Recommended arguments:

- `--project-root`
  - optional
  - defaults to repository root
- `--source-run-id`
  - required
  - identifies the persisted governance handoff source run
- `--validation-id`
  - required
  - identifies the persisted validation/reject subject
- `--dry-run`
  - optional flag
  - prevents writes under `var/`

Why this argument set is sufficient:

- it exactly matches the existing runtime entry requirements
- it does not expose internal implementation details
- it stays symmetrical with the existing `reject` command shape

### 6.3 Dispatch Freeze

Recommended main-path behavior:

1. parse `status-transition`
2. resolve `project_root`
3. call `run_governance_status_transition(...)`
4. print one JSON payload
5. return exit code `0` on success

This slice must not:

- rerun governance handoff automatically
- rerun reject execution automatically
- backfill missing reject proof
- infer transition state from baseline handoff alone

### 6.4 Output Payload Freeze

The new CLI payload should remain a narrow JSON projection of `GovernanceStatusTransitionRecord`.

Recommended output fields:

- `validation_id`
- `source_run_id`
- `status`
- `baseline_run_id`
- `candidate_run_id`
- `decision_id`
- `effective_attention_id`
- `effective_attention_status`
- `effective_blocker_id`
- `effective_blocker_active`
- `artifact_path`
- `ledger_path`
- `dry_run`

Why this output is sufficient:

- it mirrors the current CLI style of returning the typed record surface plus `dry_run`
- it exposes the effective-state outcome without forcing the operator to inspect the artifact file manually
- it avoids widening into full artifact payload echoing

### 6.5 Error Behavior Freeze

The CLI should preserve runtime-owned deterministic failures.

Expected pass-through failures include:

- missing handoff bundle
- missing reject proof
- missing validation result
- missing blocker mapping target
- missing attention mapping target

This slice does not introduce custom suppression or fallback behavior.

Why pass-through is preferred:

- the runtime is already the semantic owner
- CLI should remain a thin shell-facing facade
- hiding runtime failures would reduce auditability

## 7. Testing Strategy

Focused tests should lock:

1. parser accepts `status-transition` with the required arguments
2. dry-run execution returns a valid JSON payload and writes nothing
3. non-dry-run execution materializes transition artifact and ledger outputs
4. JSON payload fields align with the persisted typed ledger record
5. missing reject proof fails deterministically through the CLI path

Recommended reuse pattern:

- reuse the existing benchmark/handoff preparation helpers already present in `test_m5_governance_cli.py`
- reuse the reject setup path so the CLI test remains a thin facade regression rather than duplicating runtime-specific fixture logic

Do not test in this slice:

- worker integration
- API routes
- orchestrator scheduling
- transition runtime internals already covered by `test_m5_governance_status_transition.py`

## 8. Verification

Minimum verification for this design slice:

- self-review the spec for placeholders, contradictions, and ambiguity
- `git diff --check`

Implementation verification is intentionally deferred to the later plan and execution slice.

## 9. Dual-Axis Audit

### 9.1 M-Axis

- `M5`: yes
  - this slice adds the missing formal operator-facing trigger for the existing governance status-transition owner
- `M1-M4`: no
  - no upstream data, recognition, decision, or benchmark semantic change
- `M6`: no
  - no delivery or observability integration yet

### 9.2 G-Axis

- `G5`: yes
  - improves governance operability and auditability by giving the persisted transition owner a formal CLI trigger
- `G1/G2/G3/G4/G6`: no direct expansion
  - no new candidate generation
  - no promotion approval automation
  - no learning-loop writeback

## 10. Non-Claims

This slice does not claim:

- worker/API/orchestrator already expose status transition
- downstream consumers have switched to the transition artifact
- the runtime schema needs to change
- the governance lifecycle is now fully trigger-complete

It only defines the narrowest truthful next owner for the missing status-transition formal CLI surface.
