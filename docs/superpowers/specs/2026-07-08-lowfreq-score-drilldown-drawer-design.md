# Lowfreq Score Drilldown Drawer Design

Date: 2026-07-08

## 1. Goal

This slice adds the first narrow frontend consumer for the existing single-stock score endpoint:

- `GET /api/lowfreq-score/pool/{code}`

The goal is to let the `Lowfreq` page open a read-only stock detail drill-down without changing backend contracts, write behavior, or page routing.

## 2. Scope

Included:

- `neotrade3-dashboard/src/pages/Lowfreq.jsx`
- `neotrade3-dashboard/src/pages/Lowfreq.test.jsx` or a new focused test carrier if boundary audit requires it
- one right-side detail drawer triggered from the existing score-pool view

Excluded:

- backend API changes
- score write-path changes
- route changes
- cross-page component reuse
- general `Lowfreq` page reorganization
- broad styling cleanup

## 3. Existing Context

Current design and backend contract already define the drill-down endpoint:

- `GET /api/lowfreq-score/pool/{code}` returns single-stock state, latest snapshots, and key events
- this endpoint is intended for single-stock drill-down and external use

Current `Lowfreq` page already loads:

- `GET /api/lowfreq-score/summary`
- `GET /api/lowfreq-score/pool`
- `POST /api/lowfreq-score/manual/buy-intent`
- `POST /api/lowfreq-score/manual/abandon`

The current page does not yet consume the single-stock drill-down endpoint.

## 4. Approaches Considered

### Option A: Right-side drawer

Clicking a score-pool row opens a right-side drawer and fetches stock detail on demand.

Pros:

- minimal scope expansion
- preserves score-pool list context while viewing details
- enough room for item, events, and snapshots
- easiest to validate with a focused UI test

Cons:

- adds local view state to an already large page file

### Option B: Inline expandable row

Expands one table row into a detail section.

Pros:

- compact
- no overlay behavior

Cons:

- poorer fit for three detail sections
- makes table structure noisier
- more fragile in a mixed file

### Option C: Dedicated detail page or subview

Moves drill-down into a separate route or page panel.

Pros:

- scales better for richer future analytics

Cons:

- too large for the first narrow slice
- introduces navigation and page-state changes

Decision:

- choose Option A

## 5. Interaction Design

### 5.1 Entry point

The trigger lives inside the existing score-pool list on the `scorePool` tab.

The first slice may use either:

- row click, or
- a compact explicit detail action

Preferred implementation is the smaller of the two in the current file context. The slice must not introduce unrelated table restructuring just to support the trigger.

### 5.2 Drawer content

The drawer is read-only and contains exactly three sections:

1. identity and current state
   - code
   - name
   - sector / sector_name if present
   - current score-pool state
   - latest return fields if present

2. recent events
   - event date
   - event type
   - trigger source
   - note / price when present

3. latest snapshots
   - trade date
   - state
   - close / buy / sell price
   - realized / unrealized return fields when present

No write actions appear in the drawer for this slice.

### 5.3 Loading and error behavior

When the user opens a stock detail:

- drawer opens immediately in loading state
- frontend requests `GET /api/lowfreq-score/pool/{code}?date=...`
- success replaces loading state with content
- failure shows a local drawer error state

Closing the drawer clears drill-down-local state only. It must not reload the whole score-pool list.

## 6. State Design

The page keeps drill-down-local state separate from the existing score-pool block:

- selected stock code
- drawer open / closed
- drawer request loading state
- drawer payload
- drawer error

This slice must not refactor the main score-pool block loading flow unless a tiny supporting extraction is strictly necessary.

## 7. Testing Design

Required test:

- opening a score-pool stock triggers the single-stock endpoint and renders identity plus at least one event or snapshot field

Recommended second test:

- failed drill-down request shows local error state while keeping the score-pool list usable

Test boundary rules:

- do not fold broad page refactors into this slice
- if `Lowfreq.test.jsx` is too mixed, create a new focused frontend test carrier instead of widening the current diff

## 8. Validation

Expected validation for the implementation phase:

- frontend unit test for drill-down fetch + render
- any existing targeted `Lowfreq` frontend tests touched by the slice

No backend validation expansion is required because this slice consumes an already existing endpoint.

## 9. Commit Boundary

The target implementation commit should be limited to:

- the `Lowfreq` page drill-down consumer
- one focused frontend test carrier

It must exclude:

- unrelated page cleanup
- other tabs
- shared-component extraction unless strictly necessary for the drawer itself
- backend changes
