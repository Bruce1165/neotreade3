# Lowfreq M3 Market Filter Note Design

Date: 2026-07-11

## 1. Goal

This design covers only the next narrow slice after the `signal seed owner` extraction.

This slice only freezes:

- the `market sentiment -> capture-first market_filter_note/log message` block at the top of `generate_buy_signals()`

The goal is to:

- move the market-filter note resolution into a dedicated `M3` owner
- keep `get_market_sentiment()` ownership and SQL behavior unchanged
- keep `generate_buy_signals()` orchestration stable
- preserve the current note/log copy contract exactly
- add direct owner-focused coverage for the note-resolution contract

This design is not:

- a rewrite of `get_market_sentiment()`
- a rewrite of `generate_buy_signals()`
- a rewrite of candidate sourcing, dedup, payload assembly, or formal-front handling
- a redesign of market sentiment thresholds

Project-phase note:

- domain: `M3 decision gating`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency

## 2. Scope

Included:

- the top block inside [generate_buy_signals](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2223-L2232) that:
  - calls `get_market_sentiment(...)`
  - compares `market_score` with `MIN_MARKET_SCORE`
  - derives `market_filter_note`
  - chooses the log copy
- one new `decision_engine` owner module for the note-resolution contract
- engine/internal call-site preservation
- owner-focused tests for note generation and log-copy resolution
- focused regression for:
  - [test_lowfreq_engine_v16_signal_seed.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_seed.py)
  - [test_lowfreq_engine_v16_signal_payload.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_payload.py)

Excluded:

- [get_market_sentiment](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L1732-L1787)
- API/report callers that directly use `get_market_sentiment(...)`
- `generate_buy_signals()` orchestration changes beyond preserving the current call point
- hot-sector / cross-sector candidate generation
- signal seed shaping
- signal deduplication
- signal payload assembly
- formal-front build/finalize

## 3. Existing Context

Current repository evidence shows four important facts:

- the engine still owns the note/log resolution inline:
  - [lowfreq_engine_v16_advanced.py:L2225-L2232](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2225-L2232)
