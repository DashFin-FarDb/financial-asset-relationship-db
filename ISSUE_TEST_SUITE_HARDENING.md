# Issue: Test Suite Hardening and Resource Safety

## Parent Roadmap

Related to Test Suite Integrity and CI Verification Gates.

## Objective

Strengthen assertions, prevent database engine/session resource leaks, ensure correct API contract test coverage, and verify edge cases across unit and integration tests.

## Requirements

1. **Density Recommendation Boundary Tests**:
   - Add explicit assertions at exactly 10% and 30% density thresholds in `tests/unit/test_schema_report_generator.py` to protect recommendations.
2. **Directed Edge Count Helper**:
   - Fix `tests/helpers/graph_scale_factory.py`'s `add_relationship()` call to pass separate arguments (`relationship_type`, `strength`) and disable bidirectional edge generation (`bidirectional=False`).
3. **Deprecated Field Absence Asserts**:
   - Add assertions verifying that the deprecated `relationship_density` field is absent from JSON payloads in `tests/unit/test_api_main.py` and `tests/unit/test_api_density_contract.py`.
4. **Density Range Assertion**:
   - Bound sample-data network density check in `tests/unit/test_sample_data.py` to `0 < density <= 1.0`.
5. **Rebuild Jobs Route Integration Coverage**:
   - Refactor `tests/integration/test_rebuild_job_list_contract.py` to query the `/api/graph/rebuild/jobs` endpoint using FastAPI's `TestClient` to verify router wiring, DI, and response serialisation.
6. **Typed Settings Enum Assert**:
   - Assert settings vercel environment resolves to `DeploymentEnvironment.PREVIEW` instead of a plain string in `tests/unit/test_settings.py`.
7. **Resource Safety in Persistence Tests**:
   - Wrap engine and session initialization in `tests/integration/test_graph_rebuild_persistence.py` using outer `try/finally` blocks and database context managers to prevent connection/handle leaks.

## Success Criteria

- All tests pass cleanly.
- No DB engines or sessions leak during pytest execution.
- Integration tests cover router endpoint paths.

## Status

**COMPLETED**
