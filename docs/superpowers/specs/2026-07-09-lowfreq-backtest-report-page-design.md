# Lowfreq Backtest Report Page Design

Date: 2026-07-09

## 1. Goal

This slice lands the independent backtest report detail page for `Lowfreq`.

The goal is to close the gap between:

- `Lowfreq` as the summary/status surface
- the existing detail-link contract already exposed from `Lowfreq`
- the existing backend detail endpoint

This slice must deliver a read-only detail page that safely renders structured backtest report content without expanding into a new interactive workbench.

## 2. Scope

Included:

- `neotrade3-dashboard/src/pages/LowfreqBacktestReport.jsx`
- `neotrade3-dashboard/src/App.jsx` route wiring for the detail page only
- minimal `App` test coverage directly related to the detail-page route
- one focused frontend test carrier for the detail page
- read-only rendering of existing backend payload fields

Excluded:

- `Lowfreq.jsx` residual drift outside the already-landed summary/detail-link behavior
- sidebar IA expansion or adding the detail page into global primary navigation
- backend API changes
- report generation changes
- new filters, collapses, sorting controls, retry workflows, or secondary interaction flows
- turning the detail page into a second operator workbench

## 3. Existing Evidence

The design is based on already-verifiable evidence in the current workspace:

1. The summary/detail responsibility split is already defined in `2026-07-08-lowfreq-backtest-ux-detail-link-design.md`.
2. The backend detail endpoint already exists:
   - `GET /api/lowfreq/backtest/report-detail?report_id=<id>`
3. The current worktree already contains:
   - a `LowfreqBacktestReport.jsx` page file
   - `App.jsx` route wiring for `/lowfreq/backtest-reports/:reportId`

Therefore this slice is not inventing a new product direction. It is a narrow landing and cleanup of an already-established detail-page line.

## 4. Decision

Use the medium landing boundary:

- keep the page read-only
- render the structured sections already present in the detail payload
- do not add new interaction mechanics

This is preferred over a smaller loading shell because it would leave the existing page evidence underutilized.

This is preferred over a broader interactive page because it would violate the current narrow-slice discipline.

## 5. Responsibility Split

### 5.1 `Lowfreq` page responsibility

`Lowfreq` remains the summary layer.

It should answer:

- whether a backtest is running, done, failed, or abnormal
- what the top-level result looks like
- where to go for deeper inspection

It should not become the full report-inspection page.

### 5.2 Detail page responsibility

`LowfreqBacktestReport` becomes the structured read-only detail page.

It should:

- load one report by `reportId`
- render the existing structured payload in stable sections
- provide return navigation back to `Lowfreq`
- expose download links when `pdf_url` or `json_url` exists

It should not:

- mutate report state
- trigger report generation
- poll for report status
- add analysis controls or secondary workflows

## 6. Routing And Data Flow

### 6.1 Route contract

The route path is:

- `/lowfreq/backtest-reports/:reportId`

This route is wired in `App.jsx` only.

The detail page is not added to the sidebar nav. Users reach it from the existing detail links inside `Lowfreq`.

### 6.2 Load model

The detail page reads `reportId` from `useParams()`.

It issues a single request:

- `/api/lowfreq/backtest/report-detail?report_id=${encodeURIComponent(reportId)}`

The page follows a simple load model:

- initial: `loading=true`
- success: store full payload and derive display sections from it
- failure: store error string and stop normal section rendering

This slice does not add:

- polling
- chained fetches
- route state transfer from `Lowfreq`
- cross-page refresh orchestration

## 7. Display Design

The page renders the payload as structured read-only blocks.

### 7.1 Required sections

The detail page should render these existing sections when data is present:

- `summary`
- `execution_action_summary`
- `exit_quality`
- `next_session`
- `recent_trades`

It may also render other already-present payload groups that are currently implemented in the page, as long as they remain read-only and use existing fields only.

### 7.2 Display principle

The rendering rule is:

- structure and display existing backend fields
- do not invent new business calculations
- do not reinterpret the payload into new strategy semantics

This page is a detail presentation layer, not a new analytics layer.

## 8. Error And Empty-State Design

### 8.1 Loading state

While loading, the page shows a single explicit loading state such as:

- `读取报告中`

It should not render half-ready detail sections.

### 8.2 Error state

If `reportId` is missing or the API call fails, the page enters a single error state.

Examples:

- `报告编号缺失`
- `报告读取失败`

In error state, the normal detail sections are not rendered.

This slice does not add retry controls.

### 8.3 Empty-field fallback

For missing text, number, or percent values, the page uses conservative fallback display such as:

- `--`

The page must not leak raw `null`, `undefined`, or `NaN` into the UI.

### 8.4 Section-level degradation

If one section has no usable data, that section degrades locally with a clear empty message, such as:

- `暂无执行动作摘要`
- `暂无候选信号`
- `暂无交易样本`

One empty section must not cause the whole page to fail.

## 9. Testing Design

Use a focused test carrier for the detail page instead of widening `Lowfreq.test.jsx`.

Recommended test file:

- `neotrade3-dashboard/src/pages/LowfreqBacktestReport.test.jsx`

Required coverage:

1. route/page shell renders under the detail-page route
2. successful fetch renders core sections and download links
3. failed fetch renders the error state
4. missing or partial fields fall back safely without white screen

If `App.jsx` route wiring changes are directly touched, run the minimal related `App` route coverage as well.

## 10. Commit Boundary

Target implementation slice should be limited to:

- `LowfreqBacktestReport.jsx`
- route-related minimal changes in `App.jsx`
- route-related minimal changes in `App.test.jsx`
- one focused detail-page test file

It must exclude:

- unrelated `App` copy cleanup
- unrelated `Lowfreq` drift
- other pages
- backend files

## 11. Validation

Expected validation for the implementation slice:

- focused detail-page frontend tests
- minimal `App` route test if touched
- diagnostics check on recently edited frontend files

No backend validation expansion is required for this slice because the page consumes an existing endpoint and existing payload fields.
