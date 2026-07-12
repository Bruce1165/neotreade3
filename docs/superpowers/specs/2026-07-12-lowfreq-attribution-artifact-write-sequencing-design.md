Status: active
Owner: lowfreq / scripts
Scope: Narrow extraction of the remaining artifact write sequencing contract from the attribution report runner
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Artifact Write Sequencing Design

Date: 2026-07-12

## 1. Goal

This design covers the next narrow slice after:

- `R1 run context contract`
- `R1 backtest payload source contract`
- `R1 analysis engine prep contract`
- `R2 stage progression contract`
- `R3 artifact path bundle contract`
- `R4 CLI success summary payload contract`

under the `report-runner orchestration` theme.

This slice freezes only the remaining artifact write sequencing block that still lives inline in:

- [generate_lowfreq_top200_attribution_report.py:L928-L968](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L928-L968)

The goal is to:

- move the current artifact write ordering into one orchestration-side owner
- preserve the current artifact file order exactly
- preserve the current JSON serialization shape and newline behavior exactly
- preserve the current `generated_at` timestamp usage for the attribution artifact exactly
- keep `_analyze_topk(...)`, artifact path projection, done-status payload projection, and CLI summary in their current owners

This design is not:

- a rewrite of artifact payload semantics
- a rewrite of markdown formatting
- a rewrite of done-status payload projection
- a rewrite of final CLI summary emission
- a generic filesystem abstraction for all scripts

Project-phase note:

- domain: `lowfreq attribution artifact write sequencing`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G6`

## 2. Scope

Included:

- extracting the current artifact write sequencing block from the script
- preserving the current write order:
  - `ranking.json`
  - `wave_segments.json`
  - `model_attribution.json`
  - `report.md`
  - final `done` status registration
- preserving the current JSON write formatting:
  - `ensure_ascii=False`
  - `indent=2`
  - trailing `"\n"` for JSON artifacts
- preserving the current attribution artifact `generated_at` production and forwarding

Excluded:

- changing artifact file names or paths
- changing `build_attribution_artifact_payload(...)`
- changing `_write_markdown_report(...)`
- changing `build_done_report_status(...)`
- changing the final success-summary payload
- changing any pre-write analysis or sqlite lifecycle

## 3. Existing Context

Current repository evidence shows:

- the script already delegates artifact path projection:
  - [generate_lowfreq_top200_attribution_report.py:L928-L936](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L928-L936)
- the script already delegates attribution artifact payload projection:
  - [generate_lowfreq_top200_attribution_report.py:L941-L948](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L941-L948)
- the script already delegates markdown report formatting and file write:
  - [generate_lowfreq_top200_attribution_report.py:L950-L958](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L950-L958)
- the script already delegates final `done` payload projection:
  - [generate_lowfreq_top200_attribution_report.py:L959-L968](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L959-L968)

So the remaining inline responsibility is no longer payload semantics. It is now the side-effect sequencing contract across already-extracted owners.

Repository evidence also shows:

- the remaining block is broader than the already-extracted engine-prep and backtest-source slices because it combines multiple ordered writes plus final status registration
- a neighboring runner also ends with a compact artifact-write tail after compute work completes:
  - [generate_lowfreq_top200_process_research_report.py:L1024-L1031](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_process_research_report.py#L1024-L1031)

These facts together show:

- there is no narrower pure-projection helper left inside this tail
- the next defensible slice is the artifact write sequencing contract itself

## 4. Approach Options

### Option A: Extract one artifact write sequencing owner and keep payload owners unchanged (Recommended)

- create one orchestration owner for the remaining ordered side effects
- let existing path, payload, markdown, and done-status owners stay separate
- let the script keep only orchestration before and after the write block

Pros:

- matches the current repository state where semantics are already ownerized
- isolates the remaining runner-owned side-effect sequence without broad rewrites
- preserves the existing owner boundaries

Cons:

- the owner is side-effect oriented rather than projection-only

### Option B: Split the tail again into smaller write helpers

Pros:

- may appear more granular

Cons:

- current evidence does not show a narrower stable contract than the whole ordered sequence
- would likely create thin wrappers around single `write_text(...)` calls

### Option C: Leave the tail inline and stop here

Pros:

- most conservative

Cons:

- leaves the last visible runner-owned sequencing contract embedded in `main()`

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Add one new orchestration owner:

- `neotrade3/orchestration/report_runner_artifact_writes.py`

Recommended public function:

- `write_lowfreq_report_artifacts(...) -> None`

Recommended inputs:

- `output_dir: Path`
- `report_id: str`
- `year: int`
- `limit: int`
- `ranking_path: Path`
- `segments_path: Path`
- `attribution_path: Path`
- `report_path: Path`
- `ranking: list[dict[str, Any]]`
- `segments: list[dict[str, Any]]`
- `aggregate: dict[str, Any]`
- `attribution_rows: list[dict[str, Any]]`
- `backtest_payload: dict[str, Any]`
- `generated_at: str`

Why this file:

- the contract belongs to runner-side artifact emission rather than analysis semantics
- the owner sequences already-owned projections and writes them in one place
- a dedicated file prevents the final inline tail from drifting across multiple responsibilities

### 5.2 Contract Freeze

The helper must preserve the current observable behavior:

- `ranking_path.write_text(json.dumps(ranking, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")`
- `segments_path.write_text(json.dumps(segments, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")`
- build attribution artifact payload via `build_attribution_artifact_payload(...)`
- `attribution_path.write_text(json.dumps(attribution_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")`
- call `_write_markdown_report(...)`
- call `_write_status(output_dir, **build_done_report_status(...))`

The helper must preserve the current order:

1. ranking artifact write
2. wave-segment artifact write
3. attribution artifact build and write
4. markdown report write
5. final `done` status registration

The helper must not:

- rebuild artifact paths
- recompute ranking / segments / attribution rows
- change JSON formatting or newline suffix
- print the final success summary

### 5.3 Script Boundary

The script should keep:

- analysis execution
- artifact path resolution
- final CLI success summary emission

The script should stop owning:

- the inline artifact write sequence after artifact paths are resolved

### 5.4 Testing Strategy

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_report_runner_artifact_writes.py`

Minimum owner cases:

- writes ranking and segment JSON with the current formatting and trailing newline
- builds and writes attribution artifact with the forwarded `generated_at`
- writes markdown report output
- registers final `done` status with the current artifact paths
- preserves current write ordering

Test style:

- use temporary paths
- use lightweight fake payloads
- avoid broad script integration

## 6. Risks and Guardrails

Main risk:

- widening from ordered artifact writes into earlier analysis or later CLI summary flow

Guardrail:

- keep the owner limited to the current tail block after artifact paths are already resolved and before final `print(json.dumps(...))`

Secondary risk:

- accidentally changing current file formatting or write ordering

Guardrail:

- lock write order, JSON formatting, newline behavior, and final done-status registration in owner-focused tests

## 7. Implementation Outline

Planned steps:

1. add `report_runner_artifact_writes.py`
2. move the current write sequence into the new owner
3. switch the script caller to consume the new owner
4. add owner-focused tests
5. run syntax checks and focused assertions

## 8. Success Criteria

This slice is complete when:

- the remaining artifact write sequence has one orchestration-side owner
- the script no longer owns the inline artifact tail
- write ordering and formatting remain unchanged
- done-status registration remains unchanged
- focused verification passes
- syntax verification passes
