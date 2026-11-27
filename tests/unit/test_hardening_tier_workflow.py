"""Contract tests for hardening_tier P1-P3 wiring in release-evidence-verify.yml."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "release-evidence-verify.yml"


def test_release_evidence_workflow_supports_cumulative_hardening_tiers() -> None:
    """release-evidence-verify.yml exposes none/P0/P1/P2/P3 with P0 default."""
    raw = WORKFLOW_PATH.read_text(encoding="utf-8")
    parsed = yaml.safe_load(raw)
    inputs = parsed[True]["workflow_dispatch"]["inputs"]
    tier_input = inputs["hardening_tier"]

    assert tier_input["default"] == "P0"
    assert tier_input["options"] == ["none", "P0", "P1", "P2", "P3"]
    assert "gate_hardening_tier" in raw
    assert "hardening-tier-output.json" in raw


def test_hardening_tier_referenced_test_files_exist() -> None:
    """Every pytest file referenced by the P1-P3 hardening tier step exists on disk."""
    raw = WORKFLOW_PATH.read_text(encoding="utf-8")
    step_start = raw.index("id: gate_hardening_tier")
    step_end = raw.index("name: Prepare Artifact Placeholders", step_start)
    step_block = raw[step_start:step_end]

    referenced = re.findall(r"tests/(?:unit|integration)/test_[a-zA-Z0-9_]+\.py", step_block)
    assert len(referenced) >= 10
    for rel_path in referenced:
        assert (REPO_ROOT / rel_path).is_file(), f"Missing workflow test target: {rel_path}"
