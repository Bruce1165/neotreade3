# Market Intelligence Review Board Classified Candidate Snapshot Reuse Design

Date: 2026-06-15

## 1. Goal

- This design addresses one narrow performance problem in the market-intelligence review chain.
- Current evidence shows `review-board` still spends most of its time rebuilding candidate classifications twice:
  - once for `theme-board`
  - once for `recommendations`
- The goal is to let `review-board` build one larger classified candidate snapshot internally, then derive both outputs from that shared snapshot.
- The design must not change:
  - HTTP response structure
  - recommendation business rules
  - theme scoring rules
  - focus-theme selection rules
  - boundary recovered markers

## 2. Confirmed Facts

- `review-board.links` is not the current bottleneck.
- Measured `review-board(top_n=20)` residual link assembly time is approximately `0.003s`.
- After earlier optimizations, the main cost is still inside repeated candidate classification work.
- Measured service-side breakdown shows:
  - `theme_board_payload` remains one major block
  - `recommendations_payload` remains another major block
  - both blocks still drive large volumes of `_load_market_intelligence_for_stock(...)`
- Sharing only the candidate seed snapshot reduced some repeated seed query work, but did not materially reduce total `review-board` latency.

## 3. Root Cause

- The system currently shares only shallow input state:
  - seed codes
  - stock summary cache
- But `theme-board` and `recommendations` still each rebuild the three classified candidate lists:
  - `config_leader_candidates`
  - `institutional_attention_candidates`
  - `trading_leader_candidates`
- That means the heaviest stage is still duplicated:
  - stock-level summary load
  - tag inspection
  - role classification
  - candidate list sorting

## 4. Recommended Approach

- Introduce one internal snapshot layer inside `review-board`:
  - `classified_candidate_snapshot`
- This snapshot is not a new public API payload.
- It is only an internal reusable intermediate result.
- `review-board` should:
  - build one larger classified candidate snapshot first
  - pass that snapshot into `theme-board`
  - pass the same snapshot into `recommendations`
- `theme-board` and `recommendations` should keep their own current truncation semantics by slicing from the shared snapshot rather than rebuilding it.

## 5. Why This Approach

- It directly targets the current repeated heavy work instead of optimizing cheap layers.
- It is narrower and lower risk than rewriting `_load_market_intelligence_for_stock(...)` into a batch pipeline.
- It keeps the current module boundaries understandable:
  - one internal layer prepares classified candidates
  - one layer builds themes
  - one layer builds recommendations
- It preserves user-approved business semantics while reducing repeated computation.

## 6. Internal Snapshot Contract

- The internal snapshot should contain:
  - `config_leader_candidates`
  - `institutional_attention_candidates`
  - `trading_leader_candidates`
  - `coverage`
  - any internal metadata needed to confirm the build scope
- Each candidate item in the snapshot should keep the current per-role structure unchanged.
- The snapshot should be generated from the maximum scan range needed by the current `review-board` call.
- The snapshot should remain in-memory for the duration of one request only.
- No on-disk cache is introduced in this design.

## 7. Semantic Guardrails

- Shared internal construction is allowed.
- Shared external semantics are not allowed to drift.
- Specifically:
  - `theme-board` must still behave as if it only consumed its current intended candidate scope
  - `recommendations` must still behave as if it only consumed its current intended candidate scope
- Therefore the shared snapshot must support downstream slicing without cross-contaminating the two consumers.
- This means:
  - `theme-board` may use the larger upstream classified snapshot, but only the portion that matches its current scope rules
  - `recommendations` may use the same upstream classified snapshot, but only the portion that matches its current scope rules

## 8. Execution Shape

### 8.1 New Internal Flow

- `review-board`
  - build `classified_candidate_snapshot`
  - call `theme-board` with shared snapshot
  - call `recommendations` with shared snapshot
  - assemble links exactly as before

### 8.2 Theme Board

- `theme-board` should accept an optional shared classified snapshot.
- If provided, it should skip rebuilding classified candidates.
- If not provided, it should preserve current standalone behavior.

### 8.3 Recommendations

- `recommendations` should accept an optional shared classified snapshot.
- If provided, it should skip rebuilding classified candidates.
- If not provided, it should preserve current standalone behavior.

### 8.4 Standalone Endpoints

- Standalone calls must keep working unchanged:
  - `themes`
  - `recommendations`
  - `unified-candidates`
  - `candidates`
- The reuse path is an optimization for `review-board`, not a redesign of all endpoint contracts.

## 9. Scope Boundary

- In scope:
  - one shared internal classified candidate snapshot
  - wiring `review-board` to reuse that snapshot
  - preserving current downstream slicing semantics
  - regression and real-API verification
- Out of scope:
  - batch rewrite of `_load_market_intelligence_for_stock(...)`
  - theme score redesign
  - recommendation rule redesign
  - `links` redesign
  - frontend changes

## 10. Risks

- Main risk:
  - if the shared snapshot scope is too broad and downstream slicing is incorrect, `theme-board` or `recommendations` may see candidates they should not have seen before
- Secondary risk:
  - tests may pass on structure while result ordering subtly drifts
- Therefore validation must focus on:
  - output equivalence
  - focus-theme stability
  - recommendation coverage stability
  - boundary marker stability

## 11. Validation Plan

### 11.1 Regression

- Run `tests/unit/test_market_intelligence_summary.py`
- Confirm:
  - unified candidate merging is unchanged
  - recommendation status rules are unchanged
  - review-board weak-link suppression is unchanged
  - boundary markers are unchanged
  - focus-theme selection is unchanged

### 11.2 Real Output Equivalence

- Compare before and after on real endpoints:
  - `themes?top_n=20`
  - `review-board?top_n=20`
  - `recommendations?top_n=20`
- Confirm:
  - top themes do not drift unexpectedly
  - `review_focus.theme` remains the same
  - recommendation coverage counts remain the same
  - `002202` and `000338` still carry `boundary_recovered_candidate`

### 11.3 Performance Check

- Measure service-side timing for `review-board(top_n=20)`.
- Confirm that the new design reduces repeated classified-candidate construction.
- Expected signal:
  - fewer repeated internal candidate-classification passes
  - lower total `review-board` latency than the current baseline

## 12. Success Definition

- `review-board` no longer rebuilds the full classified candidate lists twice in the same request.
- Result semantics remain unchanged from the user-visible perspective.
- Real `review-board?top_n=20` latency decreases materially relative to the current baseline.
- If latency does not decrease materially, this design should be considered exhausted and the next step should move to a deeper batch strategy instead of more small optimizations.
