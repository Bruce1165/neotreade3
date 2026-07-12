Status: active
Owner: lowfreq / scripts
Scope: Narrow extraction of the report-runner run context contract from attribution report script
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Run Context Design

Date: 2026-07-12

## 1. Goal

This design covers the next narrow slice after:

- `R2 stage progression contract`
- `R3 artifact path bundle contract`
- `R4 CLI success summary payload contract`

under the `report-runner orchestration` theme.

This slice freezes only the pre-run context that still lives inline in:

- [generate_lowfreq_top200_attribution_report.py:L887-L891](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L887-L891)

The goal is to:

- move the current run-context projection into one orchestration-side owner
- preserve the current `top_label` rule derived from `limit`
- preserve the current `report_id` fallback shape exactly
- preserve the current `output_dir` resolution exactly
- keep directory creation and later orchestration steps in the script
- add direct owner-focused coverage for the run-context contract

This design is not:

- a sqlite lifecycle extraction
- a backtest payload preparation rewrite
- an engine bootstrap rewrite
- a rewrite of `_write_status(...)`
- a rewrite of artifact write ordering
- a generic runner bootstrap framework for all scripts

Project-phase note:

- domain: `lowfreq attribution run context`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G6`

## 2. Scope

Included:

- extracting the current run-context projection from `main()`
- preserving the current top-level context fields:
  - `top_label`
  - `report_id`
  - `output_dir`
- preserving the current fallback rule:
  - `report_id -> "{top_label}_{year}_{timestamp}"`
- preserving the current output root:
  - `PROJECT_ROOT / "var/artifacts" / f"lowfreq_{top_label}_attribution" / report_id`
- adding owner-focused tests for fallback, override, and path projection

Excluded:

- changing the UTC timestamp format
- changing where the initial `status.json` is written
- changing directory creation behavior
- changing sqlite open / close behavior
- changing backtest loading inputs
- changing engine preparation
- changing artifact file names

## 3. Existing Context

Current repository evidence shows:

- the attribution report script still owns one inline run-context block:
  - [generate_lowfreq_top200_attribution_report.py:L887-L891](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L887-L891)
- that block currently computes:
  - `top_label`
  - `report_id`
  - `output_dir`
  - `output_dir.mkdir(...)`
- the resolved `report_id` and `output_dir` are then reused by multiple downstream orchestration surfaces:
  - initial status write:
    - [generate_lowfreq_top200_attribution_report.py:L892-L899](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L892-L899)
  - artifact path bundle:
    - [generate_lowfreq_top200_attribution_report.py:L947-L955](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L947-L955)
  - `done` status:
    - [generate_lowfreq_top200_attribution_report.py:L978-L987](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L978-L987)
  - final CLI summary:
    - [generate_lowfreq_top200_attribution_report.py:L989-L1004](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L989-L1004)
- a neighboring runner uses the same broad startup pattern of:
  - `report_id` fallback
  - `output_dir` resolution
  - `output_dir.mkdir(...)`
  - [generate_lowfreq_top200_process_research_report.py:L756-L758](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_process_research_report.py#L756-L758)
- another neighboring runner already isolates a similar startup path projection into a dedicated helper:
  - [_build_payload_path](file:///Users/mac/NeoTrade3/scripts/run_lowfreq_top200_capacity_experiment.py#L18-L25)
  - then creates the parent directory in `main()`:
    - [run_lowfreq_top200_capacity_experiment.py:L43-L48](file:///Users/mac/NeoTrade3/scripts/run_lowfreq_top200_capacity_experiment.py#L43-L48)

These facts together show:

- the current inline startup block is a real orchestration contract
- the narrow visible contract is the run-context projection, not the directory-creation side effect
- extracting only the projection keeps this slice smaller than touching sqlite or artifact sequencing

## 4. Approach Options

### Option A: Add one run-context owner and keep `mkdir(...)` plus later orchestration in the script (Recommended)

- create one dedicated orchestration module for `top_label / report_id / output_dir`
- let the script keep:
  - directory creation
  - initial status emission
  - sqlite lifecycle
  - backtest preparation
  - engine preparation
  - artifact writes
- let the owner project only the current run context

Pros:

- isolates one visible startup contract with minimal runtime risk
- matches the repository pattern where path projection can be extracted without moving side effects
- avoids overlapping with `R2` stage progression and broader `R1` lifecycle concerns

Cons:

- `mkdir(...)` remains inline for now

### Option B: Move the entire startup bootstrap block into one helper

Pros:

- fewer lines remain at the top of `main()`

Cons:

- mixes projection with side effects
- starts absorbing sqlite and status-adjacent behavior too early
- broadens the slice beyond the visible contract

### Option C: Skip `R1` and move to artifact write sequencing

Pros:

- keeps startup untouched

Cons:

- artifact write sequencing is currently wider and more action-heavy
- leaves one still-visible run-context contract embedded in the script

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Add one new orchestration owner:

- `neotrade3/orchestration/report_runner_run_context.py`

Recommended public function:

- `build_lowfreq_report_run_context(...) -> dict[str, Any]`

Recommended inputs:

- `project_root: Path`
- `year: int`
- `limit: int`
- `report_id: str`
- `timestamp: str`

Why this file:

- the contract belongs to runner-side startup orchestration rather than analysis semantics
- it is separate from stage progression, artifact path ownership, and CLI summary ownership
- a dedicated file keeps the startup contract discoverable without mixing projection with side effects

### 5.2 Contract Freeze

The helper must preserve the current observable payload shape:

- `top_label`
- `report_id`
- `output_dir`

The helper must preserve the current rules:

- `top_label -> f"top{int(limit)}"`
- `report_id -> str(report_id or f"{top_label}_{int(year)}_{timestamp}")`
- `output_dir -> project_root / "var/artifacts" / f"lowfreq_{top_label}_attribution" / report_id`

The helper must preserve current coercions:

- `year -> int(...)`
- `limit -> int(...)`
- `report_id -> str(...)`
- `top_label -> str`
- `output_dir -> Path`

The helper must not:

- create directories
- open sqlite connections
- emit status payloads
- load backtest payloads
- configure the engine
- write artifacts

### 5.3 Script Boundary

The script should keep:

- `_setup_logging(...)`
- service construction
- `output_dir.mkdir(parents=True, exist_ok=True)`
- initial `status.json` write
- sqlite open / close
- ranking / backtest / analysis execution order
- artifact writes
- final CLI summary output

The script should stop owning:

- the inline `top_label / report_id / output_dir` projection

### 5.4 Testing Strategy

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_report_runner_run_context.py`

