# Lowfreq M3 Formal Front Build Bridge Design

Date: 2026-07-11

## 1. Goal

This design covers only the next narrow slice after the `phase1 signal contracts` extraction.

This slice only freezes:

- the engine-owned formal-front build bridge still inline in [lowfreq_engine_v16_advanced.py](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2219-L2235)
- the missing ownership gap between:
  - [formal_front.py:build_lowfreq_formal_front_payload](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/formal_front.py#L61-L163)
  - [formal_front.py:finalize_lowfreq_formal_front_payload](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/formal_front.py#L43-L58)

The goal is to:

- extend the existing `formal_front.py` owner so it also owns the DB connection lifecycle bridge for formal-front payload building
- keep `generate_buy_signals()` orchestration stable
- preserve the current formal-front output shape and error semantics exactly
- preserve current connection-closing behavior
- add direct owner-focused coverage for the new bridge helper

This design is not:

- a rewrite of `build_lowfreq_formal_front_payload(...)`
- a rewrite of `finalize_lowfreq_formal_front_payload(...)`
- a rewrite of `generate_buy_signals()` loop/orchestration
- a rewrite of M1 adapter logic
- a rewrite of formal-front projection content

Project-phase note:

- domain: `M3 formal-front build bridge`
- change type: `migration / refactor`
- NeoTrade2 remains reference only, not an active dependency

## 2. Scope

Included:

- the inline `conn -> cursor -> build_lowfreq_formal_front_payload(...) -> close` block in [lowfreq_engine_v16_advanced.py](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2219-L2230)
- one additional helper inside `neotrade3/decision_engine/formal_front.py`
- one thin engine facade for the formal-front build step
- one owner-focused test file for the bridge helper
- focused regression for:
  - [test_lowfreq_engine_v16_formal_front.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_formal_front.py)
  - [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py)

Excluded:

- changes to `build_lowfreq_formal_front_payload(...)` internals
- changes to `finalize_lowfreq_formal_front_payload(...)`
- changes to `load_formal_m1_inputs(...)`
- changes to `generate_buy_signals()` hot-sector or cross-sector loops
- changes to API or report consumers

## 3. Existing Context

Current repository evidence shows:

- `formal_front.py` already owns the formal-front projection body and payload finalize body
- `generate_buy_signals()` still owns the DB lifecycle bridge between those two steps
- `build_lowfreq_formal_front_payload(...)` has only one production caller:
  - [lowfreq_engine_v16_advanced.py](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2221-L2225)
- direct regression anchors already exist for the end-to-end formal-front chain:
  - [test_lowfreq_engine_v16_formal_front.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_formal_front.py#L126-L188)

So the current problem is not missing behavior definition. The problem is:

- the `formal_front.py` owner is still incomplete at the bridge step
- the engine still owns a small but coherent lifecycle shell
- after the `phase1 signal contracts` extraction, this is the last non-trivial local bridge in `generate_buy_signals()` before the function collapses to orchestration shell

Repository evidence:

- [formal_front.py](file:///Users/mac/NeoTrade3/neotrade3/decision_engine/formal_front.py#L43-L163)
- [lowfreq_engine_v16_advanced.py](file:///Users/mac/NeoTrade3/lowfreq_engine_v16_advanced.py#L2219-L2235)
- [test_lowfreq_engine_v16_formal_input_adapter.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_formal_input_adapter.py#L184-L202)
- [test_lowfreq_engine_v16_formal_front.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_formal_front.py#L126-L188)

## 4. Approach Options

### Option A: Extend `formal_front.py` with a connection-bridge helper and keep engine as thin facade (Recommended)

- add one helper to `formal_front.py`
- let it open a connection through an injected connection factory
- call the existing `build_lowfreq_formal_front_payload(...)`
- always close the connection
- keep the engine on a thin `_build_formal_front_payload(...)` facade

Pros:

- completes ownership inside the existing `formal_front.py` module
- keeps the change tightly scoped
- preserves the current build/finalize split while removing the engine-owned lifecycle shell

Cons:

- introduces one more helper in `formal_front.py`

### Option B: Add only an engine helper and keep the lifecycle bridge in the engine

- add `_build_formal_front_payload(...)` to the engine
- move the inline block into that method only

Pros:

- smaller diff

Cons:

- does not actually finish `formal_front.py` ownership
- only relocates the shell inside the same owner

### Option C: Leave the inline bridge as-is

Pros:

- no production code change

Cons:

- leaves a now-isolated owner gap in `generate_buy_signals()`

Decision:

- choose Option A

## 5. Design

### 5.1 Ownership Decision

`formal_front.py` should own three sequential concerns:

- build formal-front payload from a cursor
- build formal-front payload from a connection factory
- finalize formal-front payload back into the signal payload

The engine should only own:

- injecting its connection factory
- orchestrating when formal-front build/finalize is invoked

### 5.2 Recommended File Boundary

Do not create a new file.

Extend:

- `neotrade3/decision_engine/formal_front.py`

Add one helper such as:

- `build_lowfreq_formal_front_payload_from_connection(...)`

Recommended signature:

- `build_lowfreq_formal_front_payload_from_connection(connect: Callable[[], sqlite3.Connection], *, target_date: date, candidate_signals: list[dict[str, Any]], history_limit: int = 20) -> dict[str, Any]`

This helper should:

- call `connect()`
- obtain a cursor
- delegate to `build_lowfreq_formal_front_payload(...)`
- close the connection in `finally`
- suppress close failures just as the engine currently does

This helper should not:

- alter payload contents
- alter error wrapping already handled inside `build_lowfreq_formal_front_payload(...)`
- know anything about signal finalize/write-back

### 5.3 Engine Facade Boundary

Add one thin engine helper:

- `_build_formal_front_payload(...)`

Recommended signature:

- `_build_formal_front_payload(self, *, target_date: date, candidate_signals: list[dict[str, Any]]) -> dict[str, Any]`

The method should simply delegate to the new `formal_front.py` bridge helper and inject:

- `connect=self._conn`
- `history_limit=20`

Then `generate_buy_signals()` should become:

- build signal payload
- build formal payload through `_build_formal_front_payload(...)`
- finalize through `_finalize_formal_front_payload(...)`

### 5.4 Behavior Preservation Rules

This slice must preserve:

- current `formal_payload["status"]` values
- current `items_by_code` payload structure
- current `summary` structure
- current behavior when formal-front build returns `error` or `partial`
- current candidate attachment behavior after finalize
- current connection-close suppression semantics
- current fixed `history_limit=20`

No payload content changes are part of this slice.

### 5.5 Testing Strategy

Add one new owner-focused carrier:

- `tests/unit/test_lowfreq_engine_v16_formal_front_bridge.py`

Minimum owner cases:

- the new bridge helper delegates cursor-based build through a provided connection factory
- the new bridge helper closes the connection on success
- the new bridge helper also attempts to close the connection if cursor acquisition or delegated build fails

Keep and re-run consumer guards:

- [test_lowfreq_engine_v16_formal_front.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_formal_front.py)
- [test_lowfreq_engine_v16_signal_convergence.py](file:///Users/mac/NeoTrade3/tests/unit/test_lowfreq_engine_v16_signal_convergence.py)

## 6. Risks and Guardrails

Main risk:

- broadening into formal-front projection internals

Guardrail:

- keep `build_lowfreq_formal_front_payload(...)` unchanged

Secondary risk:

- changing connection-close semantics

Guardrail:

- keep `finally`-based close semantics and suppress close errors

Third risk:

- over-refactoring `generate_buy_signals()` loop shell

Guardrail:

- change only the formal-front build bridge

## 7. Implementation Outline

Planned steps:

1. extend `formal_front.py` with the connection-bridge helper
2. add `_build_formal_front_payload(...)` thin facade to the engine
3. replace the inline build block in `generate_buy_signals()`
4. add owner-focused tests for the bridge helper
5. run focused syntax and regression verification

## 8. Success Criteria

This slice is complete when:

- `formal_front.py` owns the build bridge in addition to build/finalize bodies
- `generate_buy_signals()` no longer owns the inline DB lifecycle bridge
- formal-front payload shape stays unchanged
- owner-focused bridge tests pass
- current formal-front end-to-end regression still passes
