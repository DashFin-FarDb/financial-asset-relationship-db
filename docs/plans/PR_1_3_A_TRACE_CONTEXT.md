### Async middleware usage (concrete example)

Below is a minimal FastAPI middleware implementation that demonstrates how to use
`async_request_context` and `async_trace_context` together to ensure request and
trace identifiers are installed for the lifetime of an HTTP request.

The full example is provided in `src/api/middleware/tracing_middleware.py`.

```python
# src/api/middleware/tracing_middleware.py
from uuid import uuid4
from starlette.middleware.base import BaseHTTPMiddleware

from src.observability.context import async_request_context, async_trace_context

class TracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        headers = request.headers
        request_id = headers.get("x-request-id") or f"req-{uuid4().hex}"
        correlation_id = headers.get("x-correlation-id") or f"corr-{uuid4().hex}"
        trace_id = headers.get("x-trace-id")
        span_id = headers.get("x-span-id")

        async with async_request_context(request_id, correlation_id):
            async with async_trace_context(trace_id, span_id):
                response = await call_next(request)
        return response
```

To enable the middleware in your FastAPI app:

```python
from fastapi import FastAPI
from src.api.middleware.tracing_middleware import TracingMiddleware

app = FastAPI()
app.add_middleware(TracingMiddleware)
```

This example:

- Generates stable request and correlation IDs when absent.
- Sets trace/span IDs when present (they are validated by the context helpers).
- Ensures both request and trace contexts are reset after the request completes.
