"""Contract tests for ADR 0007 / H-P0-04 operator closure setup path."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNBOOK = REPO_ROOT / "docs" / "runbooks" / "database-authorization-closure.md"
RESTRICTED = REPO_ROOT / "docs" / "evidence-records" / "templates" / "db-authz-restricted-closure.md"
PUBLIC = REPO_ROOT / "docs" / "evidence-records" / "templates" / "db-authz-public-redacted-pass.md"
ISSUE_TEMPLATE = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "database_authorization_closure.md"
RC_EVIDENCE = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "release_candidate_evidence.md"
STAGING_BASELINE = REPO_ROOT / "docs" / "staging-deployment-operating-baseline.md"
CONTINUITY = REPO_ROOT / "docs" / "strategy" / "fardb-project-continuity.md"
ADR_0007 = REPO_ROOT / "docs" / "adr" / "0007-database-authorization-boundary.md"
EVIDENCE_PACK = REPO_ROOT / "docs" / "release-evidence-pack.md"
PR_BOARD = REPO_ROOT / "docs" / "roadmap" / "enterprise-readiness-pr-board.md"
ENTERPRISE_INDEX = REPO_ROOT / "docs" / "enterprise-readiness-index.md"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
EVIDENCE_RECORD = REPO_ROOT / "docs" / "evidence-records" / "hp004-db-authz-pass-29991d03.md"


def _markdown_row_with_cell(text: str, value: str) -> str:
    """Return the first markdown table row with a cell exactly equal to ``value``."""
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if value in cells:
            return line
    raise AssertionError(f"no markdown table row with cell {value!r}")


def _roadmap_status_row(text: str, status: str) -> str:
    """Return the row for ``status`` from the roadmap status table."""
    section = text.split("## Roadmap Status Snapshot", 1)[1].split("\n## ", 1)[0]
    return _markdown_row_with_cell(section, status)


def test_adr0007_closure_runbook_exists() -> None:
    """Operator runbook must document the ADR 0007 remediation and dispatch path."""
    assert RUNBOOK.is_file()
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "check_database_authorization.py" in text
    assert "db_authz: PASS|" in text
    assert "ASSET_GRAPH_DATABASE_URL" in text
    assert "COORDINATION_DATABASE_URL" in text
    assert "FARDB_EXPOSED_DATABASE_SCHEMAS" in text
    assert "FARDB_EXPOSED_DATABASE_SCHEMAS_ASSET_GRAPH" in text
    assert "environment **secrets**" in text.lower() or "environment secrets" in text.lower()
    assert "staging-manual-gate" in text
    assert "release-evidence" in text
    assert "Settings → Environments" in text or "settings → environments" in text.lower()
    assert "full" in text.lower() and "inventoried" in text.lower()
    assert "hardening_tier=P0" in text
    assert "repository root" in text.lower()
    assert "H-P0-04 closure is target-bound" in text
    assert "Staging is Satisfied" in text
    assert "docs/evidence-records/hp004-db-authz-pass-29991d03.md" in text
    assert "db_authz: PASS|run-30002002715" in text
    assert "Until staging closure evidence and named sign-off are attached" not in text


def test_enterprise_readiness_index_does_not_reopen_satisfied_gates() -> None:
    """The current index must preserve target proof without reopening repository or staging closure."""
    text = ENTERPRISE_INDEX.read_text(encoding="utf-8")
    satisfied_automated = _roadmap_status_row(text, "Satisfied - automated")
    partially_satisfied = _roadmap_status_row(text, "Partially satisfied")
    blocked = _roadmap_status_row(text, "Blocked")

    assert "db_authz: PASS|run-30002002715" in text
    assert "strict stale-owner restart composition" in satisfied_automated.lower()
    assert "stale-owner" not in partially_satisfied.lower()
    assert "release-blocking database authorization closure" not in text.lower()
    assert "database authorization closure remains release-blocking" not in blocked.lower()
    assert "target-specific database authorization evidence" in blocked.lower()


def test_adr0007_evidence_templates_exist() -> None:
    """Restricted and public worksheets must exist and keep evidence tiers distinct."""
    assert RESTRICTED.is_file()
    assert PUBLIC.is_file()
    restricted = RESTRICTED.read_text(encoding="utf-8")
    public = PUBLIC.read_text(encoding="utf-8")
    assert "do not commit filled copies" in restricted.lower()
    assert "db_authz: PASS|" in public
    assert "do not" in public.lower() and "filled copy" in public.lower()
    assert "hardening_tier=p0" in public.lower()
    assert "workflow run commit sha" in public.lower()
    assert "FARDB_EXPOSED_DATABASE_SCHEMAS" in restricted
    assert "FARDB_EXPOSED_DATABASE_SCHEMAS" in public
    assert "environment **secrets**" in restricted.lower() or "environment secrets" in restricted.lower()
    assert "if any boundary uses the global/default inventory" in restricted.lower()
    assert "FARDB_EXPOSED_DATABASE_SCHEMAS_DATABASE" in restricted
    assert "FARDB_EXPOSED_DATABASE_SCHEMAS_ASSET_GRAPH" in restricted
    assert "FARDB_EXPOSED_DATABASE_SCHEMAS_COORDINATION" in restricted
    assert "FARDB_EXPOSED_DATABASE_SCHEMAS_POSTGRES" in restricted
    assert "manual-gate" in restricted.lower()
    assert "privileged functions manual fixed-search-path review" in public.lower()
    assert "release authority" in restricted.lower()


def test_adr0007_issue_template_exists() -> None:
    """GitHub issue template must track Environment secrets and remediation steps."""
    assert ISSUE_TEMPLATE.is_file()
    text = ISSUE_TEMPLATE.read_text(encoding="utf-8")
    assert "ADR 0007" in text
    assert "COORDINATION_DATABASE_URL" in text
    assert "db_authz: PASS|" in text
    assert "staging-promotion" in text
    assert "production-promotion" in text
    assert "release-evidence-verify" in text
    assert "`staging` Environment exists" in text
    assert "`staging-manual-gate` Environment exists" in text
    assert "`release-evidence` Environment exists" in text


def test_env_example_documents_untrusted_roles() -> None:
    """`.env.example` must document authz-gate env vars for local dry-runs."""
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "FARDB_UNTRUSTED_DATABASE_ROLES" in text
    assert "FARDB_EXPOSED_DATABASE_SCHEMAS" in text
    assert "check_database_authorization.py" in text


def test_adr0007_wired_into_existing_authorities() -> None:
    """Existing authorities must point at the operator closure setup path."""
    adr = ADR_0007.read_text(encoding="utf-8")
    staging = STAGING_BASELINE.read_text(encoding="utf-8")
    continuity = CONTINUITY.read_text(encoding="utf-8")
    rc = RC_EVIDENCE.read_text(encoding="utf-8")
    evidence_pack = EVIDENCE_PACK.read_text(encoding="utf-8")
    pr_board = PR_BOARD.read_text(encoding="utf-8")
    evidence_record = EVIDENCE_RECORD.read_text(encoding="utf-8")

    assert "database-authorization-closure.md" in adr
    assert "database-authorization-closure.md" in staging
    assert "hardening_tier=P0" in staging or "hardening_tier=none" in staging
    assert "database-authorization-closure.md" in continuity
    assert "H-P0-04a" in rc
    assert "template=database_authorization_closure.md" in rc
    assert "runbooks/database-authorization-closure.md" in evidence_pack
    assert "db_authz: PASS|run-30002002715" in evidence_pack
    assert "Partially satisfied — staging PASS attached" not in evidence_pack
    assert "sign-off open" not in evidence_pack.lower()
    assert "live redacted pass is required" not in pr_board.lower()

    hp004_pack_row = _markdown_row_with_cell(evidence_pack, "H-P0-04")
    assert "Satisfied - manual evidence" in hp004_pack_row
    assert "run-30002002715" in hp004_pack_row

    hp004_board_row = _markdown_row_with_cell(pr_board, "H-P0-04")
    assert "Satisfied - manual evidence" in hp004_board_row
    assert "operator closure runbook" in pr_board.lower() or "run-30002002715" in hp004_board_row

    assert "fixed-search-path review: passed" in evidence_record.lower()
    assert "| Closure owner                 | mohavro     | Approved | 2026-07-24 |" in evidence_record
    assert "| Promotion / release authority | mohavro     | Approved | 2026-07-24 |" in evidence_record
    assert "db_authz: PASS|run-30002002715" in evidence_record
