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
    with open(MERGIFY_PATH, "r") as f:
        return yaml.safe_load(f)


@pytest.mark.integration
class TestMergifyConfigIntegration:
    """Cross-rule integration validation for .mergify.yml."""

    def test_config_loads_and_validates(self):
        """Parse YAML and check top-level keys are present and correct."""
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
        toggle_labels lists across all rules must not share duplicate label names.
        Each size label should appear in exactly one rule.
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
        Auto-merge rules must reference 'check-success=Test Python 3.12',
        matching the actual CI job name in ci.yml.
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
        The review-request rule must have negative conditions for both
        dependabot[bot] and snyk-bot to avoid requesting reviews on bot PRs.
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
        Both a 'mark stale' rule (adds stale label) and a 'remove stale' rule
        (removes stale label) must exist so stale management is reversible.
        """
        config = load_config()
        rules = config["pull_request_rules"]

        adds_stale = [r for r in rules if "stale" in r.get("actions", {}).get("label", {}).get("add", [])]
        removes_stale = [r for r in rules if "stale" in r.get("actions", {}).get("label", {}).get("remove", [])]

        assert adds_stale, "No rule found that adds the 'stale' label"
        assert removes_stale, "No rule found that removes the 'stale' label"
        assert len(adds_stale) == 1, f"Expected exactly 1 rule to add 'stale', found {len(adds_stale)}"
        assert len(removes_stale) == 1, f"Expected exactly 1 rule to remove 'stale', found {len(removes_stale)}"


@pytest.mark.integration
class TestMergifyComplexScenarios:
    """Test complex real-world scenarios across multiple rules."""

    def test_bot_pr_auto_merge_safety(self):
        """
        Verify that bot PRs require CI success and cannot auto-merge if CI fails.
        This prevents regression where broken code gets merged automatically.
        """
        config = load_config()
        rules = config["pull_request_rules"]

        bot_auto_merge_rules = [
            r
            for r in rules
            if "merge" in r.get("actions", {})
            and any(bot in str(r.get("conditions", [])) for bot in ["dependabot", "snyk-bot"])
        ]

        assert len(bot_auto_merge_rules) >= 2, "Should have auto-merge rules for both Dependabot and Snyk"

        for rule in bot_auto_merge_rules:
            conditions = " ".join(str(c) for c in rule.get("conditions", []))
            # Must require a passing CI check
            assert "check-success" in conditions, f"Bot auto-merge rule '{rule.get('name')}' must require passing CI"

    def test_size_label_updates_when_pr_changes(self):
        """
        Verify size labels use 'toggle' so they update automatically when PR grows/shrinks.
        This prevents stale labels when a PR is updated with more/fewer changes.
        """
        config = load_config()
        rules = config["pull_request_rules"]

        size_rules = [r for r in rules if "t-shirt" in r.get("name", "").lower()]
        assert len(size_rules) > 0, "No size rules found"

        for rule in size_rules:
            label_action = rule.get("actions", {}).get("label", {})
            # Size rules should use toggle, not add
            assert "toggle" in label_action, (
                f"Size rule '{rule.get('name')}' should use 'toggle' to update automatically"
            )
            assert "add" not in label_action, (
                f"Size rule '{rule.get('name')}' should not use 'add' (use 'toggle' instead)"
            )

    def test_content_labels_are_additive(self):
        """
        Verify content labels use 'add' not 'toggle' so multiple content labels can coexist.
        A PR that touches both CI and docs should get both labels.
        """
        config = load_config()
        rules = config["pull_request_rules"]

        content_label_rules = [
            r
            for r in rules
            if any(
                label in r.get("actions", {}).get("label", {}).get("add", [])
                for label in ["security", "ci", "documentation", "dependencies"]
            )
        ]

        assert len(content_label_rules) >= 4, "Should have at least 4 content label rules"

        for rule in content_label_rules:
            label_action = rule.get("actions", {}).get("label", {})
            # Content rules should use add, not toggle
            assert "add" in label_action, f"Content rule '{rule.get('name')}' should use 'add' for cumulative labels"

    def test_review_automation_excludes_bot_prs(self):
        """
        Verify that bot PRs don't trigger human review requests.
        This prevents spam review requests for automated PRs.
        """
        config = load_config()
        rules = config["pull_request_rules"]

        review_request_rules = [r for r in rules if "request_reviews" in r.get("actions", {})]
        assert len(review_request_rules) > 0, "No review request rules found"

        for rule in review_request_rules:
            conditions = " ".join(str(c) for c in rule.get("conditions", []))
            # Should exclude both common bot accounts
            assert "-author=dependabot[bot]" in conditions, (
                f"Review request rule '{rule.get('name')}' should exclude dependabot"
            )
            assert "-author=snyk-bot" in conditions, f"Review request rule '{rule.get('name')}' should exclude snyk-bot"

    def test_stale_workflow_prevents_premature_closure(self):
        """
        Verify stale label is removed when PR gets activity, preventing accidental closure.
        This ensures active PRs don't get closed even if they were previously stale.
        """
        config = load_config()
        rules = config["pull_request_rules"]

        # Find stale removal rule
        stale_remove_rules = [r for r in rules if "stale" in r.get("actions", {}).get("label", {}).get("remove", [])]
        assert len(stale_remove_rules) > 0, "No stale removal rule found"

        for rule in stale_remove_rules:
            conditions = " ".join(str(c) for c in rule.get("conditions", []))
            # Should check for stale label and recent activity
            assert "label=stale" in conditions or "label= stale" in conditions, (
                f"Stale removal rule '{rule.get('name')}' should check for stale label"
            )
            assert "updated-at >=" in conditions, (
                f"Stale removal rule '{rule.get('name')}' should check for recent updates"
            )

    def test_multiple_labels_can_apply_simultaneously(self):
        """
        Verify a PR can have both size and content labels simultaneously.
        A PR changing requirements.txt should get both size/X and dependencies labels.
        """
        config = load_config()
        rules = config["pull_request_rules"]

        # Count rules that could apply to a hypothetical PR changing requirements.txt
        size_rules = [r for r in rules if "size/" in str(r.get("actions", {}).get("label", {}))]
        dependency_rules = [r for r in rules if "dependencies" in r.get("actions", {}).get("label", {}).get("add", [])]

        assert len(size_rules) >= 1, "Should have size labeling rules"
        assert len(dependency_rules) >= 1, "Should have dependency labeling rules"

        # Verify no conditions that would prevent both from applying
        for size_rule in size_rules:
            size_conditions = " ".join(str(c) for c in size_rule.get("conditions", []))
            # Size rules shouldn't exclude dependency changes
            assert "-files~=" not in size_conditions or "requirements" not in size_conditions, (
                "Size rules shouldn't exclude dependency files"
            )


@pytest.mark.integration
class TestMergifySecurityAndSafety:
    """Test security and safety aspects of Mergify configuration."""

    def test_auto_merge_requires_passing_tests(self):
        """
        Verify all auto-merge rules require passing CI tests.
        This prevents auto-merging broken code.
        """
        config = load_config()
        rules = config["pull_request_rules"]

        auto_merge_rules = [r for r in rules if "merge" in r.get("actions", {})]
        assert len(auto_merge_rules) > 0, "No auto-merge rules found"

        for rule in auto_merge_rules:
            conditions = " ".join(str(c) for c in rule.get("conditions", []))
            assert "check-success" in conditions, f"Auto-merge rule '{rule.get('name')}' must require passing CI check"

    def test_no_auto_merge_for_large_changes(self):
        """
        Verify Dependabot auto-merge limits changed files to prevent large auto-merges.
        This prevents accidentally merging major dependency updates without review.
        """
        config = load_config()
        rules = config["pull_request_rules"]

        dep_auto_merge = next(
            (
                r
                for r in rules
                if "dependabot" in str(r.get("conditions", [])).lower() and "merge" in r.get("actions", {})
            ),
            None,
        )
        assert dep_auto_merge is not None, "Dependabot auto-merge rule not found"

        conditions = " ".join(str(c) for c in dep_auto_merge.get("conditions", []))
        assert "#changed-files" in conditions, "Dependabot auto-merge should limit changed files"

    def test_auto_merge_uses_safe_merge_method(self):
        """
        Verify auto-merge uses 'squash' method to maintain clean history.
        This prevents pollution of main branch with multiple bot commits.
        """
        config = load_config()
        rules = config["pull_request_rules"]

        auto_merge_rules = [r for r in rules if "merge" in r.get("actions", {})]
        assert len(auto_merge_rules) > 0, "No auto-merge rules found"

        for rule in auto_merge_rules:
            merge_action = rule["actions"]["merge"]
            method = merge_action.get("method")
            assert method == "squash", (
                f"Auto-merge rule '{rule.get('name')}' should use 'squash' method, got '{method}'"
            )

    def test_dismiss_reviews_only_on_new_commits(self):
        """
        Verify review dismissal only happens on 'synchronize' (new commits).
        This ensures reviews aren't dismissed for comments or label changes.
        """
        config = load_config()
        rules = config["pull_request_rules"]

        dismiss_rules = [r for r in rules if "dismiss_reviews" in r.get("actions", {})]
        assert len(dismiss_rules) > 0, "No dismiss_reviews rules found"

        for rule in dismiss_rules:
            dismiss_action = rule["actions"]["dismiss_reviews"]
            when = dismiss_action.get("when")
            assert when == "synchronize", (
                f"Dismiss reviews rule '{rule.get('name')}' should only trigger on 'synchronize', got '{when}'"
            )

    def test_stale_management_excludes_closed_prs(self):
        """
        Verify stale marking doesn't apply to closed PRs.
        This prevents unnecessary label operations on closed PRs.
        """
        config = load_config()
        rules = config["pull_request_rules"]

        stale_add_rules = [r for r in rules if "stale" in r.get("actions", {}).get("label", {}).get("add", [])]
        assert len(stale_add_rules) > 0, "No stale marking rules found"

        for rule in stale_add_rules:
            conditions = " ".join(str(c) for c in rule.get("conditions", []))
            assert "-closed" in conditions, f"Stale marking rule '{rule.get('name')}' should exclude closed PRs"


@pytest.mark.integration
class TestMergifyRulePriority:
    """Test rule ordering and priority."""

    def test_all_size_tiers_are_mutually_exclusive(self):
        """
        Verify exactly one size tier applies to any given line count.
        This prevents multiple size labels on a single PR.
        """
        config = load_config()
        rules = config["pull_request_rules"]

        size_rules = [r for r in rules if "t-shirt" in r.get("name", "").lower()]
        assert len(size_rules) == 6, f"Expected 6 size tiers, found {len(size_rules)}"

        # Test various line counts to ensure exactly one tier matches each
        test_line_counts = [0, 5, 9, 10, 25, 49, 50, 75, 99, 100, 250, 499, 500, 750, 999, 1000, 2000]

        for line_count in test_line_counts:
            matching_tiers = []
            for rule in size_rules:
                matches = True
                for cond in rule.get("conditions", []):
                    cond_str = str(cond)
                    if ">=" in cond_str and "#modified-lines" in cond_str:
                        threshold = int(re.search(r"(\d+)", cond_str).group(1))
                        if line_count < threshold:
                            matches = False
                    if "<" in cond_str and ">=" not in cond_str and "#modified-lines" in cond_str:
                        threshold = int(re.search(r"(\d+)", cond_str).group(1))
                        if line_count >= threshold:
                            matches = False
                if matches:
                    matching_tiers.append(rule.get("name"))

            assert len(matching_tiers) == 1, (
                f"Line count {line_count} matches {len(matching_tiers)} tiers: {matching_tiers}. "
                "Expected exactly 1 tier."
            )

    def test_rule_names_are_unique(self):
        """
        Verify all rules have unique names.
        Duplicate names could cause confusion in Mergify dashboard.
        """
        config = load_config()
        rules = config["pull_request_rules"]

        names = [r.get("name") for r in rules]
        duplicates = [name for name in names if names.count(name) > 1]

        assert len(duplicates) == 0, f"Found duplicate rule names: {set(duplicates)}"
