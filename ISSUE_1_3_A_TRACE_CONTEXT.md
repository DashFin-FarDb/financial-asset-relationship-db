# Sub-Issue: Phase 1.3.a - Trace Context Model and Propagation

## Parent Roadmap

Related to Phase 1.3: Lifecycle Tracing (Observability Foundation Completion).

## Feature Description

### Is this feature request related to a problem? Please describe.

The FarDb FastAPI production backend currently lacks a distributed tracing context layer. While it implements correlation and request identifier context variables, it cannot track nested call hierarchy (spans), trace execution across asynchronous worker threads, or establish parent-child relationships for deep operational diagnostics.

To enable complete lifecycle tracing of long-running graph rebuilds, we must first establish the trace context primitives:

1. `trace_id` (representing the overall end-to-end execution path).
2. `span_id` (representing the current execution segment).
3. `parent_span_id` (representing the parent context, if nested).

### Describe the solution you'd like

Introduce thread-safe and async-safe context variables (`contextvars.ContextVar`) to manage `trace_id`, `span_id`, and `parent_span_id` in `src/observability/context.py`.

- Expose helper getters and setters.
- Integrate these fields into the existing `get_request_context()` structured log formatter interface to allow seamless structured log injection down the line.

### Describe alternatives you've considered

- **OpenTelemetry SDK**: Rejected for this baseline to keep the codebase simple and dependency-free, opting instead to reuse the existing `contextvars` pattern.
- **Thread Local Storage (`threading.local`)**: Rejected because thread-locals do not propagate across async boundaries (`async/await`), which is a core requirement of the FastAPI web server.

---

## Objective

Establish trace context management variables (`trace_id`, `span_id`, `parent_span_id`) and helper primitives in an isolated, thread-safe, and async-safe manner.

---

## Implementation Plan

### 1. Primitives Definition (`src/observability/context.py`)

- Define three new context variables:
  - `_trace_id_ctx: ContextVar[Optional[str]]`
  - `_span_id_ctx: ContextVar[Optional[str]]`
  - `_parent_span_id_ctx: ContextVar[Optional[str]]`

### 2. Context Helper Methods (`src/observability/context.py`)

- Implement the following helpers:
  - `get_trace_id() -> Optional[str]`
  - `get_span_id() -> Optional[str]`
  - `get_parent_span_id() -> Optional[str]`
  - `set_trace_context(trace_id, span_id, parent_span_id) -> tuple[Token, Token, Token]`
  - `reset_trace_context(tokens) -> None`

### 3. Log Ingestion Interface Update (`src/observability/context.py`)

- Update `get_request_context() -> dict[str, Optional[str]]` to return a dictionary containing:
  - `request_id`
  - `correlation_id`
  - `trace_id`
  - `span_id`
  - `parent_span_id`

---

## Success Criteria

1. **Async Context Isolation**: Setting a trace context in one async task must not bleed into or modify the context of a concurrent async task.
2. **Backward Compatibility**: Existing functions `get_request_id()`, `get_correlation_id()`, and `get_request_context()` must remain fully functional and preserve their current behaviors.
3. **Validation Pass**: Existing test suites run and pass without regressions.
