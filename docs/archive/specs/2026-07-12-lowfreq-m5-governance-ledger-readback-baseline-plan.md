Status: active
Owner: lowfreq / governance
Scope: Implementation plan for the narrow `M5 governance ledger/readback baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq M5 Governance Ledger Readback Baseline Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-m5-governance-ledger-readback-baseline-design.md`

## 1. Goal

This plan implements only the next narrow `M5` slice after the governance artifact persistence baseline:

- one formal governance ledger/readback owner
- one stable `GovernanceRunLedgerRecord`
- one focused test carrier that locks materialize, readback, and latest-first listing behavior

This slice explicitly does not include:

- governance CLI
- API
- worker/orchestrator registration
- `M6` delivery consumption
- mutation of `GovernanceHandoffBundle`
- changes to the existing artifact path contract
- aggregate index files beyond ledger-file scanning
- package-root export widening unless implementation evidence proves it is immediately required

## 2. Starting Point

Repository evidence before this slice:

- `M5` already has a formal in-memory handoff surface:
  - `GovernanceHandoffBundle` in `neotrade3/governance/handoff.py`
  - `build_governance_handoff_from_assessment(...)`
  - `build_governance_handoff_from_batch_run(...)`
- `M5` already has a canonical artifact persistence owner:
  - `GovernanceArtifactRecord`
  - `write_governance_handoff_artifact(...)`
- `M4` already proves the narrow ledger/readback shape that should be mirrored:
  - `BenchmarkRunLedgerRecord`
  - `write_benchmark_run_ledger(...)`
  - `materialize_benchmark_batch_run(...)`
  - `read_benchmark_run_ledger(...)`
  - `read_benchmark_run_artifact(...)`
  - `list_benchmark_run_ledgers(...)`
- there is still no production owner that materializes one governance handoff bundle into a canonical ledger path or reads it back

So the implementation strategy is:

- reuse the existing `M5` handoff input and artifact writer without rebuilding governance semantics
- mirror the existing `M4` run-ledger shape narrowly
- freeze one canonical ledger path
- keep persistence ownership separate from CLI, API, and runtime surfaces

## 3. File Boundary

Production file:

- `neotrade3/governance/run_ledger.py`

Test file:

- `tests/unit/test_m5_governance_run_ledger.py`

Documentation files:

- `docs/superpowers/specs/2026-07-12-lowfreq-m5-governance-ledger-readback-baseline-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-m5-governance-ledger-readback-baseline-plan.md`

Files explicitly not in scope:

- `neotrade3/governance/artifact_writer.py`
- `neotrade3/governance/handoff.py`
- `neotrade3/governance/contracts.py`
- `neotrade3/governance/__init__.py`
- `neotrade3/benchmark/*`
- `apps/api/*`
- `apps/worker/*`
- `config/orchestrator/*`

Plan note:

- if implementation evidence proves that package-root import ergonomics are immediately required by the new tests or by an existing production consumer, revisit `neotrade3/governance/__init__.py` then; otherwise keep it untouched

## 4. Execution Steps

### M5L-S1: Add the ledger-record contract and path helpers

Create `neotrade3/governance/run_ledger.py`.

Add one stable ledger record object, recommended as:

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

Recommended collection-count fields:

- `diagnostic_count`
- `change_request_count`
- `experiment_request_count`
- `promotion_blocker_count`

Implementation rules:

- use immutable dataclass
- provide `from_dict(...)`
- provide `to_payload()`
- keep `artifact_path` and `ledger_path` relative to `project_root`
- keep the record as a side-effect summary, not the persisted business payload

Also add internal path helpers for:

- artifact file:
  - `var/artifacts/governance_handoffs/<source_run_id>/governance_handoff_bundle.json`
- ledger file:
  - `var/ledgers/governance_handoffs/<source_run_id>/governance_handoff_run.json`

Completion check:

- downstream callers can read one stable persisted summary without reconstructing filesystem paths manually

### M5L-S2: Add the canonical ledger writer and materialize entrypoint

In `neotrade3/governance/run_ledger.py`, add:

- `write_governance_run_ledger(...)`
- `materialize_governance_handoff(...)`

`write_governance_run_ledger(...)` input:

- `project_root`
- `bundle: GovernanceHandoffBundle`
- `artifact_record: GovernanceArtifactRecord`
- `dry_run: bool = False`

Execution rules:

1. normalize `project_root` to `Path`
2. normalize `bundle.source_run_id`
3. reject empty or whitespace-only `source_run_id`
4. derive canonical ledger file path
5. build persisted payload from:
   - `source_run_id`
   - `status="completed"`
   - `written_at=artifact_record.written_at`
   - `artifact_path=artifact_record.artifact_path`
   - `ledger_path`
   - `source_layer=bundle.source_layer`
   - projected counts
   - collection counts derived from the bundle
6. if `dry_run` is false:
   - create parent directory
   - write deterministic JSON
7. return `GovernanceRunLedgerRecord`

`materialize_governance_handoff(...)` execution rules:

