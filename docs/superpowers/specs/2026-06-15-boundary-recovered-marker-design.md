# Market Intelligence Boundary Recovered Marker Design

Date: 2026-06-15

## 1. Goal

- This design addresses one narrow requirement:
  - some samples are acceptable as `recommended`
  - but the team still wants them clearly marked for extra manual review
- The first concrete sample is `000338`.
- The design does not downgrade these samples back to `watchlist`.
- The design adds an explicit business marker for human review.

## 2. Confirmed Context

- After the manual penetration-label backfill, `000338` naturally moved from `watchlist` to `recommended`.
- The team accepts that result.
- The team also requires a clear special marker for this kind of sample.
- The current issue is not recommendation logic anymore.
- Therefore, the correct solution is:
  - keep the recommendation result
  - add a separate review marker

## 3. Scope

### 3.1 In Scope

- Add a dedicated backend marker for boundary recovered candidates.
- Add a minimal configuration source for the boundary candidate list.
- Expose the marker through:
  - `recommendations`
  - `review-board`
- Show the marker in the current `MarketIntelligence` page.

### 3.2 Out Of Scope

- No recommendation-rule changes
- No risk-flag redesign
- No automatic boundary-detection model
- No changes to penetration-stage logic
- No new routing or new page

## 4. Recommended Approach

- Use an explicit configuration list instead of automatic inference.
- Return a dedicated marker field rather than overloading `risk_flags`.
- Render a neutral visual badge in the frontend.

## 5. Why This Approach

- The requirement is business-specific, not a general market rule.
- Automatic inference would expand scope and create new ambiguity.
- Reusing `risk_flags` would mix “accepted boundary review” with real recommendation risk.
- A dedicated marker keeps semantics clear:
  - still recommended
  - but requires extra human attention

## 6. Data Design

### 6.1 Config File

- Add a new config file under:
  - `config/market_intelligence/boundary_recovered_candidates.json`

### 6.2 Config Shape

- The file should follow the same simple JSON style as other `market_intelligence` config files.
- Minimum structure:
  - `version`
  - `updated_at`
  - `items`
- Each item should contain:
  - `stock_code`
  - `marker`
  - `note`

### 6.3 First-Pass Data

- First pass contains only:
  - `000338`
- Marker value:
  - `boundary_recovered_candidate`
- Note:
  - `边界样本：因补齐渗透率标注后恢复为推荐，需人工重点复核主题集中度。`

## 7. Backend Contract

### 7.1 Recommendation Payload

- Add:
  - `special_markers: string[]`
  - `special_marker_notes: string[]`

### 7.2 Review-Board Payload

- Each link item should also carry:
  - `special_markers: string[]`
  - `special_marker_notes: string[]`

### 7.3 Marker Semantics

- A marker is informational only.
- It does not participate in:
  - recommendation ranking
  - recommendation status calculation
  - theme matching

## 8. Frontend Display

### 8.1 Display Targets

- Show the marker in:
  - the focus candidate block
  - candidate list items
  - review-board links

### 8.2 Display Style

- Use a neutral emphasis badge instead of an alert-red warning style.
- Recommended label text:
  - `边界恢复`
- Recommended helper text:
  - `因补齐渗透率标注后恢复为推荐，需人工重点复核主题集中度`

## 9. Validation Rules

- `000338` remains `recommended`
- `000338` returns:
  - `special_markers = ["boundary_recovered_candidate"]`
- `000338` returns the configured note
- The marker appears in the frontend at the intended locations
- The following do not get the marker by default:
  - `002202`
  - `002179`
  - `002354`
  - `002025`
  - `002015`
  - `600030`

## 10. Implementation Boundary

- Minimum implementation surface:
  - `config/market_intelligence/boundary_recovered_candidates.json`
  - backend payload construction in `apps/api/main.py`
  - `neotrade3-dashboard/src/pages/MarketIntelligence.jsx`
  - related backend and frontend tests
- No unrelated refactor should be introduced in this pass.

## 11. Success Definition

- The system keeps `000338` as `recommended`
- The system clearly marks it as an accepted boundary recovery sample
- The team can distinguish:
  - ordinary recommended candidates
  - recommended candidates that require extra manual concentration review
