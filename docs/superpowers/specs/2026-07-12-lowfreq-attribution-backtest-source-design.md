Status: active
Owner: lowfreq / scripts
Scope: Narrow extraction of the report-runner backtest payload source contract from attribution report script
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Backtest Source Design

Date: 2026-07-12

## 1. Goal

This design covers the next narrow slice after:

- `R1 run context contract`
- `R2 stage progression contract`
- `R3 artifact path bundle contract`
- `R4 CLI success summary payload contract`

under the `report-runner orchestration` theme.

This slice freezes only the backtest payload source contract that still lives inline in:

- [generate_lowfreq_top200_attribution_report.py:L98-L130](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L98-L130)
- consumed from [generate_lowfreq_top200_attribution_report.py:L917-L925](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L917-L925)

The goal is to:

- move the current backtest payload sourcing logic into one orchestration-side owner
- preserve the current two-branch behavior exactly:
  - optional `backtest_json` override
  - engine `run_backtest(...)` fallback
- preserve the current engine override knobs exactly
- preserve the current payload shape returned to downstream analysis exactly
- keep sqlite lifecycle and analysis-stage engine preparation in the script
- add direct owner-focused coverage for the backtest source contract

This design is not:

- a sqlite lifecycle extraction
- an analysis-stage engine bootstrap rewrite
- a rewrite of `build_attribution_backtest_payload(...)`
- an artifact write sequencing extraction
- a generic backtest framework for all scripts

Project-phase note:

