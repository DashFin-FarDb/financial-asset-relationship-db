# Issue: Security, Locks, and Gate Boundaries

## Parent Roadmap

Related to Stage 5C Safety Constraints and Enterprise Promotion Gates.

## Objective

Strengthen lock validation boundaries during resets, enforce the deterministic 30-second lock reacquisition ceiling, expand sensitive metadata sanitization in audit logs, and encode pagination constraints directly in the Pydantic schema models.

## Requirements

1. **Lock Verification at reset Mutation Boundary**:
   - Update `src/logic/recovery_gate.py` to check `self.lock.check_state() != LockState.VALID` immediately before job failure state changes and database commits in `_reset_active_job()`.
2. **Deterministic 30s Lock Reacquisition ceiling**:
   - Implement an elapsed-time/deadline constraint in `src/logic/recovery_gate.py`'s lock acquisition loops to guarantee it throws `LockAcquisitionTimeout` within 30 seconds.
3. **Broadened Sensitive Key Matcher**:
   - Expand `api/auth.py`'s `_is_sensitive_metadata_key` to check for common credential substrings (`token`, `secret`, `passwd`, `password`, `passwd`, `pwd`, `authorization`, `apikey`) except for safe categories (e.g. `tokentype`).
4. **Authoritative Audit Log Fields**:
   - Restructure log metadata merging in `api/auth.py`'s `_log_security_event` to prevent arbitrary user-provided payloads from overriding canonical context fields (`request_id`, `username`, etc.).
5. **Pagination Boundary Validation**:
   - Encode bounds in `api/api_models.py`'s `MetricsResponse` pagination fields (`total >= 0`, `page >= 1`, `1 <= per_page <= 1000`) using Pydantic `Field` validation.
6. **Metrics HTTPException Propagation**:
   - Ensure `api/routers/metrics.py` propagates `HTTPException` instances without swallowing them into a generic `500 Server Error` response.

## Success Criteria

- Lock-loss during job reset raises `ExecutionBlockedError` and prevents DB commits.
- Lock acquisition times out in exactly 30s.
- Sensitive credentials do not leak to logging streams.
- Invalid pagination requests are rejected by schema validators.

## Status

**COMPLETED**