Minimum owner cases:

- projects the current `top_label / report_id / output_dir` payload from explicit inputs
- preserves the fallback `report_id` shape with the injected timestamp
- preserves explicit `report_id` override without rewriting it
- coerces `year` and `limit` with the current `int(...)` behavior

Nearby consumer rerun:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - syntax verification only; no broad integration harness is required for this slice

## 6. Risks and Guardrails

Main risk:

- accidentally widening from run-context projection into startup side effects

Guardrail:

- keep the helper projection-only and leave `mkdir(...)`, status emission, and sqlite lifecycle in the script

Secondary risk:

- changing the fallback `report_id` shape while trying to simplify naming

Guardrail:

- freeze the current fallback format and lock it in owner-focused tests with an injected timestamp

## 7. Implementation Outline

Planned steps:

1. add `report_runner_run_context.py`
2. implement `build_lowfreq_report_run_context(...)`
3. switch the script startup block to consume the resolved run context
4. add owner-focused tests
5. run syntax checks and focused assertions

## 8. Success Criteria

This slice is complete when:

- the visible run-context projection has one orchestration-side owner
- the script no longer owns the inline `top_label / report_id / output_dir` block
- directory creation remains in the script
- `report_id` fallback shape remains unchanged
- `output_dir` resolution remains unchanged
- owner-focused tests pass
- syntax verification passes
