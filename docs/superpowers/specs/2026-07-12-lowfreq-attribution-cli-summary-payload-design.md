Status: active
Owner: lowfreq / scripts
Scope: Narrow extraction of the report-runner CLI success summary payload contract
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution CLI Summary Payload Design

Date: 2026-07-12

## 1. Goal

This design covers the next narrow slice after:

- `R2 stage progression contract`
- `R3 artifact path bundle contract`

under the `report-runner orchestration` theme.

This slice freezes only the success summary payload that is currently emitted by:

- [generate_lowfreq_top200_attribution_report.py:L986-L1000](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L986-L1000)

The goal is to:

- move the visible success summary projection into one orchestration-side owner
- keep the script responsible for `print(json.dumps(...))`
- preserve the current top-level success fields exactly
- preserve the current reuse of runner outputs:
  - `report_id`
  - `output_dir`
  - artifact paths
  - `aggregate`

This design is not:

- a generic CLI response framework
- a failure payload redesign
- a rewrite of `print(...)`
- a rewrite of `json.dumps(...)`
- a rewrite of runner execution ordering

Project-phase note:

- domain: `lowfreq attribution CLI summary payload`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G6`

## 2. Scope

Included:

- extracting the final success payload projection
- preserving the current field set:
  - `status`
  - `report_id`
  - `output_dir`
  - `ranking_path`
  - `segments_path`
  - `attribution_path`
  - `report_path`
  - `aggregate`
- preserving the current success marker:
  - `"status": "ok"`
- adding owner-focused tests for the payload contract

Excluded:

- changing how stdout is produced
- changing JSON formatting:
  - `ensure_ascii=False`
  - `indent=2`
- changing failure handling
- changing artifact file names
- changing `aggregate` semantics
- changing runner stage/status behavior

## 3. Existing Context

Current repository evidence shows:

- the attribution report script still owns one inline success summary payload:
  - [generate_lowfreq_top200_attribution_report.py:L986-L1000](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L986-L1000)
- a neighboring report runner uses the same broad pattern:
  - write artifacts first
  - then emit one final success summary payload
  - [generate_lowfreq_top200_process_research_report.py:L1033-L1047](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_process_research_report.py#L1033-L1047)
- a higher-level runner consumes the attribution report stdout as one JSON success payload:
  - [run_lowfreq_top200_capacity_experiment.py:L108-L119](file:///Users/mac/NeoTrade3/scripts/run_lowfreq_top200_capacity_experiment.py#L108-L119)

These facts together show:

- the final CLI summary is a visible runner contract
- the visible contract is the payload projection itself, not the `print(json.dumps(...))` action
- the payload is still narrow enough to extract without widening into a general runner transport layer

## 4. Approach Options

### Option A: Extract only the success payload builder and keep stdout emission in the script (Recommended)

- create one orchestration-side payload owner
- let the script keep `print(json.dumps(...))`
- preserve the current field set exactly

Pros:

- isolates the visible contract with minimal runtime risk
- matches previous thin-consumer slices
- avoids pulling transport concerns into the owner

Cons:

- `print(...)` remains inline in the script

### Option B: Extract the whole CLI emit action into a helper

Pros:

- fewer lines in the script tail

Cons:

- mixes payload projection with transport behavior
- broadens the slice beyond the visible contract

### Option C: Leave the summary inline and stop at `R3`

Pros:

- most conservative

Cons:

- leaves one still-visible runner contract embedded in the script

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Add one new orchestration owner:

- `neotrade3/orchestration/report_runner_cli_summary.py`

Recommended public function:

- `build_lowfreq_report_success_summary(...) -> dict[str, Any]`

Recommended inputs:

- `report_id: str`
- `output_dir: Path`
- `ranking_path: Path`
- `segments_path: Path`
- `attribution_path: Path`
- `report_path: Path`
- `aggregate: dict[str, Any]`

Why this file:

- the contract belongs to runner-side completion reporting
- it is separate from stage progression and artifact path ownership
- it keeps the success payload discoverable without mixing it into transport code

### 5.2 Contract Freeze

The helper must preserve the current observable payload shape:

- `status`
- `report_id`
- `output_dir`
- `ranking_path`
- `segments_path`
- `attribution_path`
- `report_path`
- `aggregate`

The helper must preserve current coercions:

- `status -> "ok"`
- all path-like inputs -> `str(...)`
- `report_id -> str(...)`
- `aggregate -> pass through`

The helper must not:

- print
- serialize JSON
- handle stderr
- create files
- mutate `aggregate`

### 5.3 Script Boundary

The script should keep:

- the final `print(json.dumps(...))`
- `ensure_ascii=False`
- `indent=2`
- `return 0`

The script should stop owning:

- the inline success payload projection

### 5.4 Testing Strategy

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_report_runner_cli_summary.py`

Minimum cases:

- projects the current success payload with all expected top-level fields
- preserves `"status": "ok"`
- stringifies path-like inputs
- passes `aggregate` through by identity

## 6. Risks and Guardrails

Main risk:

- widening the slice into a generic stdout-emission abstraction

Guardrail:

- keep the owner payload-only and leave `print(json.dumps(...))` in the script

Secondary risk:

- changing the current field set while attempting to simplify the payload

Guardrail:

- freeze the current eight top-level fields in owner-focused tests

## 7. Implementation Outline

Planned steps:

1. add `report_runner_cli_summary.py`
2. implement `build_lowfreq_report_success_summary(...)`
3. switch the script tail to consume the summary payload builder
4. add owner-focused tests
5. run syntax checks and focused assertions

## 8. Success Criteria

This slice is complete when:

- the final success summary payload has one orchestration-side owner
- the script no longer owns the inline payload dict
- stdout emission remains in the script
- the field set remains unchanged
- owner-focused verification passes
- syntax verification passes
