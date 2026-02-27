"""
Integration tests for Mergify configuration cross-rule validation.

Tests verify that the rules in .mergify.yml work together correctly,
with no gaps, duplicates, or inconsistencies across rule boundaries.
"""

import re
from pathlib import Path

import pytest
import yaml

MERGIFY_PATH = Path(__file__).parent.parent.parent / ".mergify.yml"

pytestmark = pytest.mark.integration


def load_config():
    """
    Load and parse the repository's .mergify.yml configuration.

    Returns:
        The parsed Mergify configuration as Python objects (typically a dict), or `None` if the file is empty.
    """
    with open(MERGIFY_PATH, "r") as f:
        return yaml.safe_load(f)


@pytest.mark.integration
class TestMergifyConfigIntegration:
    """Cross-rule integration validation for .mergify.yml."""

    def test_config_loads_and_validates(self):
        """
        Validate that .mergify.yml loads and contains a non-empty top-level pull_request_rules list with required fields.

        Asserts that the parsed configuration is not empty, that "pull_request_rules" exists and is a non-empty list, and that each rule contains "name", "conditions", and "actions".
        """
        config = load_config()

        assert config is not None, ".mergify.yml is empty"
        assert "pull_request_rules" in config, "Missing top-level key: pull_request_rules"
        rules = config["pull_request_rules"]
        assert isinstance(rules, list), "pull_request_rules must be a list"
        assert len(rules) > 0, "pull_request_rules must not be empty"

        for idx, rule in enumerate(rules):
            assert "name" in rule, f"Rule at index {idx} is missing 'name'"
            assert "conditions" in rule, f"Rule '{rule.get('name', idx)}' is missing 'conditions'"
            assert "actions" in rule, f"Rule '{rule.get('name', idx)}' is missing 'actions'"

    def test_size_tier_continuity(self):
        """
        Extract all #modified-lines bounds, sort them, and verify upper bound
        of tier N equals lower bound of tier N+1 (no gaps between tiers).
        """
        config = load_config()
        rules = config["pull_request_rules"]
        tshirt_rules = [r for r in rules if "t-shirt" in r.get("name", "").lower()]

        # Build a list of (lower, upper) pairs for each tier
        # XS has no lower bound → treat as 0
        # XXL has no upper bound → treat as infinity
        tiers = []
        for rule in tshirt_rules:
            lower = 0
            upper = float("inf")
            for cond in rule.get("conditions", []):
                cond_str = str(cond)
                m_lower = re.search(r"#modified-lines\s*>=\s*(\d+)", cond_str)
                m_upper = re.search(r"#modified-lines\s*<\s*(\d+)", cond_str)
                if m_lower:
                    lower = int(m_lower.group(1))
                if m_upper:
                    upper = int(m_upper.group(1))
            tiers.append((lower, upper, rule["name"]))

        # Sort by lower bound
        tiers.sort(key=lambda t: t[0])

        # Verify continuity: upper bound of tier[i] == lower bound of tier[i+1]
        for i in range(len(tiers) - 1):
            current_upper = tiers[i][1]
            next_lower = tiers[i + 1][0]
            assert current_upper == next_lower, (
                f"Gap between tiers: '{tiers[i][2]}' ends at {current_upper} "
                f"but '{tiers[i + 1][2]}' starts at {next_lower}"
            )

    def test_no_duplicate_labels_across_rules(self):
        """
        Ensure label toggle actions are unique across all pull request rules.

        Asserts that no label appears in more than one rule's `actions.label.toggle` list; reports duplicates if found.
        """
        config = load_config()
        rules = config["pull_request_rules"]

        toggle_labels = []
        for rule in rules:
            label_action = rule.get("actions", {}).get("label", {})
            toggle_labels.extend(label_action.get("toggle", []))

        assert len(toggle_labels) == len(set(toggle_labels)), (
            f"Duplicate toggle labels found: {[l for l in toggle_labels if toggle_labels.count(l) > 1]}"
        )

    def test_ci_check_name_in_auto_merge_rules(self):
        """
        Verify auto-merge rules include the CI check name 'check-success=Test Python 3.12'.

        Asserts that at least one auto-merge rule is present and that each auto-merge rule's conditions contain the string "check-success=Test Python 3.12".
        """
        config = load_config()
        rules = config["pull_request_rules"]

        auto_merge_rules = [r for r in rules if "merge" in r.get("actions", {})]
        assert auto_merge_rules, "No auto-merge rules found"

        for rule in auto_merge_rules:
            conditions = " ".join(str(c) for c in rule.get("conditions", []))
            assert "check-success=Test Python 3.12" in conditions, (
                f"Auto-merge rule '{rule['name']}' must reference 'check-success=Test Python 3.12'"
            )

    def test_review_request_excludes_bots(self):
        """
        Ensure review-request rules exclude dependabot[bot] and snyk-bot.

        Asserts there is at least one rule with "request_reviews" in actions and that each such rule's conditions include "-author=dependabot[bot]" and "-author=snyk-bot".
        """
        config = load_config()
        rules = config["pull_request_rules"]

        review_rules = [r for r in rules if "request_reviews" in r.get("actions", {})]
        assert review_rules, "No request_reviews rule found"

        for rule in review_rules:
            conditions = " ".join(str(c) for c in rule.get("conditions", []))
            assert "-author=dependabot[bot]" in conditions, (
                f"Review-request rule '{rule['name']}' must exclude dependabot[bot]"
            )
            assert "-author=snyk-bot" in conditions, f"Review-request rule '{rule['name']}' must exclude snyk-bot"

    def test_stale_rules_are_paired(self):
        """
        Ensure there is exactly one rule that adds the "stale" label and exactly one rule that removes it.

        Verifies that stale label management is paired and reversible by asserting the presence of a single add-rule and a single remove-rule for the "stale" label.
        """
        config = load_config()
        rules = config["pull_request_rules"]

        adds_stale = [r for r in rules if "stale" in r.get("actions", {}).get("label", {}).get("add", [])]
        removes_stale = [r for r in rules if "stale" in r.get("actions", {}).get("label", {}).get("remove", [])]

        assert adds_stale, "No rule found that adds the 'stale' label"
        assert removes_stale, "No rule found that removes the 'stale' label"
        assert len(adds_stale) == 1, f"Expected exactly 1 rule to add 'stale', found {len(adds_stale)}"
        assert len(removes_stale) == 1, f"Expected exactly 1 rule to remove 'stale', found {len(removes_stale)}"
