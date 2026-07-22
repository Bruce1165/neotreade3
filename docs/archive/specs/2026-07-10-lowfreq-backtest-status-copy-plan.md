# Lowfreq Backtest Status-Copy Production Alignment Plan

Date: 2026-07-10  
Related design: `docs/superpowers/specs/2026-07-10-lowfreq-backtest-status-copy-design.md`

## 1. Goal

This plan covers only the backtest status-copy contract alignment inside `BacktestPanel` in `Lowfreq.jsx`. It does not expand into nearby backtest layout cleanup, condition-style cleanup, or any other `Lowfreq` theme.

This round has only three goals:

1. Align the `BacktestPanel` production copy to the existing `STATUS_COPY` contract at the exact copy points already depended on by the focused backtest carrier.
2. Keep the implementation boundary limited to copy-contract lines, excluding nearby formatting and layout drift in the same region.
3. Verify the slice with the focused backtest carrier and commit only if the `HEAD`-relative hunk is safely isolatable.

Core result required from this round:

- `BacktestPanel` uses `STATUS_COPY.processing`
- `BacktestPanel` uses `STATUS_COPY.reportNumber`
- `BacktestPanel` uses `STATUS_COPY.runMode`
- the commit contains no adjacent backtest UI cleanup

## 2. Out Of Scope

- `BacktestPanel` layout reshaping
- `next_session` candidate card layout adjustments
- `cond ? (...) : null` to `cond && (...)` style cleanup
- spacing/class order cleanup
- `PageHeader`, `ModeOverviewPanel`, `MetricCard`, `BlockMessage`
- `scorePool`, `candidates`, `manual actions`, `tools`
- any focused test carrier changes unless required by an actual syntax/structure break

## 3. Current Starting Point

### 3.1 Existing facts

- The focused carrier [Lowfreq.backtestUxDetailLink.test.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.backtestUxDetailLink.test.jsx) already asserts the user-facing backtest contract:
  - `运行方式：unbounded_opportunity`
  - `报告编号：report-done`
  - detail-link behavior
- The remaining production drift in [Lowfreq.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.jsx) includes a mixed `BacktestPanel` region where copy-contract changes sit next to unrelated formatting changes.
- The approved design narrows this slice to the copy-contract points only.

### 3.2 Structural risk

- The biggest risk is not changing the wrong string; it is accidentally staging neighboring JSX cleanup from the same `BacktestPanel` block.
- If the copy lines cannot be isolated from adjacent drift, forcing a commit would produce a misleading mixed-purpose change.
- If we widen to include layout/spacing cleanup, the slice stops being a clear production contract alignment.

## 4. Implementation Principles

- Change only the copy-contract points in `BacktestPanel`
- Do not modify the focused carrier unless a real syntax/structure failure proves it necessary
- Prefer the smallest possible production hunk
- Treat adjacent JSX formatting drift as excluded even if it appears in the same visual region
- If isolation is not safe, stop and report boundary failure instead of widening silently

## 5. Allowed Change Boundary

Allowed file:

- `neotrade3-dashboard/src/pages/Lowfreq.jsx`

Allowed logic:

- replace `运行中...` with `STATUS_COPY.processing`
- replace `报告编号` prefix with `STATUS_COPY.reportNumber`
- replace `运行方式` prefix with `STATUS_COPY.runMode`
- if required for consistency in the same contract area, include the second `报告编号` prefix used in the running-state block

Explicitly disallowed:

- changing JSX structure
- changing conditional rendering style
- changing classes or spacing
- changing next-session layout
- changing report link logic
- touching other panels or shared display helpers

## 6. Execution Stages

This plan should be executed in four stages:

- `LBS-R1`: freeze the exact copy-contract points
- `LBS-R2`: implement only the copy-contract replacements
- `LBS-R3`: run focused verification and inspect file safety
- `LBS-R4`: stage only the isolated hunk and commit if valid

## 7. Stage Plan

### LBS-R1: Freeze the exact copy-contract points

Goal:

- identify the precise `BacktestPanel` lines that belong to the production copy contract and separate them from neighboring drift.

