"""Unit tests for standing brief generation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from compound.schema import SchemaError, observation_from_mapping  # noqa: E402
from compound.standing_brief import render_standing_brief, write_standing_brief  # noqa: E402


@pytest.mark.unit
class TestStandingBrief:
    """Standing brief durability and labeling."""

    def test_brief_lists_changed_domains(self, tmp_path: Path) -> None:
        """Standing brief from fixture ledger lists changed domains."""
        (tmp_path / "docs/compound/ledger").mkdir(parents=True)
        (tmp_path / "docs/compound/briefs").mkdir(parents=True)
        row = {
            "observation_id": "1",
            "source": "github",
            "event_type": "pull_request.opened",
            "status": "provisional",
            "primary_ref": "pr:10",
            "summary": "API contract tweak",
            "domains": ["api"],
            "created_at": "2026-07-09T00:00:00Z",
        }
        (tmp_path / "docs/compound/ledger/observations.jsonl").write_text(
            json.dumps(row) + "\n",
            encoding="utf-8",
        )
        path = write_standing_brief(tmp_path, as_of="2026-07-09")
        text = path.read_text(encoding="utf-8")
        assert "### api" in text
        assert "[provisional]" in text
        assert "pr:10" in text
        assert "ADR" not in text or "not rewritten" in text.lower()

    def test_render_includes_status_labels(self) -> None:
        """Renderer includes landed/provisional markers."""
        obs = observation_from_mapping(
            {
                "observation_id": "x",
                "source": "bootstrap",
                "event_type": "seed.doc",
                "status": "landed",
                "primary_ref": "doc:a",
                "summary": "Seed",
                "domains": ["architecture"],
            }
        )
        text = render_standing_brief([obs], as_of="2026-07-09")
        assert "[landed]" in text
        assert "architecture" in text

    def test_main_reports_schema_errors(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """CLI reports schema failures without an unhandled traceback."""
        from compound import standing_brief as mod

        def raise_schema_error(repo_root: Path, *, as_of: str | None = None) -> Path:
            raise SchemaError("bad ledger")

        monkeypatch.setattr(mod, "write_standing_brief", raise_schema_error)

        assert mod.main(["--repo-root", str(tmp_path)]) == 1
        captured = capsys.readouterr()
        assert captured.err == "error: bad ledger\n"
