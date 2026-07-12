Status: active
Owner: lowfreq / analysis
Scope: Narrow extraction of model_attribution JSON artifact payload from scorecard script
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Artifact Payload Design

Date: 2026-07-12

## 1. Goal

This design covers the next narrow slice after the Markdown formatter extraction.

This slice freezes only the JSON artifact envelope that still lives inline in:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - the `attribution_payload = {...}` block used for `top{limit}_{year}_model_attribution.json`

The goal is to:

- move the visible JSON artifact contract into one analysis-side owner
- keep the script responsible for file paths and `write_text(...)`
- preserve the current `_meta`, `aggregate`, and `items` payload shape exactly
- add direct owner-focused coverage for the artifact envelope

This design is not:

- a rewrite of `aggregate`
- a rewrite of report rows
- a rewrite of the final CLI `print(...)` payload
- a generic artifact framework for all report scripts

Project-phase note:

- domain: `top200 attribution artifact payload`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency
- dual-axis target: `M3 / G6`

## 2. Scope

Included:

- extracting the `model_attribution.json` envelope projection
- preserving the current `_meta.status/report_id/generated_at/year/limit` field set
- preserving `aggregate` and `items` as pass-through payloads
- adding owner-focused tests for the artifact envelope

Excluded:

- changing `attribution_path`
- changing JSON serialization options:
  - `ensure_ascii=False`
  - `indent=2`
  - trailing newline
- changing the final CLI summary payload
- changing `status.json` writes

## 3. Existing Context

Current repository evidence shows:

- the script still owns the visible JSON artifact envelope:
  - [generate_lowfreq_top200_attribution_report.py:L933-L946](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L933-L946)
- the generated file name is already a visible report artifact:
  - [generate_lowfreq_top200_attribution_report.py:L930](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L930)
- the envelope contains one clear contract surface:
  - `_meta`
  - `aggregate`
  - `items`
- there is no existing owner under `neotrade3/analysis/` for this artifact payload

The current problem is:

- the visible attribution JSON contract is still embedded in the script tail
- artifact projection and file IO remain mixed in the same block
- downstream readers have no single owner for this payload shape

## 4. Approach Options

### Option A: Add one attribution-specific artifact-payload owner and keep file writing in the script (Recommended)

- create one dedicated analysis module for the JSON artifact envelope
- pass already prepared `aggregate` and `items` through unchanged
- keep timestamp creation and file writing at the script boundary

Pros:

- isolates one real visible contract with minimal regression surface
- matches the current output-projection extraction path
- avoids broadening into unrelated artifact writers

Cons:

- the final CLI `print(...)` payload remains inline for now

### Option B: Keep the payload inline and only wrap `json.dumps(...)`

Pros:

- smallest code movement

Cons:

- leaves the artifact contract in the script
- creates a thin serialization wrapper with no owner value

### Option C: Build one shared artifact framework for JSON, Markdown, and status payloads

Pros:

- fewer payload helpers in the long run

Cons:

- broadens scope beyond current evidence
- mixes unrelated artifact contracts during bootstrap

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

Add one new analysis owner:

- `neotrade3/analysis/attribution_artifact_payload.py`

Recommended public function:

- `build_attribution_artifact_payload(...) -> dict[str, Any]`

Recommended inputs:

- `report_id: str`
- `generated_at: str`
- `year: int`
- `limit: int`
- `aggregate: dict[str, Any]`
- `items: list[dict[str, Any]]`

Why this file:

- the contract is report-side artifact payload projection, not aggregation or formatting
- a dedicated file keeps the JSON envelope discoverable without overloading nearby owners

### 5.2 Contract Freeze

The helper must preserve the current observable payload shape:

- top-level keys:
  - `_meta`
  - `aggregate`
  - `items`
- `_meta` fields:
  - `status`
  - `report_id`
  - `generated_at`
  - `year`
  - `limit`

The helper must preserve current coercions:

- `status -> "ok"`
- `report_id -> str(... or "")`
- `generated_at -> str(... or "")`
- `year -> int(...)`
- `limit -> int(...)`
- `aggregate` pass-through
- `items` pass-through

The helper must not:

- serialize JSON
- write files
- create timestamps
- mutate `aggregate` or `items`

### 5.3 Script Boundary

The script should keep:

- creating `generated_at`
- choosing `attribution_path`
- serializing with `json.dumps(..., ensure_ascii=False, indent=2) + "\n"`
- writing the final file

The script should stop owning:

- the inline attribution artifact envelope projection

### 5.4 Testing Strategy

Add one owner-focused carrier:

- `tests/unit/test_lowfreq_attribution_artifact_payload.py`

Minimum owner cases:

- projects the current `_meta` envelope with current coercions
- preserves `aggregate` and `items` by identity
- keeps empty-string fallbacks for `report_id` and `generated_at`

Nearby consumer rerun:

- [generate_lowfreq_top200_attribution_report.py](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py)
  - syntax verification only; no broad integration harness is required for this slice

## 6. Risks and Guardrails

Main risk:

- accidentally copying or reshaping `aggregate` / `items` while extracting the helper

Guardrail:

- keep them as direct pass-through references and lock that behavior in owner-focused tests

Secondary risk:

- broadening into unrelated JSON or status payloads

Guardrail:

- limit the owner to the single `model_attribution.json` envelope only

## 7. Implementation Outline

Planned steps:

1. add `attribution_artifact_payload.py`
2. implement `build_attribution_artifact_payload(...)`
3. switch the script tail to call the new owner
4. add owner-focused tests
5. run syntax checks and focused assertions

## 8. Success Criteria

This slice is complete when:

- the visible `model_attribution.json` envelope has one analysis-side owner
- the script no longer owns the inline artifact payload block
- file output and serialization remain in the script
- payload shape remains unchanged
- owner-focused tests pass
- syntax verification passes
