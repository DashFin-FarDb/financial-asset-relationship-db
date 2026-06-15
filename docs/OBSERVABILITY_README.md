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