Tasks:

- read the current `BacktestPanel` block in [Lowfreq.jsx](file:///Users/mac/NeoTrade3/neotrade3-dashboard/src/pages/Lowfreq.jsx)
- compare it against `HEAD`
- mark only these contract points:
  - processing label
  - report number prefix
  - run mode prefix
- exclude adjacent layout/style edits

Done when:

- the exact include/exclude list is explicit
- the copy-contract points are isolated from nearby backtest formatting drift

### LBS-R2: Implement only the copy-contract replacements

Goal:

- align production copy with the focused carrier contract without changing nearby backtest structure.

Tasks:

- update the running-state label to `STATUS_COPY.processing`
- update the result-state report number prefix to `STATUS_COPY.reportNumber`
- update the result-state run mode prefix to `STATUS_COPY.runMode`
- if needed, update the running-state report number prefix to `STATUS_COPY.reportNumber`

Constraints:

- do not change surrounding condition style
- do not reorder markup
- do not touch candidate layout
- do not touch backtest link logic

Done when:

- the targeted copy points match the `STATUS_COPY` contract
- surrounding JSX structure remains unchanged

### LBS-R3: Run focused verification and inspect file safety

Goal:

- prove the backtest contract still holds and ensure no obvious syntax/structure issues were introduced.

Tasks:

- run `npm test -- src/pages/Lowfreq.backtestUxDetailLink.test.jsx`
- if the edited region shows an unexpected dependency risk, optionally run `npm test -- src/pages/Lowfreq.test.jsx`
- inspect the edited file for obvious syntax/structure issues

Done when:

- the focused backtest carrier passes
- the edited region is structurally sound

### LBS-R4: Stage only the isolated hunk and commit if valid

Goal:

- produce a single-purpose production commit for backtest status-copy alignment.

Tasks:

- inspect `git diff HEAD -- neotrade3-dashboard/src/pages/Lowfreq.jsx`
- stage only the copy-contract hunk
- exclude adjacent formatting/layout drift
- commit only if the hunk is safely isolatable

Done when:

- the staged diff contains only backtest status-copy alignment
- the commit does not include unrelated backtest UI cleanup

If isolation fails:

- stop the commit
- report that the boundary needs re-evaluation
- do not silently widen scope

## 8. File Order

Recommended execution order:

1. inspect `BacktestPanel` live block
2. inspect `HEAD` diff for the same block
3. edit only the copy-contract lines
4. run the focused backtest carrier
5. inspect `HEAD`-relative diff
6. stage only the valid hunk

Reason:

- this minimizes the risk of dragging adjacent `BacktestPanel` drift into the slice
- it lets the focused carrier validate the contract before any commit decision

## 9. Proposed Commit Shape

Suggested single commit:

### Commit LBS: Lowfreq backtest status-copy alignment

Scope:

- only the `BacktestPanel` status-copy contract lines in `Lowfreq.jsx`

Purpose:

- align production backtest copy with the existing focused backtest carrier contract

If the commit cannot be kept this narrow, the correct outcome is no commit, not a widened mixed-purpose commit.

## 10. Minimum Acceptance

This round is complete only if all of the following are true:

1. `BacktestPanel` uses `STATUS_COPY.processing`
2. `BacktestPanel` uses `STATUS_COPY.reportNumber`
3. `BacktestPanel` uses `STATUS_COPY.runMode`
4. `Lowfreq.backtestUxDetailLink.test.jsx` passes
5. no unrelated `BacktestPanel` formatting/layout drift is included in the commit

## 11. Risks

- the main risk is accidental adjacency capture from the same mixed diff block
- the second risk is believing nearby visual cleanup is “close enough” and widening the slice
- the third risk is creating a commit that is hard to explain because it mixes copy-contract and layout cleanup

## 12. Conclusion

This plan is not a backtest UI cleanup plan. It is a narrow production contract alignment plan that:

- updates only the backtest status-copy points already depended on by the focused carrier
- verifies the result through the existing focused test
- commits only if the hunk can remain isolated and atomic
