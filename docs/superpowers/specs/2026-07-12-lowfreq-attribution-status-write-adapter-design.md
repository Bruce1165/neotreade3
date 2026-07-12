Status: active
Owner: lowfreq / scripts
Scope: Narrow extraction of the shared `status.json` write adapter from the attribution report runner
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Status Write Adapter Design

Date: 2026-07-12

## 1. Goal

This design covers the next narrow slice after:

- `R1 run context contract`
- `R1 backtest payload source contract`
- `R1 analysis engine prep contract`
- `R2 stage progression contract`
- `R3 artifact path bundle contract`
- `R3 artifact write sequencing contract`
- `R4 CLI success summary payload contract`

under the `report-runner orchestration` theme.

This slice freezes only the remaining shared `status.json` write adapter that still exists in two places:

- [generate_lowfreq_top200_attribution_report.py:L83-L93](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L83-L93)
- [report_runner_artifact_writes.py:L19-L29](file:///Users/mac/NeoTrade3/neotrade3/orchestration/report_runner_artifact_writes.py#L19-L29)

The goal is to:

- extract the current `status.json` write side effect into one orchestration-side owner
- preserve the current timestamp format, JSON formatting, file path, and trailing newline exactly
- let both staged runner status updates and final `done` status registration consume the same writer
- keep stage payload projection and CLI success-summary projection in their current owners

This design is not:

- a rewrite of stage payload semantics
- a rewrite of final CLI summary emission
- a generic JSON writer abstraction for the repository
- a broad `main()` refactor

Project-phase note:

- domain: `lowfreq attribution status write adapter`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G6`

## 2. Scope

Included:

- extracting the current `status.json` write semantics into one shared orchestration owner
- preserving current `updated_at` generation:
  - `datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")`
- preserving current JSON formatting:
  - `ensure_ascii=False`
  - `indent=2`
  - trailing `"\n"`
- switching the script-side staged status writes to the new owner
- switching the artifact-write owner final `done` status write to the same owner

Excluded:

- changing `build_initializing_report_status(...)`
- changing `build_ranking_ready_report_status(...)`
- changing `build_backtest_ready_report_status(...)`
- changing `build_analysis_ready_report_status(...)`
- changing `build_done_report_status(...)`
- changing artifact write sequencing
- changing final `print(json.dumps(...))`

## 3. Existing Context

Current repository evidence shows:

- stage payload projection is already ownerized in:
  - [report_runner_status.py:L19-L81](file:///Users/mac/NeoTrade3/neotrade3/orchestration/report_runner_status.py#L19-L81)
- final CLI result payload projection is already ownerized in:
  - [report_runner_cli_summary.py:L9-L28](file:///Users/mac/NeoTrade3/neotrade3/orchestration/report_runner_cli_summary.py#L9-L28)
- the script still performs four staged status writes through its private adapter:
  - [generate_lowfreq_top200_attribution_report.py:L848-L901](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L848-L901)
- the artifact-write owner also carries a second private status writer for the final `done` status:
  - [report_runner_artifact_writes.py:L80-L89](file:///Users/mac/NeoTrade3/neotrade3/orchestration/report_runner_artifact_writes.py#L80-L89)
- the final CLI output path is already down to one thin `print(json.dumps(build_lowfreq_report_success_summary(...)))` site:
  - [generate_lowfreq_top200_attribution_report.py:L933-L947](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L933-L947)

These facts together show:

- the more valuable remaining shared contract is not the CLI payload print
- the more valuable remaining shared contract is the duplicated `status.json` side-effect adapter
- that adapter now spans both runner stage progression and artifact completion

## 4. Approach Options

### Option A: Extract one shared status writer and keep payload builders unchanged (Recommended)

- add one orchestration owner for `status.json` writes
- let `report_runner_status.py` remain the payload-projection owner
- let the script and artifact-write owner both call the same writer

Pros:

- removes the only duplicated report-runner side-effect adapter now visible across owners
- preserves the clean split between payload projection and file IO
- is narrower and better evidenced than wrapping the final CLI `print(...)`

Cons:

- introduces one more small orchestration owner

### Option B: Extract final CLI summary emission first

Pros:

- would further slim `main()`

Cons:

- current evidence shows only one remaining print site
- most of that surface is already canonicalized by `build_lowfreq_report_success_summary(...)`
- the remaining value would be only a very thin `print(json.dumps(...))` wrapper

### Option C: Merge write logic into `report_runner_status.py`

Pros:

- fewer files

Cons:

- mixes pure payload projection with file side effects
- weakens the boundary already established by `report_runner_cli_summary.py` and other orchestration owners

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Add one new orchestration owner:

- `neotrade3/orchestration/report_runner_status_writer.py`

Recommended public function:

- `write_lowfreq_report_status(...) -> None`

Recommended shape:

- `output_dir: Path`
- `stage: str`
- arbitrary extra payload fields via `**extra`

Why this file:

- the contract is runner-side status emission, not status payload semantics
- the same write semantics are now consumed by both `main()` and `report_runner_artifact_writes.py`
- a dedicated owner preserves the separation between projection and side effects

### 5.2 Contract Freeze

The new helper must preserve the current observable behavior:

- write to `(output_dir / "status.json")`
- always include:
  - `stage`
  - `updated_at`
- merge forwarded extra fields after those defaults
- serialize with:
  - `json.dumps(payload, ensure_ascii=False, indent=2) + "\n"`
- write with:
  - `encoding="utf-8"`

The helper must support the two current call classes unchanged in meaning:

1. staged runner status writes in `main()`
2. final `done` status registration inside artifact sequencing

The helper must not:

- decide which stage payload to build
- rename any stage
- change when statuses are emitted
- print CLI output

### 5.3 Consumer Boundary

The script should keep:

- deciding when `initializing`, `ranking_ready`, `backtest_ready`, and `analysis_ready` are emitted
- final CLI success-summary emission

The script should stop owning:

- the private `_write_status(...)` adapter implementation

The artifact-write owner should keep:

- deciding that final `done` status is emitted after artifact writes complete

The artifact-write owner should stop owning:

- the private `_write_status_file(...)` adapter implementation

### 5.4 Testing Strategy

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_report_runner_status_writer.py`

Minimum cases:

- writes `status.json` with the current JSON formatting and trailing newline
- injects `updated_at` using the current UTC timestamp format
- preserves payload forwarding for stage-specific fields
- supports the current `done`-style payload forwarding path

Test style:

- use temporary directories
- use direct owner calls
- avoid broad script integration

## 6. Risks and Guardrails

Main risk:

- widening from a shared status writer into stage-semantics rewrites

Guardrail:

- keep payload builders in `report_runner_status.py`
- keep the new owner limited to the current file-write adapter semantics

Secondary risk:

- accidentally changing `updated_at` shape or JSON formatting

Guardrail:

- lock timestamp presence, target path, JSON formatting, and trailing newline in owner-focused tests

## 7. Implementation Outline

Planned steps:

1. add `report_runner_status_writer.py`
2. move current status-write adapter semantics into the new owner
3. switch `generate_lowfreq_top200_attribution_report.py` staged status calls to the new owner
4. switch `report_runner_artifact_writes.py` final `done` status call to the same owner
5. add owner-focused tests
6. run syntax checks and inline assertions

## 8. Success Criteria

This slice is complete when:

- there is one shared orchestration owner for `status.json` writes
- the script no longer defines `_write_status(...)`
- `report_runner_artifact_writes.py` no longer defines its private status writer
- all current stage payloads and final `done` payload remain unchanged
- focused verification passes
- syntax verification passes
