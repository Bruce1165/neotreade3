Status: active
Owner: lowfreq / governance
Scope: Implementation plan for the narrow `M5 governance status transition CLI baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Governance Status Transition CLI Baseline Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-governance-status-transition-cli-baseline-design.md`

## 1. Goal

This slice only introduces the minimum formal CLI trigger for the already-persisted `M5 governance` status-transition runtime.

This slice must:

- add one `status-transition` subcommand to the governance CLI
- dispatch that subcommand to `run_governance_status_transition(...)`
- expose only the required runtime arguments:
  - `--project-root`
  - `--source-run-id`
  - `--validation-id`
  - `--dry-run`
- print one narrow JSON payload for the resulting transition record
- add focused CLI regression coverage

This slice explicitly does not:

- change runtime semantics
- change transition artifact or ledger schemas
- change worker behavior
- change API behavior
- change orchestrator behavior
- add downstream consumer migration
- touch `M6`

## 2. File Boundary

Spec files:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-governance-status-transition-cli-baseline-design.md`
- `docs/superpowers/specs/2026-07-13-lowfreq-m5-governance-status-transition-cli-baseline-plan.md`

Production file:

- `neotrade3/governance/cli.py`

Focused test file:

- `tests/unit/test_m5_governance_cli.py`

Files intentionally not modified:

- `neotrade3/governance/runtime.py`
- `neotrade3/governance/run_ledger.py`
- `neotrade3/governance/artifact_writer.py`
- `tests/unit/test_m5_governance_status_transition.py`
- `apps/worker/main.py`
- `apps/api/*`
- `config/orchestrator/*`

## 3. Execution Steps

### M5STC-S1: Extend parser surface

Modify:

- `neotrade3/governance/cli.py`

Implementation:

1. import `run_governance_status_transition(...)`
2. add one subparser:
   - `status-transition`
3. add the required arguments:
   - `--project-root`
   - `--source-run-id`
   - `--validation-id`
   - `--dry-run`

Implementation rules:

- keep the subcommand name hyphenated as `status-transition`
- keep argument semantics aligned with the existing runtime contract
- do not rename or reshape the existing `handoff` and `reject` subcommands

### M5STC-S2: Add main dispatch and JSON payload

Modify:

- `neotrade3/governance/cli.py`

Implementation:

1. extend `main()` branch handling for `status-transition`
2. call `run_governance_status_transition(...)`
3. print one JSON payload containing:
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

Implementation rules:

- keep CLI as a thin facade over the runtime owner
- do not re-read artifact payloads in the CLI layer
- do not suppress runtime errors
- keep current `handoff` and `reject` payload behavior unchanged

### M5STC-S3: Add focused parser coverage

Modify:

- `tests/unit/test_m5_governance_cli.py`

Implementation:

1. add one parser acceptance test for `status-transition`
2. assert:
   - `command == "status-transition"`
   - required argument parsing works
   - `dry_run` flag is recognized

Testing rules:

- mirror the current parser-test style already used for `handoff` and `reject`
- do not widen into argparse help-text snapshots

### M5STC-S4: Add focused execution coverage

Modify:

- `tests/unit/test_m5_governance_cli.py`

Test carrier pattern:

1. prepare temp project root with benchmark config
2. materialize one benchmark run
3. materialize one governance handoff
4. inject one rejected validation result
5. materialize one reject execution proof
6. invoke CLI `status-transition`
7. assert JSON payload and persisted outputs

Required coverage:

1. dry-run returns a valid payload and writes nothing
2. non-dry-run writes transition artifact and ledger
3. payload fields align with the persisted transition ledger record
4. missing reject proof fails deterministically through the CLI path

Testing rules:

- reuse the existing helper setup from `test_m5_governance_cli.py`
- keep the CLI test thin and avoid duplicating transition-runtime internal assertions already covered elsewhere

### M5STC-S5: Minimum verification

Run at minimum:

- `python3 -m py_compile neotrade3/governance/cli.py tests/unit/test_m5_governance_cli.py`
- `python3 -m pytest tests/unit/test_m5_governance_cli.py tests/unit/test_m5_governance_status_transition.py`
- `git diff --check`

## 4. Risks And Guardrails

- **Risk: widen this slice into runtime redesign**
  - Guardrail: restrict production changes to `neotrade3/governance/cli.py`
- **Risk: drift from the existing operator-facing CLI pattern**
  - Guardrail: mirror `handoff` and `reject` parser/output structure
- **Risk: duplicate runtime logic inside CLI**
  - Guardrail: keep CLI as a thin dispatcher and payload formatter only
- **Risk: blur proof requirements**
  - Guardrail: preserve runtime pass-through failure when reject proof is missing

## 5. Done Criteria

- `governance CLI` accepts `status-transition`
- `status-transition` dispatches to `run_governance_status_transition(...)`
- CLI prints the narrow transition JSON payload
- dry-run and persisted-write paths are covered
- missing reject proof is covered
- focused verification passes
- no `worker/API/orchestrator/runtime-schema` diff appears in this slice

## 6. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays entirely inside `M5` formal CLI surface completion
- `G1-G6` target mapping:
  - this is the next minimum `G5` step that makes the persisted transition owner directly operable from the governance CLI
- new contract introduced:
  - formal `status-transition` CLI subcommand
  - narrow CLI JSON summary for `GovernanceStatusTransitionRecord`
- boundaries not touched:
  - no runtime semantic rewrite
  - no artifact or ledger schema change
  - no worker/API/orchestrator adoption
  - no `M6`
