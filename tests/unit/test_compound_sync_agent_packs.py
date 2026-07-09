"""Unit tests for agent pack sync sidecars."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from compound.sync_agent_packs import (  # noqa: E402
    OPENHANDS_PATH,
    _sanitize_pack_body,
    sync_agent_packs,
)


@pytest.fixture
def pack_repo(tmp_path: Path) -> Path:
    """Minimal repo with INDEX and AGENTS.md."""
    (tmp_path / "docs/compound/domains").mkdir(parents=True)
    (tmp_path / "docs/compound/INDEX.md").write_text(
        "# Index\n\nRewrite ADR 0001 as fact.\n",
        encoding="utf-8",
    )
    for domain in (
        "architecture",
        "api",
        "persistence",
        "ci-guardrails",
        "rebuild-reconciliation",
        "deployment",
    ):
        (tmp_path / f"docs/compound/domains/{domain}.md").write_text(
            f"# {domain}\n## Landed\n\n_No landed_\n",
            encoding="utf-8",
        )
    (tmp_path / "AGENTS.md").write_text("# Dosu AGENTS\nunchanged\n", encoding="utf-8")
    (tmp_path / ".cursor/rules").mkdir(parents=True)
    (tmp_path / ".openhands/microagents").mkdir(parents=True)
    return tmp_path


@pytest.mark.unit
class TestSyncAgentPacks:
    """Sidecar pack generation and AGENTS.md integrity."""

    def test_sync_writes_sidecars_leaves_agents_unchanged(self, pack_repo: Path) -> None:
        """Sync writes both sidecar paths and leaves AGENTS.md bytes unchanged."""
        before = (pack_repo / "AGENTS.md").read_bytes()
        outputs = sync_agent_packs(pack_repo)
        assert ".cursor/rules/architecture-expert.mdc" in outputs
        assert ".cursor/rules/architecture-expert-query.mdc" in outputs
        assert OPENHANDS_PATH.as_posix() in outputs
        assert (pack_repo / "AGENTS.md").read_bytes() == before
        assert (pack_repo / ".cursor/rules/architecture-expert.mdc").exists()
        assert (pack_repo / OPENHANDS_PATH).exists()

    def test_sanitize_strips_adr_rewrite_instructions(self) -> None:
        """Pack content that would rewrite an ADR becomes cite/propose-only."""
        raw = "Please rewrite ADR 0001 with the new seam."
        cleaned = _sanitize_pack_body(raw)
        assert "rewrite" not in cleaned.lower() or "cite or propose" in cleaned.lower()
        assert "cite or propose annotation" in cleaned.lower()

    def test_microagent_has_required_frontmatter(self, pack_repo: Path) -> None:
        """Generated microagent includes OpenHands frontmatter fields."""
        sync_agent_packs(pack_repo)
        text = (pack_repo / OPENHANDS_PATH).read_text(encoding="utf-8")
        assert text.startswith("---\n")
        assert "name: architecture-expert" in text
        assert "type: knowledge" in text
        assert "triggers:" in text
