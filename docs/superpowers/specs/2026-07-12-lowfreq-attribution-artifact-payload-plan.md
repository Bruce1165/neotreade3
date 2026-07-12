Status: active
Owner: lowfreq / analysis
Scope: Implementation plan for the narrow attribution artifact payload extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-12

# Lowfreq Attribution Artifact Payload Plan

Date: 2026-07-12
Design:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-artifact-payload-design.md`

## 1. Goal

This plan covers only the next narrow slice after the Markdown formatter extraction.

This slice only handles:

- the `model_attribution.json` envelope inside the scorecard script tail
- one analysis owner for that artifact payload contract
- owner-focused tests for the payload shape

The goal is to:

- move the visible JSON artifact contract out of the script
- keep the script responsible for timestamp creation, serialization, and file writing
- preserve the current `_meta`, `aggregate`, and `items` shape exactly

This slice does not:

- rewrite the final CLI `print(...)` payload
- rewrite `status.json`
- change JSON serialization settings
- change upstream aggregate or row contents

## 2. Starting Point

Current repository evidence shows:

- the scorecard script still owns one inline `model_attribution.json` envelope
- that envelope is a visible artifact contract, separate from file IO
- no existing analysis owner currently freezes this payload shape

So the correct next slice is:

- add one attribution-specific artifact-payload owner
- keep timestamp creation and file writing in the script

## 3. Implementation Strategy

Production boundary:

- `neotrade3/analysis/attribution_artifact_payload.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_attribution_artifact_payload.py`

Documentation boundary:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-artifact-payload-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-artifact-payload-plan.md`

## 4. Execution Steps

### AAP-S1: Freeze the artifact envelope contract

Freeze the current observable payload as:

- top-level keys:
  - `_meta`
  - `aggregate`
  - `items`
- `_meta` fields:
  - `status="ok"`
  - `report_id`
  - `generated_at`
  - `year`
  - `limit`

Freeze current coercions:

- `report_id -> str(... or "")`
- `generated_at -> str(... or "")`
- `year -> int(...)`
- `limit -> int(...)`
- `aggregate` pass-through
- `items` pass-through

Completion check:

- no key is added, removed, or renamed

### AAP-S2: Add the analysis owner

Create:

- `neotrade3/analysis/attribution_artifact_payload.py`

Public function:

- `build_attribution_artifact_payload(*, report_id: str, generated_at: str, year: int, limit: int, aggregate: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]`

Implementation rules:

- perform only the envelope projection
- keep `aggregate` and `items` as direct pass-through values
- do not serialize JSON
- do not create timestamps

Completion check:

- the artifact payload has one dedicated owner outside the script

### AAP-S3: Switch the script tail

In the scorecard script tail:

- keep `generated_at = datetime.now(timezone.utc).strftime(...)` at the script boundary
- replace the inline payload literal with one call to `build_attribution_artifact_payload(...)`
- keep `json.dumps(..., ensure_ascii=False, indent=2) + "\n"`
- keep `attribution_path.write_text(...)`

Do not change:

- file names
- JSON formatting
- report markdown writing
- final CLI summary payload

Completion check:

- only the artifact envelope leaves the script

### AAP-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_attribution_artifact_payload.py`

Minimum cases:

- projects the current `_meta` payload with current coercions
- preserves `aggregate` and `items` by identity
- keeps empty-string fallbacks for `report_id` and `generated_at`

Completion check:

- the artifact contract is directly locked without a broad integration harness

### AAP-S5: Minimum verification

Run at minimum:

- `.venv/bin/python -m py_compile neotrade3/analysis/attribution_artifact_payload.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_attribution_artifact_payload.py`
- `.venv/bin/python -m pytest tests/unit/test_lowfreq_attribution_artifact_payload.py`

Fallback if `pytest` is unavailable in `.venv`:

- keep `py_compile`
- run `.venv/bin/python` inline assertions against `build_attribution_artifact_payload(...)`

Completion check:

- syntax validation passes
- owner-focused verification passes with the best available runner in the current environment

### AAP-S6: Narrow commit

For the implementation commit, stage only:

- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-artifact-payload-design.md`
- `docs/superpowers/specs/2026-07-12-lowfreq-attribution-artifact-payload-plan.md`
- `neotrade3/analysis/attribution_artifact_payload.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_attribution_artifact_payload.py`

Must exclude:

- changes to the Markdown formatter owner
- changes to the final CLI summary payload
- changes to `status.json` writes
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally copying or normalizing `aggregate` / `items`

Guard:

- lock pass-through identity in owner-focused tests

Risk 2:

- accidentally broadening into other artifact payloads

Guard:

- keep the owner focused on `model_attribution.json` only

## 6. Success Criteria

This slice is complete when:

- the `model_attribution.json` envelope has one analysis-side owner
- the script no longer owns the inline artifact payload block
- serialization and file output remain in the script
- payload shape remains unchanged
- focused verification passes
- syntax verification passes
