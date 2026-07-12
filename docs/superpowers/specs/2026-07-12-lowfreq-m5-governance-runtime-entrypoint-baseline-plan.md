Status: active
Owner: lowfreq / governance
Scope: Implementation plan for the narrow `M5 governance runtime/entrypoint baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq M5 Governance Runtime Entrypoint Baseline Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-m5-governance-runtime-entrypoint-baseline-design.md`

## 1. Goal

This plan implements only the next narrow `M5` slice after the governance ledger/readback baseline:

- one formal `M5` package CLI entrypoint
- one stable operator-facing JSON summary for a governance materialization run
- one focused test carrier that locks parser behavior and end-to-end CLI composition

This slice explicitly does not include:

- governance API
- worker/orchestrator registration
- scheduler integration
- approval workflow runtime
- promotion execution runtime
- `M6` delivery/UI projection
- mutation of `GovernanceHandoffBundle`
- mutation of `BenchmarkBatchRunResult`
- persisted `M4` artifact readback reconstruction into typed batch-run objects
- package-root export widening unless implementation evidence proves it is immediately required

## 2. Starting Point

Repository evidence before this slice:

- `M5` already has a canonical projection owner:
  - `build_governance_handoff_from_batch_run(...)` in `neotrade3/governance/handoff.py`
- `M5` already has canonical materialization and readback owners:
  - `materialize_governance_handoff(...)`
  - `read_governance_run_ledger(...)`
  - `read_governance_handoff_artifact(...)`
  - `list_governance_run_ledgers(...)`
- `M4` already has the exact runtime-entry pattern to mirror:
  - `neotrade3/benchmark/cli.py`
  - parser contract
  - mainline runtime composition
  - JSON summary print
- `M4` runtime source of truth already exists:
  - `load_benchmark_run_manifest(...)`
  - `run_benchmark_manifest(...)`
- `M5` still has no formal package-level runtime entrypoint

So the implementation strategy is:

- reuse the existing `M4` benchmark mainline path as upstream runtime source
- reuse the existing `M5` handoff and materialization owners unchanged
- add one thin `M5` CLI facade only
- keep tests focused on CLI composition, not on re-testing benchmark internals

## 3. File Boundary

Production file:

- `neotrade3/governance/cli.py`

Test file:

- `tests/unit/test_m5_governance_cli.py`

Documentation files:

- `docs/superpowers/specs/2026-07-12-lowfreq-m5-governance-runtime-entrypoint-baseline-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-m5-governance-runtime-entrypoint-baseline-plan.md`

Files intentionally reused but not modified unless implementation evidence proves it necessary:

- `neotrade3/benchmark/batch_runner.py`
- `neotrade3/governance/handoff.py`
- `neotrade3/governance/run_ledger.py`

Files explicitly not in scope:

- `apps/api/*`
- `apps/worker/*`
- `config/orchestrator/*`
- `neotrade3/governance/contracts.py`
- `neotrade3/governance/assembler.py`
- `neotrade3/governance/artifact_writer.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/__init__.py`

Plan note:

- keep `__init__.py` untouched by default
- tests should import `neotrade3.governance.cli` directly unless a real immediate import need is proven

## 4. Execution Steps

### M5CLI-S1: Add the CLI module and parser

Create:

- `neotrade3/governance/cli.py`

Implement:

- `build_parser()`
- `main(argv: Sequence[str] | None = None) -> int`

Parser contract:

- `--project-root`
- `--manifest`
- `--dry-run`

Defaults:

- project root defaults to repository root derived from module location
- manifest defaults to `config/benchmark/validation_seed_manifest.json`
- `dry_run` defaults to `False`

Completion check:

- parser can be imported and used independently from command execution

### M5CLI-S2: Wire the governance runtime composition flow

In `main()`:

1. parse args
2. resolve `project_root`
3. resolve `manifest_path`
4. call `load_benchmark_run_manifest(...)`
5. call `run_benchmark_manifest(...)`
6. call `build_governance_handoff_from_batch_run(...)`
7. call `materialize_governance_handoff(...)`
8. print one JSON summary
9. return `0`

Implementation rule:

- `main()` must stay a thin caller over existing benchmark/governance owners
- do not duplicate manifest loading, batch execution, handoff projection, or persistence internals

