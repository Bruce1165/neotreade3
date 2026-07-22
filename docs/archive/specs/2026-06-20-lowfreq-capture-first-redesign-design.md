# Lowfreq Capture-First Redesign Design

Date: 2026-06-20  
Scope: Buy-side capture-first redesign, hard-gate collapse, Top200 funnel attribution, stability diagnosis, phased recovery targets

## 1. Background

The current model is unstable in a structural way, not a random way.

We now have strong evidence of two opposite failure modes:

1. Earlier state:
   - sell-side logic was too dominant
   - `market_top` was over-triggering
   - the model could exit too early

2. Current state after tightening `market_top` and fixing `301* -> 创业板`:
   - the latest 18-month backtest collapses to `1` trade
   - total return drops to `6.26%`
   - `2025 Top200` attribution shows:
     - `picked_count = 0`
     - `bought_count = 0`
     - `held_to_top_count = 0`

This means the dominant problem is no longer the exit side.
The dominant problem is that the buy-side architecture is over-constrained upstream and fails to capture large winners at all.

The user has explicitly confirmed the target direction:

- primary objective: `capture rate first`
- loosen aggressively
- avoid dumb mistakes
- keep hard only: `execution safety`

This design follows that direction exactly.

## 2. Target State

The target state is not “high precision first”.
The target state is:

- most large winners should be spotted
- a meaningful portion of them should be bought
- the model should track and carry far more real winner candidates than it does now
- execution safety remains hard
- most other buy-side hard filters are demoted into ranking or audit layers

In other words:

```text
capture first -> then stabilize -> then optimize holding and precision
```

## 3. Problem Statement

### 3.1 Current architecture rejects too early

The current buy chain kills opportunities in multiple upstream stages:

- hot-sector seed entry
- cross-sector scan entry
- fundamentals hard filter
- structure confirmation hard filter
- focus gate
- resonance gate
- follower exclusion
- cross-sector score margin and capacity caps

These gates are individually understandable, but together they form a stacked early-rejection system.

For the current objective, that architecture is wrong.

### 3.2 The current model optimizes selectivity before capture

The system behaves as if:

- avoiding false positives is more important than seeing large winners

But the user’s objective is now the opposite:

- miss fewer 大牛股 first
- accept more noise temporarily

### 3.3 Instability comes from interacting gates, not one threshold

The evidence already shows that the model does not fail because one threshold is slightly too high.
It fails because several gates interact:

- a name may fail seed scan on one day
- enter seed later but fail structure
- survive structure later but fail focus
- survive focus later but lose on cross-sector margin

This creates a system that is hard to reason about and highly unstable under small logic changes.

## 4. Guiding Principles

1. Capture rate is the first optimization target.
2. Only execution safety remains hard.
3. Buy-side opportunity visibility is more important than early purity.
4. Market facts and model behavior must remain separate in reporting.
5. We do not claim “improvement” from backtest summary alone; we must measure funnel coverage explicitly.
6. We must avoid obvious market mistakes:
   - no unsupported asset remapping
   - no non-A-share contamination in Top200
   - no impossible execution assumptions

## 5. Approach Options

### Approach A: Capture-first rewrite with hard-gate collapse

- Collapse most hard buy-side filters into ranking/audit layers.
- Keep only execution safety hard.
- Add a full winner-capture funnel.

Pros:
- directly aligned with user objective
- fastest path to restoring winner coverage
- makes failure stages measurable

Cons:
- more false positives temporarily
- backtest quality may worsen before stabilizing

### Approach B: Staged loosening

- loosen only seed scan and cross-sector entry first
- keep structure/focus/fundamentals partly hard

Pros:
- lower short-term operational risk

Cons:
- too conservative for the current evidence
- likely too slow to restore coverage

### Approach C: Diagnose first, do not change logic yet

Pros:
- minimizes immediate behavior change

Cons:
- does not solve the active failure mode
- delays recovery of capture rate

Conclusion:
- adopt Approach A

## 6. Design Overview

The redesign has four coordinated workstreams.

### 6.1 Workstream A: Collapse hard buy gates

Goal:
- stop rejecting large-winner candidates too early

Rules:

- Keep hard only:
  - executable price bar exists
  - impossible limit-up buy is blocked
  - insufficient cash remains blocked
  - position cap remains blocked
  - minimum tradable amount remains blocked if enforced

- Demote from hard reject to ranking / penalty / audit:
  - hot-sector seed entry
  - cross-sector scan entry
  - fundamentals gate
  - structure confirmation
  - focus gate
  - resonance threshold
  - follower exclusion
  - cross-sector score margin
  - cross-sector max signals

Expected effect:
- more names survive into ranked opportunity space
- fewer large winners die before the model even “sees” them

### 6.2 Workstream B: Build a capture funnel

For each target stock, especially each `2025 Top200` name, record its state through the full funnel:

1. in valid tradable universe
2. in seed scan
3. in candidate pool
4. in ranked shortlist
5. in formal buy signals
6. actually bought
7. still held during main run
8. exited before top / at top / after top

This funnel must be built with daily traceability.

