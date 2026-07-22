Status: active
Owner: lowfreq / governance
Scope: Implementation plan for the narrow `M5 governance artifact persistence baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq M5 Governance Artifact Persistence Baseline Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-m5-governance-artifact-persistence-baseline-design.md`

## 1. Goal

This plan implements only the next narrow `M5` slice after the governance handoff adapter:

- one formal artifact writer owner
- one stable `GovernanceArtifactRecord`
- one focused test carrier that locks path, payload, and `dry_run` behavior

This slice explicitly does not include:

- governance ledger or readback index
- governance CLI
- API
- worker/orchestrator registration
- `M6` delivery consumption
- mutation of `GovernanceHandoffBundle`
- package-root export widening unless implementation evidence proves it is immediately required

## 2. Starting Point

Repository evidence before this slice:

- `M5` already has a formal in-memory handoff surface:
  - `GovernanceHandoffBundle` in `neotrade3/governance/handoff.py`
  - `build_governance_handoff_from_assessment(...)`
  - `build_governance_handoff_from_batch_run(...)`
- `M4` already proves the narrow storage pattern that should be mirrored:
  - `BenchmarkArtifactRecord`
  - `write_benchmark_batch_run_artifact(...)`
- there is still no production owner that materializes a governance handoff bundle into a canonical artifact under `var/artifacts/`

So the implementation strategy is:

- reuse existing `M5` handoff input without rebuilding governance semantics
- mirror the existing `M4` artifact-writer shape narrowly
- freeze a single canonical artifact path
- keep storage ownership separate from ledger, readback, and runtime surfaces

## 3. File Boundary

Production file:

- `neotrade3/governance/artifact_writer.py`

Test file:

- `tests/unit/test_m5_governance_artifact_writer.py`

Documentation files:

- `docs/superpowers/specs/2026-07-12-lowfreq-m5-governance-artifact-persistence-baseline-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-m5-governance-artifact-persistence-baseline-plan.md`

Files explicitly not in scope:

- `neotrade3/governance/__init__.py`
- `neotrade3/governance/handoff.py`
- `neotrade3/benchmark/*`
- `apps/api/*`
- `apps/worker/*`
- `config/orchestrator/*`
- any governance ledger/readback module

## 4. Execution Steps

### M5A-S1: Add the write-record contract

Create `neotrade3/governance/artifact_writer.py`.

Add one stable write record object, recommended as:

- `GovernanceArtifactRecord`

Minimum fields:

- `source_run_id`
- `written_at`
- `artifact_path`
- `projected_assessment_count`
- `projected_issue_count`

Implementation rules:

- use immutable dataclass
- keep `artifact_path` relative to `project_root`
- keep the record as a side-effect summary, not the persisted business payload

Completion check:

- downstream callers can read one stable write result without inspecting filesystem internals

### M5A-S2: Add the canonical artifact writer

In `neotrade3/governance/artifact_writer.py`, add:

- `write_governance_handoff_artifact(...)`

Input:

- `project_root`
- `bundle: GovernanceHandoffBundle`
- `dry_run: bool = False`

Execution rules:

1. normalize `project_root` to `Path`
2. normalize `bundle.source_run_id`
3. reject empty or whitespace-only `source_run_id`
4. derive:
   - artifact directory: `var/artifacts/governance_handoffs/<source_run_id>/`
   - artifact file: `governance_handoff_bundle.json`
5. compute `written_at`
6. build persisted payload from:
   - `bundle.to_payload()`
   - `written_at`
7. if `dry_run` is false:
   - create parent directory
   - write deterministic JSON
8. return `GovernanceArtifactRecord`

Formatting rules:

- `indent=2`
- `sort_keys=True`
- newline-terminated file
- keep `ensure_ascii=False` for parity with the existing benchmark artifact writer

Implementation guards:

- do not mutate `bundle`
- do not read any ledger or readback file
- do not invent fallback run ids
- do not write more than the single canonical artifact file

Completion check:

- one real governance handoff bundle can be materialized into one canonical JSON artifact

### M5A-S3: Add focused tests

Create `tests/unit/test_m5_governance_artifact_writer.py`.

Test groups:

1. dry-run write-record test
   - build a real handoff bundle through the existing `M5` handoff path
   - call `write_governance_handoff_artifact(..., dry_run=True)`
   - assert returned:
     - `source_run_id`
     - `artifact_path`
     - `projected_assessment_count`
     - `projected_issue_count`
   - assert no directory or file is created
2. real-write artifact test
   - write to a temp project root
   - assert canonical directory exists
   - assert canonical file exists
   - read JSON and assert it equals:
     - `bundle.to_payload()`
     - plus `written_at`
3. relative-path contract test
   - assert `artifact_path` is project-root-relative
   - assert path ends with `governance_handoff_bundle.json`
4. validation test
   - construct an empty-run-id bundle
   - assert writer raises a deterministic validation error

Testing rule:

- reuse real `build_governance_handoff_from_assessment(...)` or `build_governance_handoff_from_batch_run(...)` output where practical
- do not test benchmark logic again
- test only the new artifact path and persistence contract

Completion check:

- `M5` persistence behavior is locked independently of ledger/readback/runtime concerns

### M5A-S4: Verify

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/governance/artifact_writer.py tests/unit/test_m5_governance_artifact_writer.py`
- `.venv/bin/python -m pytest tests/unit/test_m5_governance_artifact_writer.py`

Fallback if `pytest` is unavailable:

- keep `py_compile`
- run `.venv/bin/python` inline assertions against:
  - one `dry_run=True` call
  - one real write call with a temp project root
  - one empty-run-id validation case

Completion check:

- syntax passes
- best-available focused verification passes

### M5A-S5: Commit narrowly

Stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-m5-governance-artifact-persistence-baseline-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-m5-governance-artifact-persistence-baseline-plan.md`
- `neotrade3/governance/artifact_writer.py`
- `tests/unit/test_m5_governance_artifact_writer.py`

Exclude:

- `neotrade3/governance/__init__.py`
- `neotrade3/governance/handoff.py`
- `neotrade3/benchmark/*`
- `apps/api/*`
- `apps/worker/*`
- `config/orchestrator/*`
- unrelated workspace changes

## 5. Risks And Guards

Risk 1:

- widening the persistence slice into ledger/readback semantics

Guard:

- return only one write record
- do not add index files, list APIs, or readback helpers

Risk 2:

- mutating bundle semantics while writing

Guard:

- persist `bundle.to_payload()` directly
- allow only the minimal `written_at` metadata addition

Risk 3:

- making storage identity unstable through fallback directory names

Guard:

- reject empty `source_run_id`
- keep directory derivation tied directly to the canonical bundle field

Risk 4:

- widening public API too early through package-root exports

Guard:

- keep this slice file-local by default
- only revisit export ergonomics if implementation evidence creates a real immediate consumer need

## 6. Success Criteria

This slice is complete when:

- `neotrade3/governance/artifact_writer.py` exists as a real production owner
- a real `GovernanceHandoffBundle` can be written to the canonical JSON path
- `dry_run` and real-write share the same path contract
- persisted JSON shape is stable and deterministic
- empty `source_run_id` fails deterministically
- focused verification passes