Summary payload should include at least:

- `source_run_id`
- `status`
- `source_layer`
- `projected_assessment_count`
- `projected_issue_count`
- `diagnostic_count`
- `change_request_count`
- `experiment_request_count`
- `promotion_blocker_count`
- `artifact_path`
- `ledger_path`
- `dry_run`

Completion check:

- one manifest-backed benchmark run can drive the complete `M4 -> M5` governance materialization path through the CLI only

### M5CLI-S3: Add focused tests

Create:

- `tests/unit/test_m5_governance_cli.py`

Test carrier pattern:

- mirror `tests/unit/test_m4_benchmark_cli.py`
- prepare an isolated temp project root
- copy required benchmark config files into `config/benchmark/`
- capture stdout and assert printed JSON payload

Test cases:

1. parser default behavior
   - `project_root is None`
   - default manifest is `config/benchmark/validation_seed_manifest.json`
   - `dry_run is False`
2. parser explicit arguments
   - custom `--project-root`
   - custom `--manifest`
   - `--dry-run`
3. end-to-end dry run
   - invoke `main()` with temp project root
   - capture stdout JSON
   - assert `exit_code == 0`
   - assert `dry_run is True`
   - assert governance artifact and ledger files do not exist
4. end-to-end materialization path
   - invoke `main()` with temp project root
   - capture stdout JSON
   - assert `exit_code == 0`
   - assert governance artifact and ledger files exist
   - assert persisted artifact/ledger identities match printed summary

Testing rule:

- do not re-test benchmark grading semantics exhaustively
- test only parser contract and `M4 -> M5` CLI composition behavior

Completion check:

- runtime exposure and summary contract are both locked independently of API/orchestrator concerns

### M5CLI-S4: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/governance/cli.py tests/unit/test_m5_governance_cli.py`
- `.venv/bin/python -m pytest tests/unit/test_m5_governance_cli.py tests/unit/test_m5_governance_handoff_adapter.py tests/unit/test_m5_governance_run_ledger.py tests/unit/test_m4_benchmark_cli.py`

Fallback if `pytest` is unavailable:

- keep `py_compile`
- run `.venv/bin/python` inline assertions against:
  - `build_parser()`
  - `main()` in dry-run mode with temp project root
  - `main()` in write mode with temp project root
  - printed summary fields
  - governance artifact/ledger file existence behavior

Completion check:

- syntax passes
- best-available focused verification passes

### M5CLI-S5: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-m5-governance-runtime-entrypoint-baseline-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-m5-governance-runtime-entrypoint-baseline-plan.md`
- `neotrade3/governance/cli.py`
- `tests/unit/test_m5_governance_cli.py`

Must exclude:

- `apps/api/*`
- `apps/worker/*`
- `config/orchestrator/*`
- `neotrade3/governance/contracts.py`
- `neotrade3/governance/assembler.py`
- `neotrade3/governance/artifact_writer.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/__init__.py`
- `neotrade3/benchmark/batch_runner.py`
- unrelated workspace changes

## 5. Risks And Guards

Risk 1:

- duplicating logic that is already frozen inside benchmark or governance owners

Guard:

- keep the CLI as orchestration-only glue
- call existing owners directly
- avoid helper duplication inside the CLI module

Risk 2:

- letting the new tests become another indirect copy of benchmark batch-runner tests

Guard:

- test parser behavior and CLI composition only
- rely on existing benchmark and governance owner tests for internal semantics

Risk 3:

- widening into orchestrator ownership because the new CLI is runnable

Guard:

- keep the slice package-local to `neotrade3/governance/cli.py`
- add no config changes under `config/orchestrator/`
- add no worker registration

Risk 4:

- widening into a second runtime theme by reconstructing typed batch results from persisted `M4` artifacts

Guard:

- use only manifest-backed benchmark execution in this slice
- postpone persisted readback reconstruction to a dedicated later theme if a real consumer appears

## 6. Success Criteria

This slice is complete when:

- `neotrade3.governance.cli` exists as a formal runnable entrypoint
- the default benchmark manifest can drive the full `M4 -> M5` governance materialization path
- dry-run mode returns a stable JSON summary without writing governance files
- write mode persists the canonical governance artifact and ledger outputs
- focused verification passes
- syntax verification passes
