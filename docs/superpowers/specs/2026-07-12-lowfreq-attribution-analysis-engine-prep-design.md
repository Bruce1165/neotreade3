Status: active
Owner: lowfreq / scripts
Scope: Narrow extraction of the report-runner analysis engine preparation contract from attribution report script
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Analysis Engine Prep Design

Date: 2026-07-12

## 1. Goal

This design covers the next narrow slice after:

- `R1 run context contract`
- `R1 backtest payload source contract`
- `R2 stage progression contract`
- `R3 artifact path bundle contract`
- `R4 CLI success summary payload contract`

under the `report-runner orchestration` theme.

This slice freezes only the analysis-stage engine preparation contract that still lives inline in:

- [generate_lowfreq_top200_attribution_report.py:L903-L905](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L903-L905)
- consumed by [generate_lowfreq_top200_attribution_report.py:L906-L913](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L906-L913)

The goal is to:

- move the current analysis engine acquisition and override logic into one orchestration-side owner
- preserve the current `service._lowfreq_engine_v16()` source exactly
- preserve the current `MAX_POSITIONS` override behavior exactly
- keep `_analyze_topk(...)`, sqlite lifecycle, and artifact writes in the script
- add direct owner-focused coverage for the analysis engine preparation contract

This design is not:

- a rewrite of `_analyze_topk(...)`
- a backtest payload source rewrite
- an artifact write sequencing extraction
- a generic engine factory for all scripts
- a change to execution semantics beyond the current visible override

Project-phase note:

- domain: `lowfreq attribution analysis engine prep`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G6`

## 2. Scope

Included:

- extracting the current analysis-stage engine acquisition contract from the script
- preserving the current engine source:
  - `service._lowfreq_engine_v16()`
- preserving the current optional override:
  - `engine.MAX_POSITIONS = int(max_positions_override)`
- returning the prepared engine to the caller for later `_analyze_topk(...)` consumption
- adding owner-focused tests for default path and override path

Excluded:

- changing `_analyze_topk(...)` inputs or internals
- changing `execution_one_price_limit_only` consumption in `_analyze_topk(...)`
- changing sqlite open / close behavior
- changing backtest payload loading
- changing artifact generation or final summary emission
- changing how the engine is configured on the backtest-source path

## 3. Existing Context

Current repository evidence shows:

- after `backtest_payload` becomes ready, the script still owns one dedicated analysis-stage engine prep block:
  - [generate_lowfreq_top200_attribution_report.py:L903-L905](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L903-L905)
- that block has one stable visible behavior:
  - source the engine from `service._lowfreq_engine_v16()`
  - apply `MAX_POSITIONS = int(max_positions_override)` only when the override is provided
- downstream analysis consumes only the prepared engine object:
  - [generate_lowfreq_top200_attribution_report.py:L906-L913](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L906-L913)
- the remaining `R3` area is still a broader action-heavy block with multiple writes plus timestamp generation:
  - [generate_lowfreq_top200_attribution_report.py:L924-L955](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L924-L955)
- a neighboring runner also owns a visible engine acquisition and override pattern before execution:
  - [run_lowfreq_top200_capacity_experiment.py:L50-L58](file:///Users/mac/NeoTrade3/scripts/run_lowfreq_top200_capacity_experiment.py#L50-L58)

These facts together show:

- the next narrower orchestration contract is analysis engine preparation, not artifact write sequencing
- the stable visible surface here is engine source plus one optional override, not analysis semantics
- extracting this block is narrower than touching the wider `R3` write sequence

## 4. Approach Options

### Option A: Add one analysis-engine-prep owner and keep `_analyze_topk(...)`, sqlite, and artifact writes in the script (Recommended)

- create one dedicated orchestration module for preparing the analysis-stage engine
- let the owner keep the current source and `MAX_POSITIONS` override behavior
- let the script keep:
  - sqlite lifecycle
  - backtest payload loading
  - `_analyze_topk(...)`
  - stage progression writes
  - artifact writes

Pros:

- isolates one already-bounded runtime-preparation helper with minimal behavior risk
- matches the current code fact that the remaining block is only two visible operations
- is narrower than touching the broader `R3` write sequence

Cons:

- artifact sequencing still remains inline for now

### Option B: Skip to artifact write sequencing

Pros:

- leaves all runtime preparation in place

Cons:

- the write block is broader and action-heavy
- leaves a still-visible prep contract embedded in `main()`

### Option C: Merge analysis engine prep into a broader remaining `R1` bootstrap extraction

Pros:

- fewer orchestration lines remain in `main()`

Cons:

- mixes unrelated contracts with different rollback surfaces
- loses the current narrowness

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Add one new orchestration owner:

- `neotrade3/orchestration/report_runner_analysis_engine.py`

Recommended public function:

- `prepare_lowfreq_report_analysis_engine(...) -> LowFreqTradingEngineV16`

Recommended inputs:

- `service: BootstrapApiService`
- `max_positions_override: Optional[int]`

Why this file:

- the contract belongs to runner-side runtime preparation rather than analysis semantics
- the owner returns an already-configured engine without taking ownership of the analysis flow
- a dedicated file keeps runtime prep separate from backtest source and artifact writing

### 5.2 Contract Freeze

The helper must preserve the current observable behavior:

- acquire `engine = service._lowfreq_engine_v16()`
- when `max_positions_override` is not `None`, apply:
  - `engine.MAX_POSITIONS = int(max_positions_override)`
- return the engine object

The helper must preserve current coercion:

- `max_positions_override -> int(...)`

The helper must not:

- call `_analyze_topk(...)`
- write `status.json`
- open sqlite connections
- load backtest payload
- write artifacts
- apply any extra override that is not currently visible in the analysis-stage path

### 5.3 Script Boundary

The script should keep:

- `backtest_payload` loading
- `summary` extraction for `backtest_ready`
- `_analyze_topk(...)` invocation
- stage status writes
- sqlite connect / close
- artifact writes and final summary emission

The script should stop owning:

- the inline analysis-stage engine preparation block

### 5.4 Testing Strategy

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_report_runner_analysis_engine.py`

Minimum owner cases:

- returns the exact engine instance from `service._lowfreq_engine_v16()` when no override is provided
- applies `MAX_POSITIONS = int(max_positions_override)` when provided
- preserves pass-through behavior for the service source call count

Test style:

- use a fake service and fake engine
- no sqlite or script-level integration harness is required for this slice

## 6. Risks and Guardrails

Main risk:

- widening from analysis engine prep into `_analyze_topk(...)` or the broader `R3` write sequence

Guardrail:

- keep the new owner limited to engine source plus `MAX_POSITIONS` override only

Secondary risk:

- accidentally adding override behavior that is only used by the backtest-source path

Guardrail:

- freeze only the currently visible analysis-stage behavior and lock it with owner-focused tests

## 7. Implementation Outline

Planned steps:

1. add `report_runner_analysis_engine.py`
2. move the current analysis-stage engine prep block into the new owner
3. switch the script caller to consume the new owner
4. add owner-focused tests
5. run syntax checks and focused assertions

## 8. Success Criteria

This slice is complete when:

- the analysis-stage engine prep contract has one orchestration-side owner
- the script no longer owns the inline engine prep block
- engine source and `MAX_POSITIONS` override behavior remain unchanged
- `_analyze_topk(...)` and artifact writes remain untouched
- focused verification passes
- syntax verification passes
