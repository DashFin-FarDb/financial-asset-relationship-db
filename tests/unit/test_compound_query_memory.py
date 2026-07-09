"""Unit tests for query_memory consumer."""

from __future__ import annotations

# nosec B101  # Pytest assertions are the intended style in this test module.
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from compound.query_memory import query_memory, select_domains  # noqa: E402


@pytest.fixture
def query_repo(tmp_path: Path) -> Path:
    """Repo with persistence domain observations."""
    (tmp_path / "docs/compound/domains").mkdir(parents=True)
    (tmp_path / "docs/compound/INDEX.md").write_text("# Index\n", encoding="utf-8")
    (tmp_path / "docs/compound/domains/persistence.md").write_text(
        "# Persistence\n\n"
        "## Landed\n\n"
        "- **doc:graph-persistence**: Graph rebuild persistence ownership in api/graph_lifecycle\n"
        "  - evidence: docs/graph-persistence-lifecycle-seam.md\n\n"
        "## Provisional\n\n"
        "- **pr:99**: Propose new persistence seam\n"
        "  - evidence: pr:99\n",
        encoding="utf-8",
    )
    for domain in (
        "architecture",
        "api",
        "ci-guardrails",
        "rebuild-reconciliation",
        "deployment",
    ):
        (tmp_path / f"docs/compound/domains/{domain}.md").write_text(
            f"# {domain}\n\n## Landed\n\n_No landed observations yet._\n\n"
            "## Provisional\n\n_No provisional observations yet._\n",
            encoding="utf-8",
        )
    return tmp_path


@pytest.mark.unit
class TestQueryMemory:
    """Chat/query consumer behavior."""

    def test_selects_persistence_domain(self) -> None:
        """Graph rebuild persistence questions map to persistence domain."""
        domains = select_domains("where does graph rebuild persistence ownership live?")
        assert "persistence" in domains or "rebuild-reconciliation" in domains

    def test_answer_labels_provisional_and_landed(self, query_repo: Path) -> None:
        """Query returns pointers and provisional/landed labels."""
        answer = query_memory(
            query_repo,
            "where does graph rebuild persistence ownership live?",
        )
        assert "Landed:" in answer or "landed" in answer.lower()
        assert "Provisional:" in answer or "provisional" in answer.lower()
        assert "graph rebuild persistence" in answer.lower() or "persistence" in answer.lower()
        assert "pr:99" in answer or "Propose new persistence seam" in answer
