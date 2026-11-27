"""Contract validation tests for the Playwright full-stack E2E smoke suite."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = REPO_ROOT / "frontend"


def test_playwright_e2e_files_and_exclusions_exist() -> None:
    """Playwright config, smoke spec, README, and Jest/TS exclusions are properly wired."""
    config_path = FRONTEND_DIR / "playwright.config.ts"
    spec_path = FRONTEND_DIR / "e2e" / "smoke.spec.ts"
    readme_path = FRONTEND_DIR / "e2e" / "README.md"

    assert config_path.is_file()
    assert spec_path.is_file()
    assert readme_path.is_file()

    spec_text = spec_path.read_text(encoding="utf-8")
    for expected in (
        "/api/health/detailed",
        "/api/assets",
        "/api/graph/metrics",
        "/api/auth/logout",
        "3D Visualization",
        "Metrics & Analytics",
        "Asset Explorer",
    ):
        assert expected in spec_text, f"Missing expected E2E check for {expected}"

    jest_cfg = (FRONTEND_DIR / "jest.config.js").read_text(encoding="utf-8")
    assert "<rootDir>/e2e/" in jest_cfg

    typecheck_cfg = json.loads((FRONTEND_DIR / "tsconfig.typecheck.json").read_text(encoding="utf-8"))
    assert "e2e" in typecheck_cfg["exclude"]
    assert "playwright.config.ts" in typecheck_cfg["exclude"]
