# NeoTrade3 Independence Principle

## 1. Purpose

This document defines one explicit architectural rule for NeoTrade3:

- NeoTrade3 and NeoTrade2 are ultimately two completely independent systems
- this independence requirement takes effect immediately during NeoTrade3 construction

It exists to remove ambiguity from earlier transitional wording such as "read-shared first".

## 2. Final Agreement

The agreed rule is:

- NeoTrade3 must not depend on NeoTrade2 in any runtime aspect
- NeoTrade3 must not depend on NeoTrade2 databases
- NeoTrade3 must not depend on NeoTrade2 services, scripts, schedulers, configs, or filesystem outputs
- NeoTrade3 may reference NeoTrade2 code only as migration input and feature-analysis evidence

In short:

- NeoTrade2 can be a reference source
- NeoTrade2 cannot be an operating dependency

## 3. What Counts As Dependency

The following are considered forbidden dependencies for NeoTrade3:

- reading NeoTrade2 local databases at runtime
- calling NeoTrade2 HTTP endpoints or local services
- reusing NeoTrade2 cron or launchd jobs as upstream execution dependencies
- importing NeoTrade2 Python modules into NeoTrade3 runtime code
- reading NeoTrade2-generated files as required operational input
- keeping NeoTrade3 logic correct only because NeoTrade2 is still running

## 4. What Is Still Allowed

The following are still allowed because they are migration-analysis activities, not runtime dependency:

- reading NeoTrade2 code to extract feature inventory
- using NeoTrade2 as behavior reference for migration confirmation
- comparing NeoTrade3 outputs with NeoTrade2 outputs during verification
- documenting NeoTrade2 module ownership, data sources, and run logic

## 5. Practical Meaning For NeoTrade3

From this point forward, NeoTrade3 should be built under these execution assumptions:

- its own project root
- its own configuration system
- its own runtime entrypoints
- its own local database and artifact layout
- its own orchestration chain
- its own operational health checks

Any temporary shortcut that makes NeoTrade3 operationally depend on NeoTrade2 should be treated as architectural violation, not acceptable transition state.

## 6. Relationship With NeoTrade2

NeoTrade2 still has value, but only in these roles:

- migration reference
- regression comparison source
- historical rule and behavior evidence

NeoTrade2 is not part of NeoTrade3 runtime architecture.

## 7. Why This Rule Matters

The purpose of starting NeoTrade3 was not to keep extending NeoTrade2 by another name.

The purpose was to:

- redefine the system boundary
- establish a unified main chain
- migrate validated capabilities into a new architecture

If NeoTrade3 continues to rely on NeoTrade2 runtime assets, then the architectural boundary is not actually rebuilt.

## 8. Implementation Consequence

All future NeoTrade3 design and migration work should be checked against one question:

- if NeoTrade2 is completely shut down, can NeoTrade3 still run correctly on its own?

If the answer is no, the design is not yet compliant with the NeoTrade3 independence principle.