Without this, “why didn’t we catch it?” remains hand-wavy.

### 6.3 Workstream C: Separate capture from hold

We must stop mixing three different abilities:

- spotting winners
- entering winners
- holding winners

The redesign will use separate metrics for:

- `capture rate`
  - was the stock ever selected or bought during its main run
- `entry conversion`
  - among picked names, how many were actually bought
- `hold-to-top rate`
  - among bought names, how many were meaningfully held through their main run

### 6.4 Workstream D: Stability diagnosis by stage

The model is unstable because several interacting stages can change effective behavior dramatically.

The redesign must measure stage-level leakage, not just final backtest metrics.

That means every major reject path must be attributable to one stage, not collapsed into vague narratives.

## 7. Hard-Gate Collapse Plan

### 7.1 What stays hard

Only execution safety:

- missing price bar
- impossible limit-up buy
- insufficient cash
- position cap
- minimum tradable amount / participation constraint, if enabled

### 7.2 What becomes soft

The following should no longer immediately kill a candidate:

- not in hot sectors
- not in cross-sector top seed group
- fundamentals not passing ideal profile
- structure confirm not passing
- focus gate not passing
- low resonance
- follower role
- lower relative cross-sector score

Instead, each of these becomes:

- a penalty term
- a ranking feature
- an attribution signal

### 7.3 Why this is necessary

The current Top200 report already proves that upstream exclusion is the dominant miss driver.
Until these gates are softened, improving exits or fine-tuning sell logic will not solve the main failure.

## 8. Capture Funnel Specification

For each stock-day in the target attribution scope, produce a daily state record with:

- `trade_date`
- `in_universe`
- `seed_seen`
- `candidate_seen`
- `ranked_seen`
- `signal_selected`
- `executed_buy`
- `held_position`
- `exited`
- `primary_stage`
- `primary_reason`

For each stock across its main run, produce rolled-up fields:

- first seen date
- first signal date
- first buy date
- exit date
- whether held to market-defined top
- main failure stage
- main failure reason

## 9. Metrics

### 9.1 Primary metrics

These become the first success criteria:

- `Top200 picked_count`
- `Top200 bought_count`
- `Top200 held_to_top_count`
- `Top200 seed coverage`
- `Top200 candidate coverage`
- `Top200 signal coverage`

### 9.2 Secondary metrics

- 18-month total trades
- 18-month total return
- 18-month max drawdown
- win rate
- sell reason distribution

These still matter, but they are not the first optimization target in this phase.

## 10. Stability Diagnosis Framework

We define instability as:

- small rule changes producing large coverage collapse
- or large shifts between capture and non-capture states without clear stage attribution

The new diagnosis framework must answer:

1. which stage removes the most winner candidates
2. whether misses are concentrated or widely distributed
3. whether the system is fragile to one gate or to interaction of many gates
4. whether loosening restores coverage broadly or only for one subgroup

## 11. Risk Controls

Aggressive loosening does not mean careless loosening.

The following controls remain mandatory:

### 11.1 Execution realism

- no impossible buys through limit-up bars
- no fake fills without price bars
- no buying without cash

### 11.2 Market classification sanity

- keep proper A-share universe boundaries
- no silent remap of unsupported assets
- keep `301* -> 创业板` correctly mapped

### 11.3 Reporting discipline

- market-defined top and model-defined exit remain separate
- no narrative claims without funnel evidence

## 12. Implementation Shape

### 12.1 Buy-side logic

Files likely impacted:

- `lowfreq_engine_v16_advanced.py`

Changes:

- reduce hard rejects in candidate and signal generation
- preserve execution safety gates
- expose more stage outputs for attribution

### 12.2 Funnel attribution

Files likely impacted:

- `scripts/generate_lowfreq_top200_attribution_report.py`
- possibly supporting analysis code if extraction needs reuse

Changes:

- extend from static post-hoc reasoning into structured funnel outputs
- support before/after logic comparisons where useful

### 12.3 Validation

Validation must include:

- unit tests for softened gating behavior
- 18-month backtest re-run
- `2025 Top200` attribution refresh
- comparison of coverage deltas before and after redesign

## 13. Success Criteria

Phase-1 success means:

1. `Top200 picked_count` rises materially from `0`
2. `Top200 bought_count` rises materially from `0`
3. dominant miss reason is no longer “never entered seed scan”
4. 18-month backtest no longer collapses to near-zero trades

Phase-1 does not require:

- perfect drawdown
- perfect precision
- perfect hold-to-top rate

Those are later-phase objectives.

## 14. Non-Goals

This phase is not trying to:

- maximize Sharpe
- minimize drawdown first
- fully optimize exits
- fully restore high precision

This phase is specifically about recovering winner visibility and entry coverage.

## 15. Conclusion

The model’s current instability is primarily a buy-side over-filtering problem.

The correct next move is:

- collapse hard buy gates aggressively
- keep only execution safety hard
- build a full capture funnel
- measure winner coverage explicitly
- optimize capture first, then stabilize holding and risk later

This is the intended design baseline for the next implementation plan.
