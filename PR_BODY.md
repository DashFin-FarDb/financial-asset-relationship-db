### Primary Objective
Refactor `CorrelationMiddleware` to bridge incoming HTTP requests with the trace context engine established in Phase 1.3.a.

### In Scope
- Intercept incoming requests to extract `x-trace-id` and `x-span-id` tracing headers.
- Generate safe fallback identifiers if the headers are missing or invalid.
- Initialize the request execution boundary using `set_trace_context(trace_id, span_id, parent_span_id=None)` and attach IDs to `scope["state"]`.
- Ensure guaranteed context cleanup via `reset_trace_context` within a `finally` block to prevent leakage across async worker threads.
- Update downstream HTTP headers on outgoing responses.
- Resolves: ISSUE_1_3_B_MIDDLEWARE_REFACTOR.md

### Out of Scope
- Adding tracing to the startup lifespan or reconciliation engine (deferred to Phase 1.3.c).
- Integrating OpenTelemetry SDKs or heavy tracing dependencies.

### Files Expected to Change
- `src/api/middleware/correlation.py`
- `tests/unit/api/middleware/test_correlation.py`

### Validation Commands
- `pytest tests/unit/api/middleware/test_correlation.py`
- `make lint`
- `make test`

### Merge Criteria
- [x] All unit tests pass and test coverage remains unaffected.
- [x] Trace boundaries are cleanly propagated to response headers.
- [x] Unhandled exceptions safely bypass the context and cleanup logic executes.
