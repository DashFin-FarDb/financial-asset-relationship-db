# Sub-Issue: Phase 1.3.b - Middleware Refactoring

## Parent Roadmap

Related to Phase 1.3: Lifecycle Tracing (Observability Foundation Completion). This follows the successful completion of Phase 1.3.a (Trace Context Model and Propagation).

## Feature Description

### Is this feature request related to a problem? Please describe.

With the trace context primitives (`trace_id`, `span_id`, `parent_span_id`) established in `src/observability/context.py` (via PR #1264), the application is capable of propagating context in async/thread environments. However, incoming HTTP requests to the FastAPI backend currently do not extract trace boundaries from headers or apply them to this newly established context.

As a result, API requests lack external traceability and nested span generation, breaking distributed tracing continuity.

### Describe the solution you'd like

Update the existing observability middleware (e.g., `api/middleware/tracing_middleware.py` or equivalent API integration seam) to bridge incoming HTTP requests with the new trace context engine.

1. Intercept incoming requests and extract standard tracing headers (e.g., `x-trace-id`, `x-span-id`, `traceparent`).
2. Generate a new `trace_id` and `span_id` if no external identifiers are provided.
3. Validate and sanitize extracted IDs.
4. Call `set_trace_context(trace_id, span_id, parent_span_id)` to initialize the request's execution boundary before yielding to route handlers.
5. Ensure `reset_trace_context` is guaranteed to be called in a `finally` block or context manager after the response is returned to avoid context leakage.

### Describe alternatives you've considered

- **Ad-hoc Header Parsing in Routers**: Rejected because it violates DRY principles and risks missing endpoints. Middleware guarantees all incoming traffic is formally bound to a trace context.

---

## Objective

Ensure all incoming HTTP traffic flowing through the FastAPI application is deterministically bound to an async-safe trace context, either continuing an external trace or originating a new one, without leaking state between concurrent requests.

---

## Implementation Plan

### 1. Middleware Update
- Locate the main API middleware responsible for request correlation.
- Update its `dispatch` or equivalent lifecycle method to parse external trace headers.
- Utilize the helper functions from `src/observability/context.py` to establish the trace context.

### 2. Header Response Injection (Optional but Recommended)
- Inject the active `trace_id` and `span_id` into the outgoing HTTP response headers (e.g., `x-trace-id`) to allow clients to track request execution on their side.

### 3. Cleanup Guarantee
- Enforce the absolute disposal pathway: ensure the context variables are cleanly reset regardless of whether the HTTP route succeeds or raises an unhandled exception.

---

## Success Criteria

1. **Deterministic Propagation**: Every API request automatically receives a trace context.
2. **External Tracing**: If a request supplies valid trace headers, the application adopts them rather than originating a new trace.
3. **No Leakage**: The context is perfectly reset after the request concludes, preventing bleeding into subsequent requests on the same async worker.
4. **Validation Pass**: All existing test suites pass without regression, and new unit tests assert middleware trace continuity.
