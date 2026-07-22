# Active-Boundary Drift And Placeholder Review Design

Date: 2026-07-02  
Scope: active-only drift review and remediation design for `apps/api`, `apps/worker`, `neotrade3`, active `scripts`, `neotrade3-dashboard/src`, `neotrade3-dashboard/server`, `config`, and `tests`

## 1. Background

Recent review and repair cycles have reduced several runtime-truth issues, but they also increased the risk of module drift:

- status semantics have been corrected in multiple layers
- worker, API, orchestration, lab runtime, lowfreq scripts, and frontend pages all now carry overlapping contract logic
- some active paths still expose placeholders, compatibility scaffolds, or stale field assumptions to users

The user has confirmed two non-negotiable constraints for this pass:

- review the active repository boundary only
- sort out all user-facing placeholders during this pass

This means the goal is not a repository-wide archival cleanup and not a raw coverage-percentage exercise. The goal is an evidence-backed active-boundary review that finds where logic has drifted due to repeated modifications, then removes or hard-bounds every user-facing placeholder in active code paths.

## 2. Design Goals

This pass must achieve the following:

- define a clear and correct boundary between active code and non-active code
- perform a deeper drift review across active truth surfaces, especially shared status and contract paths
- build a complete inventory of user-facing placeholders inside the active boundary
- classify each user-facing placeholder into one remediation mode:
  - replace with real implementation
  - convert to explicit hard error or unavailable state
  - remove from active UX or active runtime surface
- patch in controlled batches only after the deeper review is complete
- validate each batch with targeted regression evidence

This pass does not attempt:

- a false claim of perfect correctness
- elimination of every internal compatibility scaffold in the repo
- unrelated legacy/archive cleanup outside active-boundary leakage
- speculative feature expansion

## 3. Boundary Definition

### 3.1 Active Boundary

The following roots are treated as active for this pass:

- `apps/api`
- `apps/worker`
- `neotrade3`
- active top-level runtime file `lowfreq_engine_v16_advanced.py`
- active `scripts`
- `neotrade3-dashboard/src`
- `neotrade3-dashboard/server`
- `config`
- `tests`

### 3.2 Non-Active Boundary

The following paths are out of scope unless active code references them directly:

- `legacy/`
- `scripts/archive/`
- `docs/archive/`
- retired runtime carriers
- historical handover material

### 3.3 Boundary-Leak Rule

Any active module that depends on a non-active or non-runtime-owned artifact is treated as a review finding. This includes:

- active code reading historical or documentation-only carriers at runtime
- active code surfacing legacy compatibility fields as if they were current truth
- active UI or API flows that still depend on retired contract shapes

## 4. Placeholder Standard

### 4.1 What Counts As User-Facing

A placeholder is user-facing if it can be observed through any of the following:

- a live API endpoint
- frontend UI state, polling flow, or rendered field
- active worker/runtime output consumed by operators
- active report or artifact path intended for user or operator review

### 4.2 Allowed End States

A user-facing placeholder is acceptable only after it is transformed into one of these states:

- `real`: backed by actual runtime logic and truthful output
- `explicitly unavailable`: returns a clear hard error or explicit unsupported state without pretending to succeed
- `not surfaced`: removed from active UI/API/runtime exposure

### 4.3 Not Allowed

The following are explicitly disallowed after this pass:

- placeholder output presented with normal success semantics
- placeholder status collapsed into `ok`, `accepted`, or equivalent success language
- UI fields that appear live but are fed by narrowed or stale backend payloads
- compatibility fallbacks that silently override current canonical fields in user-visible outputs

## 5. Review Strategy

### 5.1 Review-Then-Patch Sequence

The approved execution mode for this work is `review then patch`.

The pass runs in this order:

1. complete the deeper active-boundary review
2. produce a prioritized remediation map
3. patch in controlled batches
4. validate each batch before moving to the next

This avoids making local fixes that introduce additional drift into shared status or contract layers.

### 5.2 Review Axes

