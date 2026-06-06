# NeoTrade3 Research Model And Module Taxonomy (v1)

## 1. Purpose

This document re-defines the conceptual modules derived from NeoTrade2, aligned with NeoTrade3's final objective:

- build a high-certainty (80%+) medium/low-frequency quantitative model
- identify trend segment entry and exit points with a forward horizon of 20–60+ trading days
- continuously research and calibrate certainty via an extensible factor matrix

It exists to reduce cross-module ambiguity before deeper migration and implementation work.

## 2. Scope Constraints

- Research scope is A-share stock data and excludes:
  - index stocks (指数股)
  - BeiJiao exchange stocks (北交所)
- NeoTrade3 remains runtime-independent from NeoTrade2 (no shared database, services, or artifacts).
- Daily workflows (learning/screening/evolution/feedback processing) must run automatically unless explicitly gated.
- UI should remain minimal: results + operations metrics with maintenance entrypoints.

## 3. Core Concepts

### 3.1 Certainty

Certainty is the system's measurable confidence that a stock is entering or exiting a trend segment that will materialize over a 20–60+ day horizon.

### 3.2 Trend Segment Recognition (Primary Evaluation Objective)

Primary evaluation is trend segment recognition:

- identify entry point and exit point
- optimize for price delta between entry and exit, rather than intraday noise behavior

Volatility inside the segment is not treated as the primary objective (unlike high-frequency research).

### 3.3 Factor Matrix

A factor matrix is the extensible representation of multi-dimensional and multi-layer certainty factors.

- screeners contribute factors and decision traces
- tracks compose factor sets and stage conditions
- learning evaluates and calibrates the mapping from factors to certainty

## 4. Module Taxonomy (Re-defined)

This taxonomy is conceptual. It guides NeoTrade3 domain boundaries and migration mapping decisions.

### 4.1 Universe And External Inputs

Defines the research universe for a given date and the authoritative external inputs that modify it.

- supports externally provided pools that can change over time
- supports missing external inputs on some days, but requires strict validation and audit

Example: TDX Lao-Ya-Tou pool is an external universe source updated via file upload (not guaranteed daily).

### 4.2 Data Control (Capture/Compose/Publish)

Provides validated and auditable datasets required by research and learning:

- capture: ingest raw snapshots (including external uploads)
- compose: build validated candidate datasets
- publish: commit approved datasets through strict quality gates

Data Control is a prerequisite for certainty research; it does not itself generate trading conclusions.

### 4.3 Factor Engine (Screeners)

Screeners are factor producers:

- they may be used as independent tools (manual single run entry must remain available)
- they also contribute to the factor matrix as composable factor generators

This layer must provide explainable decision traces (why accepted/rejected) for audit and learning.

### 4.4 Experiment Tracks (Research Lines)

Tracks are reusable research lines that orchestrate factor sets and stage conditions to produce candidate outputs.

Two primary tracks extracted from NeoTrade2:

- Cup-Handle Track: K-line shape-based trend prediction and factor discovery
- Five-Flags Track: external Lao-Ya-Tou pool + five internal screeners to amplify certainty inside a pre-filtered pool

Tracks do not own ad-hoc queues and scripts; those belong to orchestration.

### 4.5 Learning And Calibration

Learning evaluates and calibrates certainty:

- measures trend segment recognition quality over the target horizon
- produces auditable calibration outputs and candidate evolution signals
- links evidence to decisions

### 4.6 Orchestration And Ledger

Unifies execution and auditability:

- daily automatic runs for screening and learning
- controlled manual triggers (including independent screener run entry)
- immutable ledgers and reproducible artifacts as evidence

### 4.7 Issue Center

Turns anomalies into traceable work items:

- data gaps, stale results, failed runs, drift
- links evidence and ownership for repair

## 5. UI Boundary Rule

UI should remain clean and direct:

- surface 1: user-facing results (candidate lists, certainty summaries, trend-segment decisions)
- surface 2: operations metrics and maintenance entrypoints (health, drift, failures, repair actions)

Raw payloads and debug material remain a maintenance drill-down, not the primary reading mode.

## 6. Migration Implications (Immediate)

- Screeners mapping must preserve manual entrypoints while treating screeners as factor contributors.
- Five-Flags pool input must be modeled as an external universe source (file upload), validated before use.
- Learning should prioritize trend segment recognition metrics aligned with entry/exit price delta.
