Status: active
Owner: lowfreq / scripts
Scope: Narrow extraction of report-runner artifact path bundle contract from attribution report script
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Artifact Path Bundle Design

Date: 2026-07-12

## 1. Goal

This design covers the next narrow slice after the `R2 stage progression contract` extraction under the `report-runner orchestration` theme.

This slice freezes only the artifact path bundle that still lives inline in:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - the `ranking_path / segments_path / attribution_path / report_path` block in `main()`

The goal is to:

- move the visible artifact path contract into one orchestration-side owner
- keep the script responsible for the current artifact write order
- preserve the current four artifact file names exactly
- preserve the current reuse of those paths across artifact writes, `done` status, and final CLI summary
- add direct owner-focused coverage for the artifact path bundle

This design is not:

- a writer helper extraction
- a rewrite of `json.dumps(...)` or `write_text(...)`
- a rewrite of `_write_markdown_report(...)`
- a rewrite of the final CLI summary payload
- a generic artifact registry framework for all report runners

Project-phase note:

- domain: `lowfreq attribution artifact path bundle`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M5 / G6`

## 2. Scope

Included:

- extracting the `output_dir -> four artifact paths` projection
- preserving the current file basenames:
  - `top{limit}_{year}_ranking.json`
  - `top{limit}_{year}_wave_segments.json`
  - `top{limit}_{year}_model_attribution.json`
  - `report.md`
- preserving the current consumer relationship where the same resolved paths feed:
  - artifact writes
  - `done` status payload
  - final CLI summary payload
- adding owner-focused tests for the path bundle contract

Excluded:

- changing artifact write order
- changing JSON serialization options:
  - `ensure_ascii=False`
  - `indent=2`
  - trailing newline
- changing Markdown report writing
- changing `done` status field names
- changing final CLI summary field names
- changing `output_dir` resolution

## 3. Existing Context

Current repository evidence shows:

- the script still resolves the four artifact paths inline in `main()`:
  - [generate_lowfreq_top200_attribution_report.py:L941-L944](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L941-L944)
- those paths are then immediately reused by three different downstream surfaces:
  - artifact writes:
    - [generate_lowfreq_top200_attribution_report.py:L947-L957](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L947-L957)
  - `done` status payload:
    - [generate_lowfreq_top200_attribution_report.py:L967-L976](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L967-L976)
  - final CLI summary payload:
    - [generate_lowfreq_top200_attribution_report.py:L978-L989](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L978-L989)
- the current file names are already externally visible report artifacts rather than private temporary paths
- after `R2`, the remaining dense inline block under `R3` is no longer the stage protocol; it is the artifact path projection and its reuse surface

The current problem is:

- one visible artifact path contract is still embedded inside the script tail
- artifact path projection and artifact write actions remain mixed in the same local block
- downstream orchestration surfaces have no single owner for this four-path bundle

## 4. Approach Options

### Option A: Add one report-runner artifact-path owner and keep all writes in the script (Recommended)

- create one dedicated orchestration module for the four path projections
- let the script keep:
  - artifact write ordering
  - JSON serialization
  - Markdown report writing
  - `done` status emission
  - final CLI summary emission
- let the owner project only the visible path bundle

Pros:

- isolates one real orchestration contract with minimal regression surface
- matches the current thin-consumer extraction path
- avoids widening into IO execution helpers

Cons:

- file writes remain inline for now

### Option B: Move the entire artifact write block into one writer helper

Pros:

- fewer lines remain in the script tail

Cons:

- mixes path projection, serialization, write ordering, and status/summary side effects
- broadens into IO orchestration instead of a narrow visible contract

### Option C: Skip `R3` and move directly to the final CLI summary contract

Pros:

- smaller immediate change surface

Cons:

- leaves a still-visible four-path bundle embedded in the script
- forces `R4` to keep depending on inline path construction

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Add one new orchestration owner:

- `neotrade3/orchestration/report_runner_artifact_paths.py`

Recommended public function:

- `build_lowfreq_report_artifact_paths(...) -> dict[str, str]`

Recommended inputs:

- `output_dir: Path`
- `year: int`
- `limit: int`

Why this file:

- the contract belongs to report-runner orchestration rather than analysis semantics
- a dedicated file keeps the path bundle discoverable without overloading `report_runner_status.py`
- the output is a stable runner-side contract consumed by multiple script-tail surfaces

### 5.2 Contract Freeze

The helper must preserve the current observable payload shape:

- top-level keys:
  - `ranking_path`
  - `segments_path`
  - `attribution_path`
  - `report_path`

The helper must preserve the current file naming rules:

- `ranking_path -> output_dir / f"top{int(limit)}_{year}_ranking.json"`
- `segments_path -> output_dir / f"top{int(limit)}_{year}_wave_segments.json"`
- `attribution_path -> output_dir / f"top{int(limit)}_{year}_model_attribution.json"`
- `report_path -> output_dir / "report.md"`

The helper must preserve current coercions:

- `year -> int(...)`
- `limit -> int(...)`
- each output path -> `str(...)`

The helper must not:

- write files
- create directories
- serialize JSON
- emit status payloads
- emit CLI summary payloads
- decide artifact write order

### 5.3 Script Boundary

The script should keep:

- creating `generated_at`
- writing ranking JSON
- writing wave-segment JSON
- building attribution artifact payload and writing it
- calling `_write_markdown_report(...)`
- emitting `done` status
- printing the final CLI summary payload

The script should stop owning:

- the inline artifact path bundle projection

### 5.4 Consumer Boundary

After extraction, the script should consume one resolved path bundle and reuse it across:

- ranking artifact write
- segments artifact write
- attribution artifact write
- markdown report write
- `done` status payload
- final CLI summary payload

This slice must not change the current ordering:

1. write ranking artifact
2. write segments artifact
3. write attribution artifact
4. write markdown report
5. emit `done` status
6. print final CLI summary

### 5.5 Testing Strategy

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_report_runner_artifact_paths.py`

Minimum owner cases:

- projects the current four path keys from `output_dir/year/limit`
- preserves the current `top{limit}_{year}_...` file naming contract
- coerces `year` and `limit` with the current `int(...)` behavior
- keeps `report.md` as the fixed Markdown artifact name

Nearby consumer rerun:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - syntax verification only; no broad integration harness is required for this slice

## 6. Risks and Guardrails

Main risk:

- accidentally widening from path projection into a full artifact writer helper

Guardrail:

- keep the helper payload-only and forbid file writes or serialization inside it

Secondary risk:

- changing file basenames while trying to make names more generic

Guardrail:

- freeze the current four filenames exactly and lock them in owner-focused tests

## 7. Implementation Outline

Planned steps:

1. add `report_runner_artifact_paths.py`
2. implement `build_lowfreq_report_artifact_paths(...)`
3. switch the script tail to consume the resolved path bundle
4. add owner-focused tests
5. run syntax checks and focused assertions

## 8. Success Criteria

This slice is complete when:

- the visible artifact path bundle has one orchestration-side owner
- the script no longer owns the inline four-path projection
- file writes and serialization remain in the script
- file naming remains unchanged
- owner-focused tests pass
- syntax verification passes
