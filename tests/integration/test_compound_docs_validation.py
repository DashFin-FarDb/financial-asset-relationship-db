"""Integration tests for compound docs validation and guardrails."""

from __future__ import annotations

# nosec B101  # Pytest assertions are the intended style in this test module.
from pathlib import Path

import pytest
import yaml

from tests.integration.test_github_workflows import load_yaml_safe

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "architecture-compound.yml"
COMPOUND = REPO_ROOT / "docs" / "compound"
ENTERPRISE_INDEX = REPO_ROOT / "docs" / "enterprise-readiness-index.md"


@pytest.mark.integration
class TestCompoundDocsValidation:
    """Compound tree shape and cross-links."""

    def test_compound_tree_exists(self) -> None:
        """Required compound paths exist."""
        assert (COMPOUND / "INDEX.md").exists()
        assert (COMPOUND / "watched-series.yml").exists()
        assert (COMPOUND / "runtime.yml").exists()
        assert (COMPOUND / "ledger" / "observations.jsonl").exists()
        for domain in (
            "architecture",
            "api",
            "persistence",
            "ci-guardrails",
            "rebuild-reconciliation",
            "deployment",
        ):
            assert (COMPOUND / "domains" / f"{domain}.md").exists()

    def test_runtime_yml_has_writer_mode(self) -> None:
        """runtime.yml declares writer_mode."""
        data = yaml.safe_load((COMPOUND / "runtime.yml").read_text(encoding="utf-8"))
        assert data["writer_mode"] in {"dual", "github_only"}


@pytest.mark.integration
class TestCompoundGuardrails:
    """High-risk automation contracts."""

    def test_workflow_no_main_merge_steps(self) -> None:
        """No auto-merge / main merge commands in non-comment workflow lines."""
        text = WORKFLOW.read_text(encoding="utf-8")
        code_only = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
        lowered = code_only.lower()
        assert "gh pr merge" not in lowered
        assert "auto-merge" not in lowered

    def test_synthesize_job_has_contents_write(self) -> None:
        """Only synthesize elevates contents: write."""
        data = load_yaml_safe(WORKFLOW)
        assert data["permissions"]["contents"] == "read"
        assert data["jobs"]["synthesize"]["permissions"]["contents"] == "write"

    def test_enterprise_index_links_compound_when_present(self) -> None:
        """If enterprise index mentions compound, the target exists."""
        if not ENTERPRISE_INDEX.exists():
            pytest.skip("enterprise-readiness-index.md missing")
        text = ENTERPRISE_INDEX.read_text(encoding="utf-8")
        if "docs/compound" not in text and "compound/INDEX" not in text:
            pytest.skip("enterprise index not yet linked (U6 additive link)")
        assert (COMPOUND / "INDEX.md").exists()