The deeper review must cover these axes:

- active truth surfaces:
  - worker run result
  - orchestration task and run ledgers
  - API `_meta.status` and business status
  - lab runtime outputs
- shared contracts:
  - config registries
  - orchestration status vocabulary
  - lowfreq result and report schemas
  - frontend/backend state machines
- user-facing placeholders:
  - API placeholder endpoints or payload branches
  - UI placeholder rendering or polling assumptions
  - active script/report outputs that still use placeholder semantics
- active/non-active leaks:
  - runtime reads from docs-only or historical sources
  - legacy field fallbacks inside active user-visible outputs

### 5.3 Evidence Standard

Every finding must include:

- exact file evidence
- why the behavior is logically wrong
- whether it is a `truth drift`, `contract drift`, `placeholder leak`, or `boundary leak`
- whether it is user-facing

## 6. Remediation Strategy

### 6.1 Batch Order

Remediation proceeds in this order:

1. backend truth surfaces
2. user-facing API and lab placeholders
3. frontend contract drift and placeholder rendering
4. active script/reporting placeholders that leak into user-visible artifacts

### 6.2 Decision Rules Per Finding

Use these rules to decide how to sort out a placeholder:

- if real runtime logic already exists elsewhere for the same capability, align the user-facing path to the real implementation
- if no truthful implementation exists, replace the placeholder with an explicit unavailable or not-implemented error
- if the capability should not be live yet, remove it from active UI/API exposure instead of simulating success
- if the placeholder is only an internal compatibility carrier and does not leak to active truth surfaces, it can remain for now with a strict boundary note

### 6.3 Shared-Truth Protection

No remediation may introduce a new local status vocabulary or shadow contract when a canonical contract already exists. In particular:

- worker, orchestration, API, and lab surfaces must not diverge on what counts as `ok`, `failed`, `blocked`, `skipped`, or `pending_implementation`
- frontend termination and error handling must align to backend terminal states
- active reports must prefer canonical engine-owned fields over locally recomputed substitutes when those fields already exist

## 7. Initial Priority Findings Already Confirmed

The deeper pass starts with these already confirmed high-risk areas:

- worker CLI success fallback can mask failed or blocked execution
- API orchestration status semantics drift from shared orchestrator status vocabulary
- direct API lab runs still expose placeholder truth while worker/orchestration execute real lab logic
- stored snapshot reuse can ignore the current `publish_succeeded` request semantics
- active lab artifact contracts do not match actual persisted artifact locations or shapes
- active lowfreq reporting still contains legacy field fallback and local simulation logic
- frontend pages still carry stale assumptions in selected-date scoping, status handling, and narrowed backend fields

These are not the final list. They are the anchor set for the patch order.

## 8. Validation Strategy

Validation is required after each patch batch.

Required validation methods:

- targeted unit or integration regression around the changed truth surface
- endpoint or UI contract assertions for changed user-facing payloads
- status-semantics assertions where drift was previously observed
- artifact-path assertions where contracts and produced outputs were previously mismatched

Validation is considered sufficient only when:

- the new behavior is truthful
- the placeholder is removed, hard-bounded, or explicitly unavailable
- no downstream consumer still depends on the old misleading behavior

## 9. Success Criteria

This pass is successful when all of the following are true:

- active versus non-active boundary is explicit and evidence-backed
- no active user-facing path returns placeholder success as live truth
- shared truth surfaces no longer drift in status or contract semantics for the remediated areas
- frontend and active reports do not depend on stale placeholder assumptions for the remediated areas
- each remediation batch has concrete regression evidence

## 10. Implementation Handoff

The next phase should execute this design in controlled batches:

1. finish the deeper review inventory
2. finalize the prioritized remediation list
3. implement backend truth fixes first
4. remove or hard-bound user-facing placeholders
5. close frontend and active-report drift
6. validate each batch before continuing

This design intentionally keeps the boundary narrow, the evidence standard high, and the placeholder policy strict, so the repository does not drift further while being repaired.
