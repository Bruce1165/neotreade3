# Top100 Scorecard and Layered Elite-Stock Framework Design

Date: 2026-06-21
Scope: Elite-stock research framework, Top100 evaluation scorecard, rolling elite-segment mining, layered discovery/hold/peak formula design, no-lookahead validation path

## 1. Background

Recent rounds of work already established several important facts:

1. Continuing to widen or tighten isolated sell-side thresholds is not enough.
2. The strategy can improve or degrade materially from small local changes, which means the current architecture is still too threshold-driven and not pattern-driven.
3. The strongest evidence gap is upstream:
   - many elite stocks are not discovered early enough
   - some are discovered but not converted into actual positions
   - some are bought but their hold/exit behavior is still governed by rules that are not explicitly pattern-layered
4. Annual winner statistics show the opportunity set is far richer than the current realized strategy return:
   - `Top100` average annual return is far above current model return
   - therefore the dominant bottleneck is not only “holding a bit longer”
   - it is the full layered problem of discovery -> hold -> peak recognition

The user has now explicitly confirmed the preferred decomposition:

1. identify most elite stocks
2. hold through noise after entry
3. recognize real peaks for exit

This design formalizes that decomposition and freezes further ad hoc threshold tuning until the framework is in place.

## 2. Problem Statement

The current workflow still mixes three different abilities into one moving target:

1. **Discovery ability**
   - can the model see future elite stocks early enough to matter?

2. **Hold ability**
   - once bought, can the model distinguish ordinary turbulence from true deterioration?

3. **Peak ability**
   - can the model recognize real terminal top structure instead of reacting to intermediate consolidation?

When these three abilities are tuned together through local thresholds, several failure modes appear:

- discovery failures are mistaken for hold failures
- hold failures are mistaken for peak failures
- local fixes improve one stock but degrade the whole system
- backtest summary moves without giving a stable explanation of why

This makes the model difficult to reason about and too unstable for reliable iterative improvement.

## 3. Design Goal

Build a layered, research-first framework that:

1. uses annual `Top100` only as the evaluation scorecard
2. uses rolling elite-stock segments as the research evidence set
3. separates discovery, hold, and peak into distinct pattern families
4. formalizes pattern evidence into explicit formulas
5. validates formulas in no-lookahead backtests before they affect live trading logic

The target is not “one perfect formula.”

The target is:

- a reusable elite-stock pattern library
- a stable layered research pipeline
- a formula bank that can be tested and promoted gradually

## 4. Guiding Principles

1. **No future leakage**
   - annual `Top100` may be used for scoring and post-hoc evaluation only
   - annual rank membership must never enter runtime decision logic

2. **Research set and scorecard must remain separate**
   - rolling elite segments are for learning patterns
   - annual `Top100` is for measuring business outcome

3. **Layer separation is mandatory**
   - discovery formulas must not silently encode hold logic
   - hold formulas must not silently encode terminal peak logic
   - peak formulas must require stronger evidence than noise filters

4. **Pattern first, threshold second**
   - thresholds may exist inside formulas
   - but they must be anchored to a named pattern and evidence class
   - not introduced as isolated tuning knobs

5. **All available data should be leveraged**
   - price structure
   - turnover and volume
   - sector behavior
   - market behavior
   - leadership / role semantics
   - practical trading constraints

6. **Validation must be dual-track**
   - scorecard quality improves
   - total return / drawdown profile remains practical

## 5. Approach Options

### Approach A: Top100-only annual winner study

- Build everything directly around annual `Top100`
- Learn entry/hold/exit behavior only from those names

Pros:
- simple to explain
- directly aligned with evaluation target

Cons:
- too tied to year-end hindsight
- weak for learning reusable pattern sequences
- not ideal for building non-lookahead runtime rules

### Approach B: Hybrid framework

- Use annual `Top100` as the scorecard
- Use rolling elite-stock segments as the research/training evidence set
- Build layered formulas from the segment library

Pros:
- preserves clean evaluation
- supports repeatable pattern mining
- avoids annual-rank overfitting
- best fit for no-lookahead formalization

Cons:
- more moving parts than a simple annual study
- requires an explicit segment-mining pipeline

### Approach C: Keep current architecture and continue local tuning

Pros:
- fastest short-term iteration

Cons:
- directly contradicted by recent evidence
- does not solve the structural mixing of discovery/hold/peak
- likely to produce more unstable local wins and broad regressions

## 6. Chosen Approach

Adopt **Approach B: Hybrid framework**.

This means:

- `Top100` becomes the outcome scorecard
- rolling elite-stock segments become the research dataset
- formula design is organized into discovery / hold / peak layers
- strategy iterations are judged by both:
  - annual elite-stock capture quality
  - multi-month backtest return quality

## 7. System Overview

The framework has six coordinated components.

### 7.1 Top100 Scorecard Builder

Purpose:
- produce a stable annual evaluation target

Inputs:
- stock database
- chosen year
- ranking limit, default `100`

Outputs:
- annual ranking JSON
- annual attribution JSON
- annual report markdown

Required metrics:
- `count`
- `picked_count`
- `bought_count`
- `held_to_top_count`
- reason buckets
- representative misses and premature exits

This component replaces the current optimization emphasis on `Top200` with a tighter `Top100` scorecard for precision.

### 7.2 Rolling Elite-Segment Miner

Purpose:
- build a reusable research set not tied to year-end hindsight

Definition:
- an elite segment is a major tradable upmove identified by rule-based segmentation over rolling history

Core output for each segment:
- segment start
- segment peak
- segment return
- drawdown pattern before peak
- volatility and turnover profile
- sector and market context
- major pivot structure

