# Runtime Modes

This document defines how FarDb determines its data source and fallback behavior at runtime.

## Core variables

### DATA_MODE

Controls the primary data source for graph construction.

Allowed values:

- `sample` — use synthetic/sample data only
- `cache` — load graph from persisted cache
- `live` — fetch real data and build graph dynamically

### DATA_FALLBACK_POLICY

Controls what happens when the primary mode fails.

Allowed values:

- `fail` — application startup fails
- `cache` — fallback to cached graph
- `sample` — fallback to sample data

## Mode definitions

### sample

- deterministic
- no external dependencies
- suitable for local development and testing
- not suitable for production

### cache

- uses previously computed graph data
- stable and reproducible
- preferred for staging and many production scenarios

### live

- fetches data from external sources
- most accurate but also most failure-prone
- should be paired with a deliberate fallback policy

## Recommended defaults

### development

```
DATA_MODE=sample
DATA_FALLBACK_POLICY=sample
```

### staging

```
DATA_MODE=cache
DATA_FALLBACK_POLICY=fail
```

### production

Option A (stable):
```
DATA_MODE=cache
DATA_FALLBACK_POLICY=fail
```

Option B (live-first):
```
DATA_MODE=live
DATA_FALLBACK_POLICY=cache
```

## Design principle

A production system must not silently degrade to sample data unless explicitly configured.

If fallback occurs, it must be:

- intentional
- observable (logged and exposed via status endpoints)
- consistent with the declared policy

## Observability

At startup and during runtime, the system should expose:

- active DATA_MODE
- active data source (sample/cache/live)
- fallback events

## Relationship to layout

Data mode affects graph construction only.

Layout generation consumes the graph but must not influence the selection of data mode or graph source.
