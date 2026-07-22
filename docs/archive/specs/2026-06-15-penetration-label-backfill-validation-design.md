# Market Intelligence Penetration Label Backfill And Validation Design

Date: 2026-06-15

## 1. Goal

- This design addresses one narrow problem: several `market_intelligence` candidates are currently held in `watchlist` because their matched themes are missing from the manual penetration label file.
- The design does not change recommendation logic.
- The design does not change API contracts, frontend behavior, or theme-board ranking.
- The design only covers:
  - manual penetration-label backfill for a small set of missing themes
  - a fixed validation list to verify whether likely false negatives recover naturally after the label backfill

## 2. Confirmed Facts

- The current recommendation boundary has already been tightened:
  - weak broad anchors are no longer accepted as confirmed themes
  - `non_ai_theme`, `penetration_unknown`, and missing confirmed-theme cases can demote a candidate from `recommended` to `watchlist`
- Real-data review after that tightening shows a specific false-negative pattern:
  - several dual-role candidates remain in `watchlist`
  - they still have:
    - `institutional_attention + trading_leader`
    - `ai_related = true`
    - `kshape_direction = up`
    - a concrete non-broad matched concept
  - but they are demoted only because `penetration_stage = unknown`
- The current manual label file is `config/market_intelligence/penetration_stages.json`.
- The current file already contains manual theme labels such as:
  - `光模块 -> 10_30`
  - `芯片 -> 10_30`
  - `半导体 -> 10_30`
- Real review confirms that the following themes are currently missing from the manual label file:
  - `东数西算(算力)`
  - `数据中心`
  - `算力租赁`
  - `液冷服务器`

## 3. Scope

### 3.1 In Scope

- Add manual penetration-label rules for the missing themes listed above.
- Validate the effect on a fixed stock list after backfill.
- Keep all existing recommendation logic unchanged.

### 3.2 Out Of Scope

- No recommendation-rule changes
- No new fallback heuristics
- No broader AI-theme relabeling sweep
- No code refactor outside the minimum required file update
- No frontend changes

## 4. Target Themes

- The proposed backfill set is:
  - `东数西算(算力)`
  - `数据中心`
  - `算力租赁`
  - `液冷服务器`

## 5. Labeling Approach

### 5.1 Recommended Approach

- Use the existing `penetration_stages.json` schema.
- Add explicit `scope = "theme"` entries.
- Use `match_type = "keyword"` to stay aligned with the current file pattern.
- Assign a single concrete penetration stage to each target theme in this pass.

### 5.2 Why This Approach

- The current file already uses keyword-based theme rules.
- This keeps the change localized and consistent with the existing configuration style.
- It preserves the recommendation boundary instead of weakening it.

### 5.3 Stage Assignment Principle

- This design does not invent a broader thematic model.
- The actual stage values must follow the team’s market interpretation.
- For implementation, each target theme should receive one explicit stage value from the existing enum:
  - `0_1`
  - `1_10`
  - `10_30`
- This design assumes the team will use a single stage assignment per target theme in the first pass.

## 6. Validation Set

### 6.1 Likely False-Negative Recovery Set

- These five names are expected to be the primary validation set:
  - `002202`
  - `002179`
  - `002354`
  - `002025`
  - `002015`

### 6.2 Boundary Sample

- `000338`

### 6.3 Reason For Split

- The first five names share the same structural pattern:
  - dual-role
  - AI-related
  - upward K-shape
  - concrete matched concept
  - demoted only by `penetration_unknown`
- `000338` is different:
  - it is also demoted only by `penetration_unknown`
  - but its concept set is more mixed
  - therefore it should be reviewed as a boundary sample, not used as a hard pass/fail expectation for the backfill itself

## 7. Expected Behavior After Backfill

- For the five likely false negatives:
  - `penetration_unknown` should disappear if the matched theme is covered by the new manual labels
  - if no other negative condition exists, these names should move from `watchlist` to `recommended`
- For `000338`:
  - the result should be observed, not forced
  - it may move or remain constrained depending on the team’s view of its theme concentration
- For already-correctly-demoted weak-link samples:
  - they should remain constrained
  - for example, broad-anchor-only or non-AI names should not regain `recommended` status because of this change

## 8. Validation Procedure

### 8.1 Before/After Checks

- Re-run:
  - `GET /api/market-intelligence/recommendations`
  - `GET /api/market-intelligence/review-board`

### 8.2 Per-Stock Validation Fields

- For each validation stock, inspect:
  - `recommendation_status`
  - `risk_flags`
  - `recommendation_reasons`
  - `thematic_tags.penetration_stage`
  - `candidate.roles[*].best_concept_name`
  - `review-board.links[].matched_themes`

### 8.3 Required Pass Conditions

- The five likely false negatives no longer carry `penetration_unknown` when their matched themes are covered by the backfill.
- Their resulting status is upgraded if no other blocking condition exists.
- Weak-link suppression remains intact.
- Known non-AI or weak-anchor samples do not regress into `recommended`.

## 9. Risks

### 9.1 Main Risk

- Over-labeling a broad infrastructure theme could cause too many names to recover at once.

### 9.2 Mitigation

- Limit the first pass to the four confirmed missing themes only.
- Validate against the fixed five-stock recovery set plus `000338`.
- Re-check a known weak-link sample such as `600030` to ensure it remains constrained.

## 10. Implementation Boundary

- The minimum expected implementation surface is:
  - `config/market_intelligence/penetration_stages.json`
- No production logic changes are part of this design.
- If validation fails after the config backfill, the next step should be a new review cycle, not an immediate logic change.

## 11. Recommendation

- Proceed with targeted manual penetration-label backfill for:
  - `东数西算(算力)`
  - `数据中心`
  - `算力租赁`
  - `液冷服务器`
- Validate against:
  - `002202`
  - `002179`
  - `002354`
  - `002025`
  - `002015`
- Keep `000338` as a boundary review sample.

## 12. Success Definition

- The current stricter recommendation boundary remains unchanged.
- The five likely false negatives recover naturally if the missing manual labels were the real cause.
- The system fixes a data-readiness gap instead of compensating with weaker recommendation logic.
