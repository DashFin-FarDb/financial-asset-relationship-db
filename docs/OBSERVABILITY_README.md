# Observability README

For the broader enterprise-readiness audit and rollout plan, see [docs/enterprise-readiness-index.md](./enterprise-readiness-index.md).

This short README links to the tracing middleware example, shows how to enable it in a FastAPI app, and details our key observability metrics and PromQL best practices.

## Tracing middleware example

A concrete implementation of the tracing middleware is provided at:

- `src/api/middleware/tracing_middleware.py`

It demonstrates how to use the async helpers exposed by `src.observability.context`:

- `async_request_context(request_id, correlation_id)`
- `async_trace_context(trace_id, span_id)`

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

  - `api/app_factory.py`
  - `tests/unit/test_app_factory.py`
  - `tests/unit/api/observability`

  Format: trace_id is the full `uuid4().hex` (32 lowercase hex chars); span_id is 16 lowercase hex characters (e.g. the first 16 chars of `uuid4().hex` for startup tracing, or `secrets.token_hex(8)` for the middleware).

## Key Metrics

We are currently tracking several observability metrics to monitor system health and performance:

- **Startup Durations**: Tracks the time taken during application initialization, broken down by subsystem (e.g., database connection, reconciliation, graph build).
- **Rebuild State Transitions**: Counts the transitions of our rebuild engine and data graphs, ensuring state loops execute smoothly and failures are quickly caught.
- **Lock Acquisition Counters**: Monitors the frequency and duration of lock acquisitions. High lock contention indicates potential starvation or concurrency bottlenecks.

## PromQL Best Practices

When querying these metrics in Prometheus, adhere to the following best practices to ensure optimal performance and accuracy:

- **Recording Rules for SLIs**: Use Recording Rules to precompute expensive queries (such as 30-day error budget burn rates or long-term aggregations). This ensures dashboards load quickly and alerting evaluation is efficient.
- **Rate over Gauge**: Prefer using `rate()` or `irate()` on counters (like lock acquisitions or state transitions) rather than relying purely on gauges, which can obscure short-lived spikes.
- **Label Cardinality**: Keep label cardinality low. Avoid putting unbounded values (e.g., full request paths or user IDs) into metric labels.