1. call `write_governance_handoff_artifact(...)`
2. call `write_governance_run_ledger(...)`
3. return `GovernanceRunLedgerRecord`

Implementation guards:

- do not mutate `bundle`
- do not redesign or rewrite the existing artifact payload contract
- do not add aggregate index files
- do not add CLI or runtime behavior

Completion check:

- one real governance handoff bundle can be materialized into one canonical artifact file and one canonical ledger file

### M5L-S3: Add readback and latest-first listing helpers

In `neotrade3/governance/run_ledger.py`, add:

- `read_governance_run_ledger(...)`
- `read_governance_handoff_artifact(...)`
- `list_governance_run_ledgers(...)`

Execution rules:

1. `read_governance_run_ledger(...)`
   - return `None` if the ledger file does not exist
   - read JSON
   - return `None` for non-object roots
   - otherwise return `GovernanceRunLedgerRecord.from_dict(...)`
2. `read_governance_handoff_artifact(...)`
   - return `None` if the artifact file does not exist
   - read JSON
   - return the payload only when the root is a JSON object
3. `list_governance_run_ledgers(...)`
   - return `[]` if the ledger root directory does not exist
   - scan `*/governance_handoff_run.json`
   - skip unreadable or invalid JSON files
   - convert valid objects to `GovernanceRunLedgerRecord`
   - sort by `(written_at, source_run_id)` descending

Implementation guard:

- mirror the existing `M4` listing/readback posture exactly where evidence exists
- do not invent extra query filters or search semantics in this slice

Completion check:

- callers can recover one persisted governance ledger, one persisted governance artifact, and a latest-first run list without touching CLI/API/runtime layers

### M5L-S4: Add focused tests

Create `tests/unit/test_m5_governance_run_ledger.py`.

Test groups:

1. real materialize test
   - build a real handoff bundle through the existing `M5` handoff path
   - call `materialize_governance_handoff(...)`
   - assert artifact and ledger both exist
   - assert returned `GovernanceRunLedgerRecord` fields are stable
2. dry-run materialize test
   - call `materialize_governance_handoff(..., dry_run=True)`
   - assert neither artifact nor ledger file exists
   - assert the returned ledger record still carries the canonical relative paths
3. ledger readback test
   - materialize one real bundle
   - assert `read_governance_run_ledger(...)` returns the same persisted summary
4. artifact readback test
   - materialize one real bundle
   - assert `read_governance_handoff_artifact(...)` returns the persisted artifact payload object
5. latest-first listing test
   - materialize two bundles with different `source_run_id`
   - assert `list_governance_run_ledgers(...)` returns the newest first

Testing rule:

- reuse real `build_governance_handoff_from_assessment(...)` output where practical
- do not test benchmark logic again
- test only the new ledger/readback contract and materialize boundary

Completion check:

- `M5` ledger/readback behavior is locked independently of CLI/API/runtime concerns

### M5L-S5: Verify

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/governance/run_ledger.py tests/unit/test_m5_governance_run_ledger.py`
- `.venv/bin/python -m pytest tests/unit/test_m5_governance_run_ledger.py`

Fallback if `pytest` is unavailable:

- keep `py_compile`
- run `.venv/bin/python` inline assertions against:
  - one `dry_run=True` materialize call
  - one real materialize call with a temp project root
  - one ledger readback
  - one artifact readback
  - one latest-first listing case

Completion check:

- syntax passes
- best-available focused verification passes

### M5L-S6: Commit narrowly

Stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-m5-governance-ledger-readback-baseline-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-m5-governance-ledger-readback-baseline-plan.md`
- `neotrade3/governance/run_ledger.py`
- `tests/unit/test_m5_governance_run_ledger.py`

Exclude:

- `neotrade3/governance/artifact_writer.py`
- `neotrade3/governance/handoff.py`
- `neotrade3/governance/contracts.py`
- `neotrade3/governance/__init__.py`
- `neotrade3/benchmark/*`
- `apps/api/*`
- `apps/worker/*`
- `config/orchestrator/*`
- unrelated workspace changes

## 5. Risks And Guards

Risk 1:

- widening the persistence slice into CLI or API semantics because readback now exists

Guard:

- keep all entrypoints package-internal
- add no user-facing command or HTTP surface

Risk 2:

- drifting from the already-frozen artifact path contract

Guard:

- derive artifact readback strictly from the existing canonical artifact path
- do not rename the artifact filename

Risk 3:

- over-designing listing with an extra index file

Guard:

- scan ledger files only
- postpone aggregate index semantics until a real consumer appears

Risk 4:

- widening public API too early through package-root exports

Guard:

- keep `__init__.py` untouched by default
- only revisit export ergonomics if implementation evidence creates a real immediate need

## 6. Success Criteria

This slice is complete when:

- `neotrade3/governance/run_ledger.py` exists as a real production owner
- a real `GovernanceHandoffBundle` can be materialized into the canonical artifact and ledger paths
- readback can recover one persisted ledger and one persisted artifact by `source_run_id`
- listing returns persisted ledger records latest-first
- focused verification passes
