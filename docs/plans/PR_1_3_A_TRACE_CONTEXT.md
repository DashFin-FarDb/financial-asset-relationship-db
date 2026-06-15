# PR 1.3.a - Trace Context Model and Propagation (PR 1)

## Status: PLANNING

## Context & Problem Statement

_(Derived from the Feature Request Issue Template)_

**Problem:**
The FarDb production backend (FastAPI) lacks a structured tracing context propagation layer. While it supports basic `request_id` and `correlation_id` propagation, it cannot track sub-operation lifetimes (spans) or parent-child relationships across asynchronous or thread boundaries. To implement Phase 1.3: Lifecycle Tracing, the system requires tracing context primitives (`trace_id`, `span_id`, and `parent_span_id`) that are safely managed and propagated across execution threads and asynchronous tasks.

**Solution:**
Introduce thread-safe and async-safe context variables (`contextvars.ContextVar`) to store `trace_id`, `span_id`, and `parent_span_id` within the `src/observability/context.py` module. Provide safe getter/setter functions and update `get_request_context()` to include the new fields.

**Alternatives Considered:**

1. _OpenTelemetry SDK_: Using a full OpenTelemetry integration was considered but rejected for this baseline to minimize dependencies and complexity, preferring lightweight `contextvars` that align with our custom structured logging and event schemas.
2. _Dict-based thread-local storage_: Thread-locals do not automatically propagate across asynchronous tasks (`async/await`), whereas `contextvars` natively support async boundaries in Python.

---

## Architectural Alignment

- **Backend**: FastAPI (production path)
- **Scope**: Modifies `src/observability/context.py` (production path)
- **Gradio / Frontend**: No impact (strictly backend context propagation primitives)

## Primary Objective

Establish the foundational context management variables and helper functions for tracing (`trace_id`, `span_id`, `parent_span_id`) in a single, isolated file change to `src/observability/context.py`.

---

## Scope

### In Scope

1. **Trace Context Variables**:
   - Define `_trace_id_ctx: ContextVar[Optional[str]]`
   - Define `_span_id_ctx: ContextVar[Optional[str]]`
   - Define `_parent_span_id_ctx: ContextVar[Optional[str]]`
2. **Context Helpers**:
   - Implement `get_trace_id() -> Optional[str]`
   - Implement `get_span_id() -> Optional[str]`
   - Implement `get_parent_span_id() -> Optional[str]`
   - Implement `set_trace_context(trace_id: Optional[str], span_id: Optional[str], parent_span_id: Optional[str]) -> tuple[Token[Optional[str]], Token[Optional[str]], Token[Optional[str]]]`
   - Implement `reset_trace_context(tokens: tuple[Token[Optional[str]], Token[Optional[str]], Token[Optional[str]]]) -> None`
3. **Structured Logging Integration**:
   - Update `get_request_context()` to return a dictionary including `trace_id`, `span_id`, and `parent_span_id`.

### Out of Scope

1. **Middleware Refactoring**: Modifying `api/middleware/correlation.py` to extract headers from HTTP requests is deferred to a separate, sequential PR.
2. **Startup & Rebuild Integration**: Instrumenting startup lifecycle and background tasks with tracing spans is deferred to separate PRs.
3. **Unit Test Changes**: Unit testing for trace context primitives, log integration, and async isolation are explicitly included in this PR.

### Files Expected to Change

- [`src/observability/context.py`](../../src/observability/context.py) — Establish context variables, getters, setters, and update context getter dict.

---

## PR Triage & Description Standards

_(Required by GEMINI.md global rules)_

- **Upstream Source**: Calls to context getters (`get_trace_id`, `get_span_id`, `get_parent_span_id`, and `get_request_context`) will be initiated by the logging setup (`src/observability/logging.py`) and future tracing middleware. The callers assume these operations are lightweight, thread-safe, and execute with $O(1)$ complexity.
- **Downstream Impact**: The return values are merged into logging payloads and event schemas. Adding these fields to `get_request_context` will automatically propagate them to all structured logs, but will not affect performance or cause memory leaks, as context variables are garbage collected when the request/task context terminates.
- **Failure Mode**: Since `ContextVar` operations are thread-safe and isolated to current asynchronous chains, failures in context mutation do not leak state across requests or threads. If invalid/missing IDs are set, they are returned as `None`, ensuring structured logging does not fail.

---

## Proposed Changes

### [`src/observability/context.py`](file:///home/mo/projects/financial-asset-relationship-db/src/observability/context.py)

