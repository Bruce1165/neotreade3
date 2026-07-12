Status: active
Owner: lowfreq / scripts
Scope: Reframe the remaining attribution report script work as report-runner orchestration
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Report-Runner Orchestration Design

Date: 2026-07-12

## 1. Goal

This design redefines the topic ownership for the remaining work in:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)

The previous narrow slices have already extracted the report-side `M3` contracts that were supported by repository evidence:

- reasoning owners
- daily audit payload owners
- report row owners
- aggregate owner
- markdown formatter owner
- artifact payload owner
- wave segment payload owner
- ranking payload owner
- backtest payload owner

After those extractions, the remaining dense logic in the script is no longer best described as `analysis contract` ownership.

The goal of this design is to:

- explicitly reclassify the remaining script responsibilities as `report-runner orchestration`
- define what belongs to that new theme and what does not
- identify the next narrow slice under the new theme
- avoid forcing orchestration or IO concerns into `analysis` owners

This design is not:

- a new `analysis` extraction plan
- an engine refactor
- an API payload redesign
- an implementation plan

Project-phase note:

- domain: `lowfreq attribution report-runner orchestration`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G6`

## 2. Topic Reclassification

### 2.1 Old topic

The previous topic was:

- `lowfreq attribution report M3 contract extraction`

That topic was valid while the script still owned visible report-side contracts such as:

- reason decisions
- report row projections
- aggregate projections
- markdown formatting
- artifact envelopes

### 2.2 New topic

The new topic is:

- `lowfreq attribution report-runner orchestration`

This new topic owns the script-side run flow around report generation rather than the report semantics themselves.

It is a better fit for the current repository state because the remaining script code is now dominated by:

- stage progression
- runtime preparation
- database / engine coordination
- artifact write ordering
- final CLI summary emission

### 2.3 Layer assignment

This topic should be treated as:

- `scripts / orchestration`
- not `analysis / M3`

Rationale:

- the current lowfreq code wiki already says scripts own experiment setup, attribution, and output generation:
  - [lowfreq_code_wiki.md:L63-L82](file:///Users/mac/NeoTrade3/docs/architecture/lowfreq_code_wiki.md#L63-L82)
- scripts must rely on canonical engine outputs, but they may still own orchestration:
  - [lowfreq_code_wiki.md:L79-L82](file:///Users/mac/NeoTrade3/docs/architecture/lowfreq_code_wiki.md#L79-L82)

## 3. Repository Evidence

Current repository evidence shows:

- the script still owns status-stage writes:
  - [generate_lowfreq_top200_attribution_report.py:L62-L72](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L62-L72)
- the script still owns the end-to-end report run flow in `main()`:
  - [generate_lowfreq_top200_attribution_report.py:L859-L978](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L859-L978)
- that flow includes:
  - `report_id` generation
  - `output_dir` creation
  - staged status transitions
  - sqlite connection lifecycle
  - ranking / backtest / analysis execution ordering
  - artifact file write ordering
  - final CLI summary output
- a neighboring script already treats this script as a downstream runner:
  - [run_lowfreq_top200_capacity_experiment.py:L84-L120](file:///Users/mac/NeoTrade3/scripts/run_lowfreq_top200_capacity_experiment.py#L84-L120)

These facts together show that:

- the remaining work is not primarily about report semantics anymore
- the remaining work is about the runner contract around how the report is produced

## 4. Scope

Included in the new topic:

- report run input preparation
- stage progression contract
- artifact write orchestration
- final CLI summary contract

Excluded from the new topic:

- canonical backtest semantics in `lowfreq_engine_v16_advanced.py`
- already-extracted `analysis` owners
- API readback payloads
- frontend display contracts
- new business meaning for attribution fields

## 5. Internal Decomposition

The remaining script-runner work should be divided into four orchestration responsibilities:

### R1. Input Preparation

Includes:

- CLI argument normalization
- `report_id` generation
- `output_dir` resolution
- sqlite connection setup / teardown
- backtest payload preparation
- engine preparation for the analysis stage

### R2. Stage Progression

Includes:

- `initializing`
- `ranking_ready`
- `backtest_ready`
- `analysis_ready`
- `done`

And the minimum visible payload that each stage writes to `status.json`.

### R3. Artifact Write Orchestration

Includes:

- ranking artifact write
- wave-segment artifact write
- attribution artifact write
- markdown report write
- final `done` status path registration

### R4. CLI Result Summary

Includes:

- the final `print(json.dumps(...))` payload
- report run success summary fields

## 6. Approach Options

### Option A: Continue forcing the script into more `analysis` owners

Pros:

- preserves one previous migration pattern

Cons:

- no longer matches the remaining code facts
- would push IO or orchestration concerns into `analysis`
- weakens layer clarity

### Option B: Reclassify the script remainder as `report-runner orchestration` and cut new slices there (Recommended)

Pros:

- matches the current repository evidence
- preserves `analysis` owner purity
- lets the remaining script work continue as narrow slices

Cons:

- requires an explicit topic reset

### Option C: Declare the script fully done and stop all further work there

Pros:

- most conservative

Cons:

- leaves visible runner contracts embedded in `main()`
- gives up a still-meaningful narrow line of cleanup

Decision:

- choose Option B

## 7. Recommended First Slice

The recommended first slice under the new topic is:

- `R2 stage progression contract`

Why this should be first:

- it has the clearest visible contract surface
- it is less entangled with engine or SQL ownership than `R1`
- it provides a stable orchestration anchor for later `R3` artifact-write work

Primary evidence:

- the current stage writes are already explicit and finite:
  - [generate_lowfreq_top200_attribution_report.py:L879-L918](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L879-L918)
  - [generate_lowfreq_top200_attribution_report.py:L948-L956](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L948-L956)

## 8. R2 Contract Freeze

The `R2` slice should freeze only the stage progression protocol.

### 8.1 Stages

The currently visible stages are:

- `initializing`
- `ranking_ready`
- `backtest_ready`
- `analysis_ready`
- `done`

No stage should be renamed, removed, or reordered in this slice without explicit new evidence.

### 8.2 Minimum per-stage payload

Current visible payload fields are:

- `initializing`
  - `year`
  - `limit`
  - `report_id`
- `ranking_ready`
  - `ranking_count`
- `backtest_ready`
  - `ranking_count`
  - `total_return_pct`
  - `total_trades`
- `analysis_ready`
  - `ranking_count`
  - `aggregate`
- `done`
  - `report_id`
  - `ranking_path`
  - `segments_path`
  - `attribution_path`
  - `report_path`

Each stage also includes:

- `updated_at`

through `_write_status(...)`.

### 8.3 Boundary rules

The `R2` slice must not:

- change how timestamps are formatted
- change where `status.json` is written
- change artifact file names
- change stage production order
- merge status logic with artifact write logic

The `R2` slice may:

- centralize stage payload projection
- centralize stage-name constants
- centralize per-stage payload builders

if done without altering the visible stage protocol.

## 9. Risks and Guardrails

Main risk:

- reclassification drifts into a broad `main()` rewrite instead of one narrow orchestration contract

Guardrail:

- treat each orchestration responsibility (`R1-R4`) as a separate theme candidate, not one implementation block

Secondary risk:

- mixing engine truth and runner truth

Guardrail:

- engine continues to own canonical backtest outputs
- runner only owns sequencing, state, write ordering, and run summary contracts

## 10. Success Criteria

This design is complete when:

- the remaining script work is explicitly reclassified away from `M3 analysis contract extraction`
- the new theme boundary is documented
- the four orchestration responsibilities are enumerated
- the next narrow slice is locked as `R2 stage progression contract`
- excluded boundaries are explicit enough to prevent topic drift
