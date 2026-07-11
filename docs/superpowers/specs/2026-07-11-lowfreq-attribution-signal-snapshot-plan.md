Status: active
Owner: lowfreq / analysis
Scope: Implementation plan for the narrow top200 attribution report signal snapshot extraction
Canonical: self
Supersedes: none
Superseded_by: none
Last_reviewed: 2026-07-11

# Lowfreq Attribution Signal Snapshot Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-attribution-signal-snapshot-design.md`

## 1. Goal

This plan covers only the next narrow report-consumer snapshot slice after the attribution execution audit reason extraction.

This slice only handles:

- the raw signal payload -> attribution snapshot contract used by `_signal_layer_snapshot(...)`
- reuse of `project_lowfreq_formal_front(...)` inside a dedicated analysis owner
- direct owner-focused tests plus the nearby consumer guard rerun

The goal is to:

- remove the inline snapshot assembler from the script
- keep `AuditContext` cache and orchestration stable
- preserve returned snapshot shape exactly

This slice does not:

- rewrite `AuditContext`
- rewrite signal generation
- rewrite the producer-side projection helper

## 2. Starting Point

Current repository evidence shows:

- `_signal_layer_snapshot(...)` is still inline in the report script
- the helper is self-contained and already has a dedicated focused test carrier
- formal-front compression is already owned by `project_lowfreq_formal_front(...)`

So the correct next slice is:

- extract only the snapshot assembler
- keep the script as a thin consumer around it

## 3. Implementation Strategy

Production boundary:

- `neotrade3/analysis/attribution_signal_snapshot.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`

Test boundary:

- `tests/unit/test_lowfreq_attribution_signal_snapshot_owner.py`
- `tests/unit/test_lowfreq_attribution_signal_snapshot.py`

## 4. Execution Steps

### ASS-S1: Freeze observable snapshot contract

Freeze the visible shape:

- output keys stay `candidate_signals`, `entry_signals`, `signal_summary`
- codes remain the dict keys for both candidate and entry signals
- summary keeps `candidate_count`, `entry_count`, and `soft_retained_count`

Freeze the selection algorithm:

1. if `raw` is not a dict, return empty snapshot with default summary
2. accept `entry_signals` only when it is a list
3. if `candidate_signals` is not a list, fall back to `entry_signals`
4. normalize each item only when it is a dict with a non-empty `code`
5. apply formal-front priority overrides exactly as today

Completion check:

- no `AuditContext` cache logic is included in this slice

### ASS-S2: Add the analysis owner

Create `neotrade3/analysis/attribution_signal_snapshot.py` with:

- `build_attribution_signal_snapshot(raw: Any) -> dict[str, Any]`

Implementation rules:

- reuse `project_lowfreq_formal_front(...)`
- keep the nested normalization local to the new owner
- do not call the engine
- do not touch report rows or counters outside `signal_summary`

Completion check:

- the snapshot contract is independently understandable from the report script

### ASS-S3: Switch the report script to a thin consumer

In `scripts/generate_lowfreq_top200_attribution_report.py`:

- import `build_attribution_signal_snapshot(...)`
- replace inline `_signal_layer_snapshot(...)` logic with a single delegation call
- remove now-unused direct import of `project_lowfreq_formal_front`

Do not change:

- `AuditContext.signal_snapshot(...)`
- signal cache shape
- downstream snapshot consumers

Completion check:

- the script no longer owns the snapshot assembly logic inline

### ASS-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_attribution_signal_snapshot_owner.py`

Minimum owner cases:

- preserves candidate/entry split and summary defaults
- prefers formal-front `entry_ready` override
- ignores legacy `buy_signals` without `entry_signals`

Completion check:

- the owner contract has direct focused coverage

### ASS-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_attribution_signal_snapshot_owner.py tests/unit/test_lowfreq_attribution_signal_snapshot.py`
- `python3 -m py_compile neotrade3/analysis/attribution_signal_snapshot.py scripts/generate_lowfreq_top200_attribution_report.py tests/unit/test_lowfreq_attribution_signal_snapshot_owner.py`

Completion check:

- owner tests pass
- nearby consumer guard passes
- syntax validation passes

### ASS-S6: Narrow commit

For the implementation commit, stage only:

- `neotrade3/analysis/attribution_signal_snapshot.py`
- `scripts/generate_lowfreq_top200_attribution_report.py`
- `tests/unit/test_lowfreq_attribution_signal_snapshot_owner.py`

Must exclude:

- unrelated report changes
- engine/API files
- unrelated workspace changes

## 5. Risks and Guards

Risk 1:

- accidentally expanding into `AuditContext` cache semantics

Guard:

- move only the snapshot assembler

Risk 2:

- silently drifting `candidate_tier` and `entry_ready` override behavior

Guard:

- freeze the formal-front priority rules exactly
- verify focused owner tests plus the nearby consumer guard

## 6. Success Criteria

This slice is complete when:

- the signal snapshot contract has one analysis owner
- the report script no longer owns the assembly logic inline
- returned snapshot shape remains unchanged
- owner-focused tests pass
- nearby consumer guard passes
- syntax verification passes