```python
# Context variables for trace identifiers
# trace_id: Root identifier for a distributed trace
# span_id: Identifier for the current trace segment
# parent_span_id: Parent span identifier (if nested)
_trace_id_ctx: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
_span_id_ctx: ContextVar[Optional[str]] = ContextVar("span_id", default=None)
_parent_span_id_ctx: ContextVar[Optional[str]] = ContextVar("parent_span_id", default=None)
```

And expose getters, setters, and reset helpers:

```python
def get_trace_id() -> Optional[str]:
    """Return the current trace ID from context."""
    return _trace_id_ctx.get()


def get_span_id() -> Optional[str]:
    """Return the current span ID from context."""
    return _span_id_ctx.get()


def get_parent_span_id() -> Optional[str]:
    """Return the current parent span ID from context."""
    return _parent_span_id_ctx.get()


def set_trace_context(
    trace_id: Optional[str],
    span_id: Optional[str],
    parent_span_id: Optional[str] = None,
) -> tuple[Token[Optional[str]], Token[Optional[str]], Token[Optional[str]]]:
    """
    Set the trace context variables.

    Returns:
        A tuple of tokens that can be used to reset the context variables.
    """
    t1 = _trace_id_ctx.set(trace_id)
    t2 = _span_id_ctx.set(span_id)
    t3 = _parent_span_id_ctx.set(parent_span_id)
    return t1, t2, t3


def reset_trace_context(
    tokens: tuple[Token[Optional[str]], Token[Optional[str]], Token[Optional[str]]]
) -> None:
    """
    Reset the trace context variables using the provided tokens.

    Args:
        tokens: The tokens returned by set_trace_context.
    """
    t1, t2, t3 = tokens
    _trace_id_ctx.reset(t1)
    _span_id_ctx.reset(t2)
    _parent_span_id_ctx.reset(t3)

@contextlib.contextmanager
def trace_context(trace_id: Optional[str], span_id: Optional[str], parent_span_id: Optional[str] = None):
    tokens = set_trace_context(trace_id, span_id, parent_span_id)
    try:
        yield
    finally:
        reset_trace_context(tokens)
```

**Middleware Usage Example:**
```python
from src.observability.context import trace_context

@app.middleware("http")
async def add_tracing_middleware(request: Request, call_next):
    # Extract trace IDs from headers or generate new ones
    trace_id = request.headers.get("x-b3-traceid") or generate_id()
    span_id = request.headers.get("x-b3-spanid") or generate_id()

    # Use context manager for robust lifecycle management
    with trace_context(trace_id, span_id):
        response = await call_next(request)
        return response
```

Update `get_request_context()` to return these fields:

```python
def get_request_context() -> dict[str, Optional[str]]:
    """
    Return a dictionary of the current request metadata.

    Useful for structured logging to ensure all log entries within a request
    contain the necessary identifiers.
    """
    return {
        "request_id": get_request_id(),
        "correlation_id": get_correlation_id(),
        "trace_id": get_trace_id(),
        "span_id": get_span_id(),
        "parent_span_id": get_parent_span_id(),
    }
```

---

## Verification Plan

### Automated Tests

Run the existing test suites to confirm no regressions are introduced:

```bash
pytest tests/unit/api/observability/test_context.py -v
pytest tests/unit/api/middleware/test_correlation.py -v
```

### Manual Verification

Write a temporary scratch verification script in the artifacts directory (`scratch/verify_tracing_context.py`) that sets the context variables, validates getters, and resets the context.
Run this script:

```bash
python scratch/verify_tracing_context.py
```

---

## Architectural Constraints

### Must Preserve

- **Thread & Async Safety**: Always use `contextvars` to manage context across asynchronous task boundaries.
- **Backward Compatibility**: `get_request_context()` must continue to return the dictionary containing `request_id` and `correlation_id` keys intact.

### Must Not Introduce

- **Global Mutators**: Avoid using global dictionaries or raw thread-locals that can bleed request boundaries in high-concurrency event loops.
- **Heavy Callbacks**: Keep context setters/getters free of heavy logic or external database lookups.

---

## Risk Assessment

- **Low Risk**: Introducing context variables has no runtime impact on existing flows, as long as they default to `None` and the dictionary returned by `get_request_context` contains all legacy keys.

## Success Metrics

- 100% of existing tests pass.
- Verification script successfully exercises async-safe trace context propagation.