- domain: `lowfreq attribution backtest source`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G6`

## 2. Scope

Included:

- extracting the current `_load_backtest_payload(...)` contract from the script
- preserving the current file-override behavior:
  - `if backtest_json and backtest_json.exists(): json.loads(...)`
- preserving the current engine fallback behavior:
  - `service._lowfreq_engine_v16()`
  - `MAX_POSITIONS` override
  - `EXEC_BLOCK_ONLY_ONE_PRICE_LIMIT` override
  - `run_backtest(..., include_trades=True)`
- preserving the current payload normalization:
  - split `metrics` into `summary` and `trades`
  - remove `summary["trades"]`
  - delegate payload envelope building to `build_attribution_backtest_payload(...)`
- adding owner-focused tests for override path, engine path, and normalization

Excluded:

- changing backtest date inputs
- changing initial capital semantics
- changing attribution backtest payload keys
- changing sqlite open / close behavior
- changing analysis-stage `engine = service._lowfreq_engine_v16()` behavior
- changing artifact generation or final summary emission

## 3. Existing Context

Current repository evidence shows:

- the attribution report script still owns one dedicated helper for backtest payload sourcing:
  - [generate_lowfreq_top200_attribution_report.py:L98-L130](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L98-L130)
- that helper already exposes a stable visible branch structure:
  - file override branch:
    - [generate_lowfreq_top200_attribution_report.py:L108-L109](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L108-L109)
  - engine fallback branch:
    - [generate_lowfreq_top200_attribution_report.py:L111-L125](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L111-L125)
- the helper is consumed from `main()` as one orchestration step before analysis:
  - [generate_lowfreq_top200_attribution_report.py:L917-L925](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L917-L925)
- downstream analysis consumes only the resulting `backtest_payload`, not the sourcing details:
  - [generate_lowfreq_top200_attribution_report.py:L938-L945](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L938-L945)
- the payload envelope itself is already ownerized in M3:
  - [attribution_backtest_payload.py:L8-L29](file:///Users/mac/NeoTrade3/neotrade3/analysis/attribution_backtest_payload.py#L8-L29)
- a neighboring runner directly performs a similar engine backtest call with the same visible flags:
  - [run_lowfreq_top200_capacity_experiment.py:L50-L58](file:///Users/mac/NeoTrade3/scripts/run_lowfreq_top200_capacity_experiment.py#L50-L58)
  - it also persists `execution_one_price_limit_only` in its visible payload:
    - [run_lowfreq_top200_capacity_experiment.py:L71-L73](file:///Users/mac/NeoTrade3/scripts/run_lowfreq_top200_capacity_experiment.py#L71-L73)
- by contrast, the remaining `R3` area is still one action-heavy write block with 4 writes plus timestamp generation:
  - [generate_lowfreq_top200_attribution_report.py:L965-L983](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L965-L983)

These facts together show:

- the next narrower orchestration contract is the backtest payload source, not artifact write sequencing
- the stable visible surface here is the source decision and normalization, not the already-ownerized payload envelope
- extracting this helper is narrower than touching sqlite lifecycle or the analysis-stage engine bootstrap

## 4. Approach Options

### Option A: Add one backtest-source owner and keep sqlite plus analysis-stage engine prep in the script (Recommended)

- create one dedicated orchestration module for loading the report backtest payload
- let the owner keep the current two-branch sourcing behavior
- let the script keep:
  - sqlite lifecycle
  - ranking load
  - analysis-stage engine acquisition
  - stage progression writes
  - artifact writes

Pros:

- isolates one already-bounded orchestration helper with minimal runtime risk
- matches the current code fact that the sourcing logic is already grouped in one function
- keeps the slice narrower than touching the broader `R3` write block

Cons:

- the later analysis-stage engine bootstrap still remains inline for now

### Option B: Extract the whole remaining `R1` bootstrap chain together

Pros:

- fewer orchestration lines remain in `main()`

Cons:

- mixes sqlite lifecycle, backtest sourcing, and analysis engine prep into one wider slice
- loses the already-visible helper boundary
- raises rollback and verification cost

### Option C: Skip to artifact write sequencing

Pros:

- leaves startup and backtest preparation untouched

Cons:

- the write block is wider, more action-heavy, and less contract-shaped
- leaves an existing standalone sourcing helper embedded in the script

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Add one new orchestration owner:

- `neotrade3/orchestration/report_runner_backtest_source.py`

Recommended public function:

- `load_lowfreq_report_backtest_payload(...) -> dict[str, Any]`

Recommended inputs:

- `service: BootstrapApiService`
- `backtest_json: Optional[Path]`
- `start_date: date`
- `end_date: date`
- `initial_capital: float`
- `max_positions_override: Optional[int]`
- `execution_one_price_limit_only: bool`
- `generated_at: str`

Why this file:

- the contract belongs to runner-side sourcing/orchestration rather than analysis semantics
- the payload envelope is already owned by M3, so this file should own only the source decision and runtime sourcing
- a dedicated file keeps the side-effecting backtest acquisition separate from stage progression and artifact writing

### 5.2 Contract Freeze

The helper must preserve the current observable branch behavior:

- if `backtest_json` exists, return `json.loads(backtest_json.read_text(...))`
- otherwise:
  - build `engine = service._lowfreq_engine_v16()`
  - apply `MAX_POSITIONS = int(max_positions_override)` when provided
  - apply `EXEC_BLOCK_ONLY_ONE_PRICE_LIMIT = True` when requested
  - call `engine.run_backtest(..., include_trades=True)`
  - separate `trades` from `summary`
  - remove `summary["trades"]`
  - return `build_attribution_backtest_payload(...)`

The helper must preserve current coercions:

- `initial_capital -> float(...)`
- `max_positions_override -> int(...)`
- `execution_one_price_limit_only -> bool gate`

The helper must preserve current payload semantics:

- file branch passes through JSON as loaded
- engine branch returns the current attribution backtest envelope

The helper must not:

- open sqlite connections
- write `status.json`
- create output directories
- acquire the analysis-stage engine used by `_analyze_topk(...)`
- write artifacts

### 5.3 Script Boundary

The script should keep:

- run context resolution
- `output_dir.mkdir(...)`
- stage status writes
- sqlite connect / close
- ranking load
- later analysis engine preparation:
  - [generate_lowfreq_top200_attribution_report.py:L935-L937](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L935-L937)
- artifact writes and final summary emission

The script should stop owning:

- `_load_backtest_payload(...)`

### 5.4 Testing Strategy

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_report_runner_backtest_source.py`

Minimum owner cases:

- returns file JSON unchanged when `backtest_json` exists
- applies engine overrides and `include_trades=True` on the fallback path
- removes `trades` from `summary` before calling `build_attribution_backtest_payload(...)`
- preserves `generated_at` and `requested_by="script"` in the built payload path

Test style:

- use a fake service and fake engine instead of broad runner integration
- no sqlite or script-level integration harness is required for this slice

## 6. Risks and Guardrails

Main risk:

- widening from backtest source ownership into the whole remaining `R1` chain

Guardrail:

- keep the new owner limited to `_load_backtest_payload(...)` semantics only

Secondary risk:

- accidentally drifting payload semantics between the file branch and engine branch

Guardrail:

- lock both branches explicitly in owner-focused tests

## 7. Implementation Outline

Planned steps:

1. add `report_runner_backtest_source.py`
2. move the current `_load_backtest_payload(...)` logic into the new owner
3. switch the script caller to consume the new owner
4. remove the inline script helper
5. add owner-focused tests
6. run syntax checks and focused assertions

## 8. Success Criteria

This slice is complete when:

- the backtest payload source contract has one orchestration-side owner
- the script no longer owns `_load_backtest_payload(...)`
- file override and engine fallback behavior remain unchanged
- the M3 payload envelope remains reused, not duplicated
- focused verification passes
- syntax verification passes
