# NeoTrade3 Research Goal And Definitions (v1)

## 1. Purpose

This document captures the research objective and the core definitions that drove NeoTrade2's feature set, so NeoTrade3 can reorganize modules without losing capabilities.

It is a reference contract for migration and for future design discussions.

## 2. Final Objective

NeoTrade3's final objective is to mature a high-certainty quantitative model that supports medium-frequency and low-frequency trading.

The model must:

- identify trend segment entry points and exit points
- focus on forecasting upward trends with a forward horizon of at least 20–60 trading days (and potentially longer)
- aim for high certainty in decisions (typically 80%+)

This goal is not high-frequency trading research; intraday noise and micro-volatility are not the core optimization target.

## 3. Core Research Concept: Certainty

The system is built around the research of "certainty" as a primary concept.

- Certainty is established through research and iteration, not assumed by rules.
- The core work is to build a multi-dimensional, multi-layer certainty factor matrix.
- The factor matrix supports high-probability trend judgments and provides evidence for why a stock is selected or rejected.

## 4. Research Scope And Data Boundary

### 4.1 Maximum Universe

- Maximum data range is A-share stock data.
- Exclude:
  - index stocks (指数股)
  - BeiJiao exchange stocks (北交所)

### 4.2 Pool Types (Inputs)

The system uses multiple pool types, all rooted in the A-share universe:

1) Full A-share universe (after exclusions)
2) External pre-filtered pool derived from an external system
3) Team-provided pool derived from experience

## 5. Base Tooling: Screeners

Screeners are internally defined tools and are fundamental to the system.

They must support two roles simultaneously:

1) Factors: screeners can be used as components of the certainty factor matrix (on-demand).
2) Tools: the user must retain an entrypoint to run a screener independently when needed.

## 6. Two Primary Research Tracks Extracted From NeoTrade2

NeoTrade2 eventually extracted two major research methods into independent tracks:

### 6.1 Cup-Handle Experiment Track

- Every trading day, continuously screen directly from the A-share universe (after exclusions).
- Accumulate passing stocks into a pool over time.
- Track the pool and identify successful stocks.
- Extract common factors from successful cases to optimize the cup-handle screening logic.
- The track targets "self-evolution" by iterating on factor discovery and screening refinement.

### 6.2 Lao-Ya-Tou Five-Flags Track

- Current operational form: daily Lao-Ya-Tou pool provided by TongDaXin (通达信), filtered by its Lao-Ya-Tou shape definition.
- Research meaning: it is essentially a first-pass filter over the A-share universe by the Lao-Ya-Tou logic.
- Then the internal "Five-Flags" layer (five internal screeners) performs daily tracking and filtering inside that pool.
- Goal: identify stocks passing one or more of the five internal filters, as higher-certainty candidates for building positions.

The track targets "certainty amplification": start with a shape-defined pool (a form of certainty), then apply additional factor filters to increase certainty further.

## 7. Additional Strategy Inputs: Triple Screen / Turtle

- Triple Screen and Turtle are stock selection methods based primarily on trading indicators.
- Their stock pool is team-provided (selected from the A-share universe based on experience) and may be replaced over time.

This pool should be treated as an external input type distinct from internal screener discovery.

## 8. Automation And UI Rule

### 8.1 Automation Default

Daily actions must run automatically whenever possible:

- daily learning
- daily screening
- candidate evolution
- feedback processing

### 8.2 Two-Surface UI

UI should be deliberately minimal and show only two primary surfaces:

1) results users care about (candidates, conclusions, certainty summaries)
2) system operations metrics and maintenance entrypoints (inspection and repair)

## Appendix A. Module Taxonomy (Re-defined)

The following appendix includes the current module re-definition used to guide NeoTrade3 domain boundaries and migration mapping.

--- 

### A.1 Universe And External Inputs

Defines the research universe for a given date and the authoritative external inputs that modify it.

- supports externally provided pools that can change over time
- supports missing external inputs on some days, but requires strict validation and audit

Example: TDX Lao-Ya-Tou pool is an external universe source updated via file upload (not guaranteed daily).

### A.2 Data Control (Capture/Compose/Publish)

Provides validated and auditable datasets required by research and learning:

- capture: ingest raw snapshots (including external uploads)
- compose: build validated candidate datasets
- publish: commit approved datasets through strict quality gates

Data Control is a prerequisite for certainty research; it does not itself generate trading conclusions.

### A.3 Factor Engine (Screeners)

Screeners are factor producers:

- they may be used as independent tools (manual single run entry must remain available)
- they also contribute to the factor matrix as composable factor generators

This layer must provide explainable decision traces (why accepted/rejected) for audit and learning.

### A.4 Experiment Tracks (Research Lines)

Tracks are reusable research lines that orchestrate factor sets and stage conditions to produce candidate outputs.

Two primary tracks extracted from NeoTrade2:

- Cup-Handle Track: K-line shape-based trend prediction and factor discovery
- Five-Flags Track: external Lao-Ya-Tou pool + five internal screeners to amplify certainty inside a pre-filtered pool

Tracks do not own ad-hoc queues and scripts; those belong to orchestration.

### A.5 Learning And Calibration

Learning evaluates and calibrates certainty:

- measures trend segment recognition quality over the target horizon
- produces auditable calibration outputs and candidate evolution signals
- links evidence to decisions

### A.6 Orchestration And Ledger

Unifies execution and auditability:

- daily automatic runs for screening and learning
- controlled manual triggers (including independent screener run entry)
- immutable ledgers and reproducible artifacts as evidence

### A.7 Issue Center

Turns anomalies into traceable work items:

- data gaps, stale results, failed runs, drift
- links evidence and ownership for repair