The miner should allow one stock to contribute more than one segment across long history, if they are separable by rule.

### 7.3 Pattern Label Library

Purpose:
- attach interpretable labels to elite segments

Label families:

1. **Discovery labels**
   - early leadership emergence
   - sector co-resonance
   - cross-sector breakaway
   - accumulation-before-expansion
   - institutional-quality trend emergence

2. **Hold labels**
   - benign pullback
   - deep-but-recoverable shakeout
   - sector churn without structural failure
   - market disturbance with relative strength retention
   - early profit validation with incomplete distribution

3. **Peak labels**
   - terminal acceleration
   - failed continuation after exhaustion
   - repeated distribution
   - sector collapse with leadership loss
   - market-wide terminal confirmation

Labels are research annotations only until promoted into formulas.

### 7.4 Formula Bank

Purpose:
- formalize pattern evidence into explicit, testable rule bundles

Formula categories:

1. **Discovery formulas**
   - generate ranked candidate opportunities
   - goal is high elite-stock coverage, not low false-positive rate alone

2. **Hold formulas**
   - classify pullback and disturbance regimes
   - goal is to delay premature exit without turning into indiscriminate holding

3. **Peak formulas**
   - require stronger multi-source evidence
   - goal is to detect real terminal conditions rather than transient weakness

Each formula must have:
- a name
- a layer
- required fields
- decision semantics
- audit output
- backtest eligibility

### 7.5 Shadow Evaluation Layer

Purpose:
- run candidate formulas in research mode before promoting them into formal execution

This layer should:
- record when a formula would trigger
- not change official strategy behavior initially
- compare formula triggers against actual elite-stock outcomes

This is required especially for hold and peak formulas, where premature promotion can damage total strategy return.

### 7.6 Official A/B Validation Layer

Purpose:
- promote only formulas that improve both scorecard and backtest quality

Validation dimensions:
- annual `Top100` scorecard
- 18-month total return
- max drawdown
- trade count
- sell reason distribution
- funnel conversion quality

## 8. Layer Definitions

### 8.1 Layer 1: Discovery

Question:
- did the model identify elite stocks early enough to matter?

This layer should answer:
- was the stock visible in seed scan?
- did it survive candidate generation?
- did it become a formal signal?
- was it actually bought?
- if not bought, why not?

Key metrics:
- seed coverage
- candidate coverage
- signal coverage
- picked count
- bought count
- picked-not-bought reasons

This layer is the first optimization priority.

### 8.2 Layer 2: Hold

Question:
- after entry, was the stock held through ordinary noise?

This layer should distinguish:
- routine pullback
- broad market disturbance
- sector churn
- true structural damage

Key metrics:
- hold duration relative to segment
- exit timing relative to segment pivots
- profit retention before exit
- post-exit remaining upside

This layer is the second optimization priority.

### 8.3 Layer 3: Peak

Question:
- was the exit aligned with a real peak rather than ordinary fluctuation?

This layer should require:
- stronger stock-level weakness
- meaningful sector deterioration
- or stronger market-level terminal evidence

Key metrics:
- held-to-top count
- top-aligned exits
- post-exit upside leakage
- false-terminal exits

This layer is optimized only after discovery quality and hold quality are separately measurable.

## 9. Data Requirements

The framework should leverage all currently available data already inside or adjacent to the model context:

- daily price series
- daily turnover / volume behavior
- market proxy state
- sector heat and deterioration state
- stock role semantics such as leader / middle force / follower
- signal timestamps and rankings
- trade records
- exit audit events
- practical execution constraints

No new external data source is required for the first implementation round.

## 10. Output Artifacts

### 10.1 Scorecard Outputs

- `top100_<year>_ranking.json`
- `top100_<year>_model_attribution.json`
- `top100_<year>_report.md`

### 10.2 Elite-Segment Outputs

- rolling elite-segment dataset JSON
- elite-segment summary markdown
- pattern label summary JSON

### 10.3 Formula Evaluation Outputs

- shadow trigger logs
- formula-level scorecard comparison
- formula bundle A/B summary

## 11. Success Criteria

The framework is successful only if it enables measurable progress on both fronts:

### 11.1 Scorecard Success

- `Top100 picked_count` improves materially
- `Top100 bought_count` improves materially
- `Top100 held_to_top_count` improves materially
- reason buckets become more concentrated and interpretable

### 11.2 Strategy Success

- 18-month total return improves over the current accepted baseline
- drawdown does not deteriorate beyond practical tolerance
- changes remain explainable by layer

### 11.3 Research Success

- discovery, hold, and peak errors can be diagnosed separately
- new formula proposals can be traced back to specific elite-stock evidence

## 12. Non-Goals

This design does **not** do the following:

- directly use annual `Top100` membership as a live signal
- claim that every elite stock must be captured
- replace all runtime logic in one step
- promise immediate return improvement from a single formula

## 13. Implementation Order

Phase 1:
- build `Top100` scorecard outputs alongside current attribution pipeline
- keep `Top200` outputs available during transition for comparison

Phase 2:
- build rolling elite-segment miner
- generate the first reusable elite-segment dataset

Phase 3:
- define pattern schema for discovery / hold / peak
- label representative elite segments

Phase 4:
- formalize first discovery formula bundle
- validate in shadow mode

Phase 5:
- formalize first hold formula bundle
- validate in shadow mode and A/B

Phase 6:
- formalize first peak formula bundle
- validate only after discovery and hold layers are independently measurable

## 14. Immediate Next Step

The immediate next step is:

- build the `Top100` scorecard pipeline and annual attribution outputs
- in parallel, build the rolling elite-segment research dataset

No further broad threshold tuning should proceed before these two foundations exist.
