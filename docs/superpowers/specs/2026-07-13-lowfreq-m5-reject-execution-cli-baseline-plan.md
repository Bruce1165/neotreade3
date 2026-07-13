Status: active
Owner: lowfreq / governance
Scope: Implementation plan for the narrow `M5 reject execution CLI baseline` slice
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-13

# Lowfreq M5 Reject Execution CLI Baseline Plan

Date: 2026-07-13
Design:

- `docs/superpowers/specs/2026-07-13-lowfreq-m5-reject-execution-cli-baseline-design.md`

## 1. Goal

This slice only exposes the already-landed reject runtime through a formal CLI entrypoint.

This slice must:

- introduce `handoff` and `reject` CLI subcommands
- preserve existing handoff behavior
- expose reject execution output through JSON
- add focused CLI tests

This slice explicitly does not:

- change runtime or persistence contracts
- change worker/orchestrator behavior
- implement promotion approval

## 2. File Boundary

Production file:

- `neotrade3/governance/cli.py`

Focused test file:

- `tests/unit/test_m5_governance_cli.py`

Files intentionally not modified:

- `neotrade3/governance/runtime.py`
- `neotrade3/governance/run_ledger.py`
- `apps/worker/main.py`
- `neotrade3/orchestration/*`

## 3. Execution Steps

### M5REJCLI-S1: Convert parser to subcommands

Modify:

- `neotrade3/governance/cli.py`

Implementation:

1. add `handoff` subcommand
2. add `reject` subcommand
3. preserve current handoff arg names and semantics

### M5REJCLI-S2: Wire reject runtime

Modify:

- `neotrade3/governance/cli.py`

Implementation:

1. dispatch `handoff` to `run_governance_for_benchmark_run(...)`
2. dispatch `reject` to `run_governance_reject_execution(...)`
3. print stable JSON payloads for both

### M5REJCLI-S3: Lock focused CLI tests

Modify:

- `tests/unit/test_m5_governance_cli.py`

Required coverage:

1. parser requires subcommand
2. handoff parser accepts explicit arguments
3. reject parser accepts explicit arguments
4. reject dry-run writes nothing
5. reject materialization writes independent artifact/ledger
6. reject missing validation path raises

### M5REJCLI-S4: Minimum verification

Run at minimum:

- `python3 -m py_compile neotrade3/governance/cli.py tests/unit/test_m5_governance_cli.py`
- `python3 -m pytest tests/unit/test_m5_governance_cli.py`
- `git diff --check`

## 4. Risks And Guardrails

- **Risk: break existing handoff CLI**
  - Guardrail: preserve output payload and arg names under `handoff`
- **Risk: widen into worker/orchestrator**
  - Guardrail: change only CLI and CLI tests
- **Risk: overload one parser with mixed required args**
  - Guardrail: use explicit subcommands

## 5. Done Criteria

- CLI subcommands exist
- handoff output remains stable
- reject output is stable
- focused CLI tests pass
- no worker/orchestrator changes

## 6. Dual-Axis Audit

- `M1-M6` layer ownership:
  - this slice stays inside `M5` CLI entrypoint adoption
- `G1-G6` target mapping:
  - this is the minimum `G2` formal trigger surface for reject execution
- new contract introduced:
  - `governance cli reject` subcommand
- boundaries not touched:
  - no worker/orchestrator fit
  - no promotion approval
  - no `M6`
