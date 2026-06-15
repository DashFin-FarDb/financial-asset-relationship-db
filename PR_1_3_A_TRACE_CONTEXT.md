# PR: Phase 1.3.a - Trace Context Model and Propagation

## Architectural Alignment

- **Backend**: FastAPI (production path)
- **Frontend**: Next.js (production path)
- **Gradio**: non-production (demo/testing only)

This PR implements thread-safe and async-safe trace context variables (`trace_id`, `span_id`, `parent_span_id`) inside `src/observability/context.py` using standard `contextvars.ContextVar`. These changes align with our structured logging and observability design, preparing the application for deep operational span tracing.

## Primary Objective

Establish trace context management variables (`trace_id`, `span_id`, `parent_span_id`) and helper primitives in a single, isolated, thread-safe, and async-safe file change to `src/observability/context.py`.

## Triage Data (Project Mandate)

- **Upstream Source**: Calls to context getters (`get_trace_id`, `get_span_id`, `get_parent_span_id`, and `get_request_context`) will be initiated by logging and middleware components. The callers assume these operations are $O(1)$ and thread/async safe.
- **Downstream Impact**: The return values are merged into logging payloads and event schemas. Adding these fields to `get_request_context` will automatically propagate them to all structured logs, but will not affect performance or cause memory leaks, as context variables are garbage collected when the request/task context terminates.
- **Failure Mode**: Since `ContextVar` operations are thread-safe and isolated to current asynchronous chains, failures in context mutation do not leak state across requests or threads. If invalid/missing IDs are set, they are returned as `None`, ensuring structured logging does not fail.

## Scope

### In Scope

- **Context Variables**: Defined `_trace_id_ctx`, `_span_id_ctx`, and `_parent_span_id_ctx` in `src/observability/context.py`.
- **Getters & Setters**: Implemented `get_trace_id()`, `get_span_id()`, `get_parent_span_id()`, `set_trace_context(trace_id, span_id, parent_span_id)`, and `reset_trace_context(tokens)`.
- **Structured Logging Hook**: Updated `get_request_context()` to include the new trace variables in the returned dictionary.

### Out of Scope

- **Middleware Refactoring**: Modifying `api/middleware/correlation.py` is deferred to a separate PR.
- **Startup & Rebuild Integration**: Instrumenting startup Lifespan or Reconciliation Engine loops with tracing spans is deferred.

### Files Expected to Change

- `src/observability/context.py`

## Validation Commands

```bash
# Verify existing context and correlation tests pass
pytest tests/unit/api/observability/test_context.py -v
pytest tests/unit/api/middleware/test_correlation.py -v
```

## Merge Criteria

- [x] Scope is tightly aligned to the Primary Objective
- [x] Validation commands pass locally or in CI
- [x] Changes align with production architecture (FastAPI + Next.js)

## Checklist

### Scope Compliance

- [x] This PR makes one primary decision only (Trace Context Model)
- [x] I have explicitly listed what is out of scope
- [x] I have verified the base branch is `main`
- [x] I have checked this PR against the production architecture

### Testing Best Practices

- [x] Tests verify observable behavior (isolation and retrieval)
- [x] Tests properly clean up resources (using finally blocks for resetting contexts)
