# Lowfreq Backtest UX Detail Link Design

Date: 2026-07-08

## 1. Goal

This slice upgrades the `Lowfreq` page backtest UX so that the backtest tab becomes a reliable summary-and-status surface, while deep inspection moves to a separate detail page.

The `Lowfreq` page must:

- show explicit status for running, done, failed, and unknown backtest states
- expose execution mode and key result groups when backtest results are available
- provide read-only links to a backtest detail page

The `Lowfreq` page must not become the deep inspection page itself.

## 2. Scope

Included:

- `neotrade3-dashboard/src/pages/Lowfreq.jsx`
- one focused frontend test carrier for backtest UX if needed
- current-report detail link in the `BacktestPanel`
- history-report detail links when report detail artifacts exist
- explicit error state for unknown / failed backtest status
- execution mode and richer summary visibility for completed backtests

Excluded:

- implementing the detail page itself unless it already exists and only needs link routing
- page shell redesign
- candidates panel redesign
- tools-tab IA changes
- backend API changes
- report generation logic changes

## 3. Existing Context

Current remaining frontend drift already contains three mixed lines:

1. page shell / workbench IA
2. candidates reading-vs-action redesign
3. backtest result / status UX

This spec only addresses line 3.

The current backtest UI evidence shows:

- unknown / failed status handling is currently weak or absent
- execution mode and richer runtime outputs exist in backend payloads
- a report detail link path can be derived from report id

## 4. Approach Options

### Option A: Summary tab + detail-page links only

Keep `Lowfreq` backtest as a summary/status surface and link out to a detail page for deep inspection.

Pros:

- narrowest boundary
- aligns with user requirement for a new detail page
- preserves clear responsibility split
- closest to backtest-result visibility without redesigning the whole page

Cons:

- deep inspection remains dependent on another page

### Option B: Full detail embedded inside `Lowfreq`

Expand the current tab until it contains the deep report inspection itself.

Pros:

- one-stop page

Cons:

- too broad
- duplicates future detail-page responsibility
- risks mixing with page shell redesign

### Option C: Status fix only, no links

Improve status handling but postpone detail-page links.

Pros:

- smallest implementation

Cons:

- not aligned with explicit user preference for a detail page

Decision:

- choose Option A

## 5. Design

### 5.1 Backtest tab responsibility

The `回测报告` tab remains the summary layer.

It should answer:

- is a report still running
- did a report fail or enter unknown state
- what are the top-level performance results
- where can the user click to inspect the full detail

It should not become a second full report-detail page.

### 5.2 Status design

Backtest status handling should be explicit:

- running:
  - show “报告生成中”
  - keep report id visible when available
- failed or unknown:
  - show “回测状态异常”
  - show backend-provided reason or message
  - do not render endless-running language
- done:
  - show execution mode when present
  - show current report id
  - render the completed summary panels

### 5.3 Result visibility

For completed reports, `BacktestPanel` should expose a summary-oriented view of:

- core metrics
- execution action summary
- exit quality
- next trading day signal summary

These are overview cards/sections only. The detailed JSON interpretation remains on the detail page.

### 5.4 Detail-page link rules

Current report area:

- if `report_id` and detail artifact exist, show `查看明细`

History list:

- show `明细` link only when detail JSON exists
- if only PDF exists, keep `PDF` download without forcing a detail link

The path contract is:

- `/lowfreq/backtest-reports/{report_id}`

Link generation belongs to `Lowfreq.jsx`, not to global routing refactors in this slice.

## 6. Testing Design

Required tests:

1. unknown backtest status renders explicit error state
2. done status renders execution mode and summary fields
3. current report shows detail link when allowed
4. history reports show `明细` only when detail JSON exists

If the current `Lowfreq.test.jsx` file is too mixed, create a new focused carrier instead of widening unrelated test drift.

## 7. Validation

Expected implementation validation:

- targeted frontend tests for the focused backtest UX carrier
- any existing `Lowfreq` regression test directly touched by the slice

No backend validation expansion is required for this slice because it consumes existing payload fields.

## 8. Commit Boundary

Target implementation commit should be limited to:

- `Lowfreq` backtest tab UX changes
- one focused frontend test carrier

It must exclude:

- workbench shell renaming
- candidate workbench redesign
- tools tab
- detail page implementation itself
- API or report-generation backend changes
