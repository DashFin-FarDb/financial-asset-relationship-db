"""Unit tests for Loki recording rule coverage."""

# pylint: disable=import-error,invalid-name
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import pytest
import yaml  # type: ignore[import-untyped]

pytestmark = pytest.mark.unit

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOKI_RECORDING_PATH = PROJECT_ROOT / "monitoring" / "alerts" / "loki-recording.yml"


def _recording_rules() -> dict[str, str]:
    """Load Loki recording rules by record name."""
    loaded = yaml.safe_load(LOKI_RECORDING_PATH.read_text(encoding="utf-8"))
    assert isinstance(loaded, Mapping), "Loki recording file must contain a YAML mapping"
    config = cast(Mapping[str, Any], loaded)
    groups = cast(list[Mapping[str, Any]], config.get("groups", []))
    assert groups, "Loki recording file must contain at least one group"
    rules = [rule for group in groups for rule in cast(list[Mapping[str, Any]], group.get("rules", []))]
    assert rules, "Loki recording groups must contain at least one rule"
    return {cast(str, rule["record"]): cast(str, rule["expr"]) for rule in rules}


def test_loki_recording_rules_include_auth_failure_aggregation() -> None:
    """Loki should pre-aggregate login and token validation failures."""
    rules = _recording_rules()
    expr = rules["log_auth_failures_total"]

    assert "auth_login_failure" in expr
    assert "auth_token_expired" in expr
    assert "auth_token_invalid" in expr
    assert "sum by (event)" in expr


def test_loki_recording_rules_include_access_denied_aggregation() -> None:
    """Loki should pre-aggregate authorization and disabled-user denials."""
    rules = _recording_rules()
    expr = rules["log_access_denied_total"]

    assert "auth_access_denied" in expr
    assert "auth_user_disabled" in expr
    assert "sum by (event)" in expr
