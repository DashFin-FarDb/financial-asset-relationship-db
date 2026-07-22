"""Contract tests for ADR 0007 / H-P0-04 operator closure setup path."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNBOOK = REPO_ROOT / "docs" / "runbooks" / "database-authorization-closure.md"
RESTRICTED = REPO_ROOT / "docs" / "evidence-records" / "templates" / "db-authz-restricted-closure.md"
PUBLIC = REPO_ROOT / "docs" / "evidence-records" / "templates" / "db-authz-public-redacted-pass.md"
ISSUE_TEMPLATE = REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "database_authorization_closure.md"
ENV_EXAMPLE = REPO_ROOT / ".env.example"


def test_adr0007_closure_runbook_exists() -> None:
    """Operator runbook must document the ADR 0007 remediation and dispatch path."""
    assert RUNBOOK.is_file()
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "check_database_authorization.py" in text
    assert "db_authz: PASS|" in text
    assert "ASSET_GRAPH_DATABASE_URL" in text
    assert "COORDINATION_DATABASE_URL" in text
    assert "hardening_tier=P0" in text


def test_adr0007_evidence_templates_exist() -> None:
    """Restricted and public worksheets must exist and keep evidence tiers distinct."""
    assert RESTRICTED.is_file()
    assert PUBLIC.is_file()
    restricted = RESTRICTED.read_text(encoding="utf-8")
    public = PUBLIC.read_text(encoding="utf-8")
    assert "do not commit filled copies" in restricted.lower()
    assert "db_authz: PASS|" in public
    assert "hardening_tier=P0" in public or "hardening_tier" in public
    assert "Workflow run commit SHA" in public
    assert "--exposed-schema" in restricted
    assert "Privileged functions manual fixed-search-path review" in public


def test_adr0007_issue_template_exists() -> None:
    """GitHub issue template must track Environment secrets and remediation steps."""
    assert ISSUE_TEMPLATE.is_file()
    text = ISSUE_TEMPLATE.read_text(encoding="utf-8")
    assert "ADR 0007" in text
    assert "COORDINATION_DATABASE_URL" in text
    assert "db_authz: PASS|" in text


def test_env_example_documents_untrusted_roles() -> None:
    """`.env.example` must document FARDB_UNTRUSTED_DATABASE_ROLES for local dry-runs."""
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert "FARDB_UNTRUSTED_DATABASE_ROLES" in text
    assert "check_database_authorization.py" in text
