# Issue: Documentation and Templates Alignment

## Parent Roadmap

Related to Enterprise Readiness Release Checklist and the Operational Evidence Capture Framework.

## Objective

Align all repository documentation, issue templates, and specifications with the canonical field names, status legends, and fixed-TTL constraints.

## Requirements

1. **Tech Spec Metrics Normalisation**:
   - Update `docs/tech_spec.md` and `tech_spec.md` to ensure "Total Assets" and "Average Degree" metrics are defined consistently and do not conflict.
2. **Roadmap Legend Correction**:
   - Update `docs/roadmap/enterprise-readiness-roadmap.md` line 46 to use `Satisfied - automated` instead of `Satisfied`.
3. **Runbook TTL Clarification**:
   - Update `docs/runbooks/backup-restore-dr.md` to remove references to `REBUILD_LOCK_TTL_SECONDS` changing the lock wait window, cementing the 300s fixed TTL ceiling.
4. **Issue Templates Persistent Keys Alignment**:
   - Update `.github/ISSUE_TEMPLATE/operational_drill_evidence.md`, `.github/ISSUE_TEMPLATE/release_candidate_evidence.md`, and `.github/ISSUE_TEMPLATE/restore_rehearsal_evidence.md` to replace top-level references with `graph_persistence_configured` while preserving nested `graph.persistence_enabled` where it validates the graph object structure.
5. **PR Body Refresh**:
   - Update `pr_body.md` to describe the correct scope of this branch (fixing documentation, security boundaries, and test edge cases) instead of legacy Gitlink/graph density renames.

## Success Criteria

- Pre-commit checks pass on all modified files.
- No references to the outdated `graph.persistence_enabled` key remain in issue templates.
- All documentation files accurately reflect repository architectural constraints.

## Status

**COMPLETED**
