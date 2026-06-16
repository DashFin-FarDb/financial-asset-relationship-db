# Observability README

This short README links to the tracing middleware example and shows how to enable it in a FastAPI app.

## Tracing middleware example

A concrete implementation of the tracing middleware is provided at:

- `src/api/middleware/tracing_middleware.py`

It demonstrates how to use the async helpers exposed by `src.observability.context`:

- async_request_context(request_id, correlation_id)
- async_trace_context(trace_id, span_id)

## Quickstart

To enable the middleware in your FastAPI application:

```python
from fastapi import FastAPI
from src.api.middleware.tracing_middleware import TracingMiddleware

app = FastAPI()
app.add_middleware(TracingMiddleware)
```

This will automatically install request and trace contexts for every incoming request. The middleware will:

- Respect `x-request-id` and `x-correlation-id` headers when present; otherwise generate stable IDs.
- Respect `x-trace-id` and `x-span-id` headers when present; invalid values are dropped.
- Ensure contexts are reset after the request completes.

- Startup tracing: the application lifespan creates and applies a startup trace context (trace_id/span_id) during state initialization so observability events emitted during startup (reconciliation, get_graph, etc.) carry the same trace identifiers. For implementation details and tests, see:

  - api/app_factory.py: https://github.com/DashFin-FarDb/financial-asset-relationship-db/blob/docs/trace-startup-note/api/app_factory.py
  - tests/unit/test_app_factory.py: https://github.com/DashFin-FarDb/financial-asset-relationship-db/blob/docs/trace-startup-note/tests/unit/test_app_factory.py
  - tests/unit/api/observability: https://github.com/DashFin-FarDb/financial-asset-relationship-db/tree/docs/trace-startup-note/tests/unit/api/observability

  Format: trace_id is the full `uuid4().hex` (32 lowercase hex chars); span_id is the first 16 hex characters of `uuid4().hex` (16 lowercase hex chars).
