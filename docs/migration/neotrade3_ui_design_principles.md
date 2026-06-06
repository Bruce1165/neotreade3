# NeoTrade3 UI Design Principles

## 1. Purpose

This document defines the front-end and UI design rules for NeoTrade3.

It exists to make one point explicit:

- NeoTrade3 UI must not copy NeoTrade2 UI
- NeoTrade3 UI must serve NeoTrade3 architecture, research workflow, and operating model

## 2. Final Rule

NeoTrade3 front-end design must satisfy all of the following:

- independent visual and interaction design
- intuitive information structure
- easy-to-understand presentation
- result-oriented workflow
- maximum automation for experiment execution
- support for adding new experiments at any time

In short:

- UI is not a clone of NeoTrade2
- UI is an operating and research interface for NeoTrade3

## 3. What Must Be Avoided

The following are explicitly discouraged:

- copying NeoTrade2 page structure, tab structure, or information grouping
- carrying over old UI logic only because users are familiar with it
- exposing large raw payloads as the primary reading mode
- making users manually stitch together experiment input, status, result, and next action
- hardcoding front-end around a fixed small set of experiments
- adding one-off experiment pages that do not fit a reusable system

## 4. Core Design Targets

### 4.1 Intuitive

NeoTrade3 pages should answer these questions immediately:

- what is happening now
- what needs attention now
- what failed or is blocked
- what should be done next

Important status, conclusion, and action should appear before implementation detail.

### 4.2 Easy To Understand

Information should be grouped by user task and decision flow, not by historical code structure.

A reader should not need to understand backend module boundaries before understanding the page.

### 4.3 Result-Oriented

UI should emphasize:

- conclusions
- experiment outcomes
- quality gates
- risk and anomaly signals
- recommended next actions

UI should de-emphasize:

- incidental implementation detail
- low-value internal noise
- raw intermediate data as the default view

### 4.4 Experiment Automation

Experiments should appear in the system as managed operating units, not scattered custom pages.

The UI direction should support:

- experiment registration
- experiment readiness checks
- experiment triggering
- run status tracking
- result summarization
- issue aggregation
- learning feedback

### 4.6 Two-Surface UI Rule

NeoTrade3 UI should be deliberately minimal, with only two primary surfaces:

- user-facing results and conclusions
- system operations metrics and maintenance entrypoints (for inspection and repair)

Everything else (raw payloads, internal ledgers, debug traces) remains accessible only as a lower-priority maintenance layer.

This rule exists to keep the front-end clean, direct, and decision-oriented.

### 4.5 Continuous Extensibility

Adding a new experiment should primarily mean:

- registering a new experiment contract
- providing its metadata and runtime hooks
- plugging it into shared UI containers and workflows

It should not require rebuilding the front-end structure from scratch.

## 5. Recommended UI Organization

NeoTrade3 UI should move toward these layers:

- system overview
  - current system state, major alerts, current decision focus
- orchestration view
  - run chain, blocking state, readiness, execution status
- experiment hub
  - experiment catalog, registration metadata, current runs, results, comparison
- issue and learning center
  - problem pool, recurring failures, review queue, follow-up actions
- configuration and contract health
  - config validity, experiment contract integrity, data/control readiness

This organization is closer to NeoTrade3's operating-system role than a legacy dashboard menu.

## 6. Default Presentation Rules

Unless there is a strong reason otherwise, UI should follow this display priority:

1. summary and conclusion
2. current status and next action
3. important metrics and trend indicators
4. drill-down details
5. raw payload and debug material

Raw JSON can remain available, but only as a lower-priority debug layer.

## 6.1 Automation Default

Unless a workflow explicitly requires human intervention, the system should automatically execute:

- daily learning
- daily screening
- candidate evolution
- feedback processing

UI should focus on the outputs and on actionable maintenance signals, not on exposing every intermediate step.

## 7. Implications For Labs And Experiments

Labs should not be treated as isolated special pages forever.

The UI should eventually treat each lab or experiment through a common model:

- identity
- purpose
- data dependencies
- readiness state
- trigger mode
- execution history
- result summary
- issue summary
- learning feedback

That is the UI basis required to support "add new experiments at any time".

## 8. Review Question

Any future NeoTrade3 UI work should be checked against this question:

- does this design make NeoTrade3 more understandable, more action-oriented, more automated, and easier to extend with new experiments?

If the answer is no, the design is not aligned with NeoTrade3 UI principles.
