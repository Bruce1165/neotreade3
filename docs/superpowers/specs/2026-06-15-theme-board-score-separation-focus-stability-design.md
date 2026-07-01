# Market Intelligence Theme Board Score Separation And Focus Stability Design

Date: 2026-06-15

## 1. Goal

- This design addresses one narrow problem:
  - `themes` ranking and `review-board.review_focus.theme` are currently too sensitive to `top_n`
- The goal is to make the focus theme represent a more stable mainline judgment.
- The design does not change:
  - recommendation logic
  - penetration-stage rules
  - boundary recovered markers
  - candidate generation logic

## 2. Confirmed Facts

- Current real-data review shows that changing `top_n` changes the focus theme on the same trade date.
- Example on `2026-06-12`:
  - `top_n=5` -> focus theme `数据中心`
  - `top_n=10` -> focus theme `数据中心`
  - `top_n=15` -> focus theme `MCU芯片`
  - `top_n=20` -> focus theme `数据中心`
  - `top_n=30` -> focus theme `东数西算(算力)`
  - `top_n=40` -> focus theme `东数西算(算力)`
- The current theme board score is heavily driven by:
  - matched candidate counts
  - matched candidate scores
- The current `review-board.review_focus.theme` directly follows the first theme returned by `themes`.
- Therefore, the current focus theme is not stable enough to serve as a clean mainline signal.

## 3. Root Cause

- The current theme board mixes two different ideas into one score:
  - theme intrinsic strength
  - candidate resonance strength
- Theme intrinsic strength should represent the theme itself.
- Candidate resonance strength should represent how strongly the current candidate pool echoes that theme.
- Right now both are combined into one `board_score`, and the candidate-driven portion expands when `top_n` expands.
- This makes the final focus theme overly dependent on candidate truncation.

## 4. Recommended Approach

- Split the current theme score into two explicit parts:
  - `base_score`
  - `resonance_score`
- Keep a combined score:
  - `total_score`
- Use the following focus rule:
  - focus theme should prioritize `base_score`
  - `resonance_score` remains visible as supporting evidence

## 5. Why This Approach

- It matches the team workflow:
  - first identify the mainline
  - then see whether current candidates resonate with it
- It reduces parameter sensitivity without throwing away candidate information.
- It keeps the system readable:
  - stable theme judgment
  - clear candidate resonance explanation

## 6. Score Design

### 6.1 Base Score

- `base_score` should come mainly from stable theme-layer information already present in `ths_concept_daily`.
- It should rely on fields such as:
  - `mainline_rank`
  - `heat_rank`
  - `risk_level`
  - optional light use of `trend_state`
- `base_score` should avoid direct dependence on the size of the truncated candidate set.

### 6.2 Resonance Score

- `resonance_score` should continue to reflect candidate co-occurrence and candidate quality.
- It may use:
  - matched config candidate count
  - matched institutional candidate count
  - matched trading candidate count
  - limited contribution from top candidate scores
- This is the part that may vary with `top_n`, and that is acceptable as long as it is kept separate.

### 6.3 Total Score

- `total_score = base_score + resonance_score`
- `total_score` remains useful for full theme-board display.
- But `total_score` should no longer be the only source of the focus theme.

## 7. Focus Theme Rule

- `review-board.review_focus.theme` should primarily follow the theme with the strongest `base_score`.
- If multiple themes are very close on `base_score`, then `resonance_score` may be used as a secondary tie-breaker.
- This means:
  - the mainline focus becomes more stable
  - candidate resonance still matters, but it cannot dominate the focus theme by itself

## 8. Output Contract

### 8.1 Theme Payload

- Each theme item should expose:
  - `base_score`
  - `resonance_score`
  - `total_score`
- Existing fields such as:
  - candidate counts
  - top stocks
  - thematic tags
  - `ths_mainline`
  remain available

### 8.2 Focus Theme Payload

- The focus theme may still expose the familiar display fields:
  - `concept_code`
  - `concept_name`
  - `total_score`
- But it should also expose:
  - `base_score`
  - `resonance_score`
- This makes the selection reason auditable.

## 9. Frontend Direction

- No new page is needed.
- The theme card can keep one primary score display.
- Secondary score detail can be shown as:
  - 主线分
  - 共振分
- The focus-theme card should visually indicate that the current focus is based on stable mainline priority.

## 10. Validation Plan

### 10.1 Stability Check

- Compare the same trade date under:
  - `top_n=10`
  - `top_n=20`
  - `top_n=30`
  - `top_n=40`
  - `top_n=60`
- The goal is not that all rankings stay identical.
- The goal is that the focus theme becomes materially more stable.

### 10.2 Score Behavior Check

- `base_score` should stay relatively stable across `top_n`.
- `resonance_score` may vary with `top_n`.
- `total_score` may vary, but should not cause focus-theme whiplash unless the underlying base scores are genuinely close.

### 10.3 Regression Check

- Candidate recommendation results should remain unchanged.
- Boundary recovered markers should remain unchanged.
- Existing theme links should remain explainable.

## 11. Scope Boundary

- In scope:
  - theme score separation
  - focus-theme selection rule
  - related payload updates
  - minimal frontend display updates if implemented later
- Out of scope:
  - recommendation logic changes
  - candidate scoring changes
  - boundary-marker redesign
  - new multi-focus interaction design

## 12. Recommendation

- Proceed with:
  - separating theme board scoring into `base_score` and `resonance_score`
  - keeping `total_score` for overall display
  - making focus theme prioritize `base_score`
- This is the smallest change that aligns the system with the team’s operational logic:
  - mainline first
  - candidates second

## 13. Success Definition

- Focus theme no longer changes dramatically when `top_n` changes within normal review ranges.
- Theme-layer judgment becomes more stable and interpretable.
- Candidate resonance remains visible without hijacking the mainline focus.