- `get_market_sentiment(...)` has direct consumers outside `generate_buy_signals()`:
  - [generate_lowfreq_top200_attribution_report.py:L339-L343](file:///Users/mac/NeoTrade3/scripts/generate_lowfreq_top200_attribution_report.py#L339-L343)
  - [main.py:L27191-L27193](file:///Users/mac/NeoTrade3/apps/api/main.py#L27191-L27193)
- current owner tests already protect the downstream note consumers:
  - [test_lowfreq_engine_v16_signal_seed.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_seed.py)
  - [test_lowfreq_engine_v16_signal_payload.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_payload.py)
- there is no existing shared helper that converts sentiment/score/threshold into the capture-first note copy

The problem is not uncertainty about behavior. The problem is:

- the note-resolution contract is still embedded in the engine monolith
- `get_market_sentiment(...)` is too broad because it has independent callers
- the current note/log copy contract has no direct owner-focused carrier

## 4. Approach Options

### Option A: Extract a dedicated `decision_engine` note-resolution owner and keep engine as a thin facade (Recommended)

- add a small `decision_engine` helper module
- move only the note/log resolution there
- keep `get_market_sentiment(...)` in the engine

Pros:

- isolates the narrowest remaining market-filter block
- avoids touching broader sentiment SQL ownership
- preserves current engine call order

Cons:

- adds one small production file

### Option B: Extract the whole `get_market_sentiment(...)` path

- move SQL and note generation together
- make engine call the new owner end-to-end

Pros:

- larger ownership move

Cons:

- crosses into a broader surface with API/report consumers
- exceeds current narrow-slice evidence

### Option C: Keep production code unchanged and add tests only

- preserve the note block inside engine
- add direct tests around current engine behavior

Pros:

- smallest code diff

Cons:

- does not reduce engine ownership
- leaves the note-resolution owner unfinished

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

This slice should own:

- converting `enabled + sentiment + market_score + min_market_score` into a narrow resolution result
- deriving `market_filter_note`
- deriving the current log copy

These responsibilities should be treated as:

- `M3 capture-first market filter note resolution`

They should not be treated as:

- market sentiment data retrieval
- market sentiment scoring
- API/report market filter state formatting
- signal seed/payload shaping

### 5.2 Recommended File Boundary

Recommended new module:

- `neotrade3/decision_engine/market_filter_note.py`

This module should own:

- `resolve_capture_first_market_filter_note(...)`

Recommended signature:

- `resolve_capture_first_market_filter_note(*, enabled: bool, sentiment: Any, market_score: float, min_market_score: float) -> dict[str, Any]`

Recommended output contract:

- `note`: `str | None`
- `log_message`: `str | None`
- `score_below_threshold`: `bool`

This helper should:

- accept sentiment-like inputs that expose either `.value` or a string form
- return `note=None` and `log_message=None` when disabled
- return the current capture-first downgrade note when enabled and score is below threshold
- return the current informational log copy when enabled and score is not below threshold

This helper should not own:

- DB access
- `get_market_sentiment(...)`
- logging side effects

### 5.3 Engine Compatibility Surface

The engine should keep the current top-level order:

- call `get_market_sentiment(...)`
- pass the result into the note owner
- emit `logger.info(...)` only when the owner returns a log copy
- reuse `note` downstream as before

This preserves the current downstream flow:

- market sentiment retrieval
- note/log resolution
- signal seed shaping
- dedup
- payload assembly
- formal-front handling

### 5.4 Behavior Preservation Rules

This slice must preserve the current semantics exactly:

- when `enabled` is false:
  - `note` is `None`
  - `log_message` is `None`
  - `score_below_threshold` is `False`
- when `enabled` is true and `market_score < min_market_score`:
  - `note` is `capture-first: 市场情绪{sentiment} ({score:.0f}分)，降权但不暂停买入`
  - `log_message` equals that same note
  - `score_below_threshold` is `True`
- when `enabled` is true and `market_score >= min_market_score`:
  - `note` is `None`
  - `log_message` is `市场情绪: {sentiment} ({score:.0f}分)`
  - `score_below_threshold` is `False`

No threshold changes and no sentiment-score changes are included in this slice.

### 5.5 Testing Strategy

Add one new owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_market_filter_note.py`

This carrier should directly exercise `resolve_capture_first_market_filter_note(...)` and cover at least:

- disabled mode returns an empty resolution
- below-threshold mode emits the capture-first downgrade note
- non-below-threshold mode emits the informational log copy
- sentiment objects with `.value` are rendered correctly

Focused regression should continue to re-run:

- [test_lowfreq_engine_v16_signal_seed.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_seed.py)
- [test_lowfreq_engine_v16_signal_payload.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_payload.py)

## 6. Risks and Guardrails

Main risk:

- accidentally changing the capture-first note copy while moving the owner

Guardrails:

- preserve the current string template exactly
- keep the score formatting as `{score:.0f}`
- avoid touching `get_market_sentiment(...)` in the same slice
- avoid mixing API/report market-filter state formatting into this helper

## 7. Implementation Outline

Planned implementation steps:

1. add `neotrade3/decision_engine/market_filter_note.py`
2. move the note/log resolution into `resolve_capture_first_market_filter_note(...)`
3. switch `generate_buy_signals()` to call the owner
4. add `tests/unit/test_lowfreq_engine_v16_market_filter_note.py`
5. run minimal syntax and focused pytest verification

## 8. Success Criteria

This slice is complete when:

- the real market-filter note owner lives outside `lowfreq_engine_v16_advanced.py`
- `get_market_sentiment(...)` stays unchanged
- `generate_buy_signals()` keeps the same note/log semantics
- an owner-focused test directly protects the note contract
- downstream note consumers still pass
