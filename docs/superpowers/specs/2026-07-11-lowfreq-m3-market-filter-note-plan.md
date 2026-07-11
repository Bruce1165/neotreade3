# Lowfreq M3 Market Filter Note Plan

Date: 2026-07-11
Design:

- `docs/superpowers/specs/2026-07-11-lowfreq-m3-market-filter-note-design.md`

## 1. Goal

This plan covers only the next narrow `M3 capture-first market filter note resolution` slice after the `signal seed owner` extraction.

This slice only handles:

- the top `sentiment/score -> market_filter_note/log copy` block inside `generate_buy_signals()`

The goal is to:

- move the real note-resolution logic into a dedicated `decision_engine` owner
- keep `get_market_sentiment()` unchanged
- keep `generate_buy_signals()` orchestration stable
- preserve the current note and log-copy semantics exactly
- add owner-focused coverage for the note-resolution contract

This slice does not:

- rewrite `get_market_sentiment()`
- rewrite `generate_buy_signals()` orchestration
- rewrite signal seed shaping, dedup, payload assembly, or formal-front handling

## 2. Starting Point

The current note owner still lives inline inside:

- `lowfreq_engine_v16_advanced.py`

The current block owns exactly these rules:

- when market filtering is disabled, emit no note and no log copy
- when enabled and score is below threshold, emit the capture-first downgrade note
- when enabled and score is not below threshold, emit the informational market log copy
- keep the score formatting as `{score:.0f}`

Existing owner/consumer-facing coverage already exists here:

- `tests/unit/test_lowfreq_engine_v16_signal_seed.py`
- `tests/unit/test_lowfreq_engine_v16_signal_payload.py`

Those carriers protect downstream note consumers, but they still do not directly pin the note owner semantics as a standalone unit.

## 3. Implementation Strategy

Use the same thin-facade extraction pattern as earlier slices, with one dedicated owner module under `decision_engine`:

- add a new owner module:
  - `neotrade3/decision_engine/market_filter_note.py`
- move the real note-resolution body into:
  - `resolve_capture_first_market_filter_note(...)`
- keep `lowfreq_engine_v16_advanced.py` responsible only for:
  - calling `get_market_sentiment(...)`
  - passing explicit parameters into the owner
  - logging the returned `log_message`
  - reusing the returned `note` downstream
- add one new owner-focused carrier:
  - `tests/unit/test_lowfreq_engine_v16_market_filter_note.py`
- keep the existing signal-seed and signal-payload tests as compatibility guards

## 4. Execution Steps

### M3-MFN-S1: Freeze file boundary and note contract

Before implementation, freeze the production/test file set to:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/market_filter_note.py`
- `tests/unit/test_lowfreq_engine_v16_market_filter_note.py`

Keep these existing consumer guards unchanged:

- `tests/unit/test_lowfreq_engine_v16_signal_seed.py`
- `tests/unit/test_lowfreq_engine_v16_signal_payload.py`

Freeze the observable note contract:

- disabled mode returns no note and no log message
- below-threshold mode returns:
  - `capture-first: 市场情绪{sentiment} ({score:.0f}分)，降权但不暂停买入`
- non-below-threshold mode returns:
  - `市场情绪: {sentiment} ({score:.0f}分)`
- score formatting remains `{score:.0f}`
- `get_market_sentiment()` behavior and ownership remain unchanged

Completion check:

- no downstream consumer should need to change its expectations about the note string

### M3-MFN-S2: Implement the shared note owner

Create:

- `neotrade3/decision_engine/market_filter_note.py`

Move the rule body into that module:

- `resolve_capture_first_market_filter_note(...)`

Implementation rules:

- the module must not read engine state directly
- the module reads only explicit parameters
- the module accepts sentiment-like inputs with either `.value` or string form
- the module preserves the current note/log templates exactly

Completion check:

- the note-resolution contract can be understood independently from `generate_buy_signals()`

### M3-MFN-S3: Convert engine call site to a thin facade

In `lowfreq_engine_v16_advanced.py`:

- import the note owner
- keep the existing `get_market_sentiment(...)` call
- replace the inline note/log resolution with one owner call
- log the returned `log_message` only when present

Do not change:

- `get_market_sentiment()`
- market-filter thresholds
- signal seed shaping
- deduplication
- payload assembly
- formal-front build/finalize

Completion check:

- engine no longer owns the real note-resolution body

### M3-MFN-S4: Add owner-focused tests

Create:

- `tests/unit/test_lowfreq_engine_v16_market_filter_note.py`

Minimum owner cases:

- disabled mode returns an empty resolution
- below-threshold mode emits the downgrade note
- non-below-threshold mode emits the informational log message
- sentiment objects with `.value` render correctly

Keep and re-run the existing consumer guards:

- `tests/unit/test_lowfreq_engine_v16_signal_seed.py`
- `tests/unit/test_lowfreq_engine_v16_signal_payload.py`

Completion check:

- the note owner has a direct focused carrier
- downstream note consumers still pass unchanged

### M3-MFN-S5: Minimum verification

Run at minimum:

- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_market_filter_note.py`
- `python3 -m pytest tests/unit/test_lowfreq_engine_v16_signal_seed.py tests/unit/test_lowfreq_engine_v16_signal_payload.py`
- `python3 -m py_compile lowfreq_engine_v16_advanced.py neotrade3/decision_engine/market_filter_note.py tests/unit/test_lowfreq_engine_v16_market_filter_note.py`

Completion check:

- owner tests pass
- consumer tests pass
- syntax validation passes

### M3-MFN-S6: Narrow commit

Before committing, stage only:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/market_filter_note.py`
- `tests/unit/test_lowfreq_engine_v16_market_filter_note.py`

Must exclude:

- `signal_seed.py`
- `signal_payload.py`
- `formal_front.py`
- API/report files
- `tests/unit/test_bootstrap_skeleton.py`
- any unrelated workspace changes

## 5. Risks And Guards

Risk 1:

- changing the capture-first note copy while moving the owner

Guard:

- preserve the current string template exactly

Risk 2:

- broadening this slice into full market sentiment ownership

Guard:

- keep `get_market_sentiment()` unchanged and out of this slice

Risk 3:

- mixing API/report market-filter formatting into the helper

Guard:

- keep the helper limited to `generate_buy_signals()` note/log semantics only

Risk 4:

- breaking downstream note consumers through a formatting drift

Guard:

- re-run signal-seed and signal-payload note consumer tests

## 6. Success Criteria

This slice is complete when:

- the real market-filter note owner lives in `decision_engine`
- engine keeps only a thin note-resolution call site
- `get_market_sentiment()` stays unchanged
- public `generate_buy_signals()` note/log behavior stays unchanged
- an owner-focused test directly protects the note owner
- signal-seed and signal-payload consumer tests still pass

## 7. Commit Boundary

The plan commit should include only:

- `docs/superpowers/specs/2026-07-11-lowfreq-m3-market-filter-note-plan.md`

It must exclude:

- `lowfreq_engine_v16_advanced.py`
- `neotrade3/decision_engine/*`
- `tests/unit/*`
- any other workspace changes
