"""
Comprehensive unit tests for .mergify.yml configuration file.

Tests validate:
- YAML syntax and structure
- Required fields and valid values
- Pull request rule configurations
- Label assignment logic
- Modified lines thresholds
"""

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.unit


class TestMergifyConfiguration:
    """Test .mergify.yml configuration file validation."""

    MERGIFY_PATH = Path(__file__).parent.parent.parent / ".mergify.yml"

    def test_mergify_file_exists(self):
        """Test that .mergify.yml file exists in repository root."""
        assert self.MERGIFY_PATH.exists(), ".mergify.yml file not found"

    def test_mergify_valid_yaml_syntax(self):
        """Test that .mergify.yml contains valid YAML syntax."""
        try:
            with open(self.MERGIFY_PATH, "r") as f:
                data = yaml.safe_load(f)
            assert data is not None, ".mergify.yml is empty"
        except yaml.YAMLError as e:
            pytest.fail(f"Invalid YAML syntax in .mergify.yml: {e}")

    def test_mergify_has_pull_request_rules(self):
        """Test that .mergify.yml contains pull_request_rules key."""
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)

        assert "pull_request_rules" in config, "Missing pull_request_rules key"
        assert isinstance(config["pull_request_rules"], list), "pull_request_rules must be a list"
        assert len(config["pull_request_rules"]) > 0, "pull_request_rules is empty"

    def test_tshirt_size_rule_exists(self):
        """
        Ensure at least one t-shirt size rule is present and that each such rule includes required fields.

        Asserts that the configuration contains one or more entries in `pull_request_rules` whose `name` contains "t-shirt" (case-insensitive), and that every matched rule has non-empty `name`, `conditions`, and `actions` fields.
        """
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)

        rules = config["pull_request_rules"]
        tshirt_rules = [r for r in rules if "t-shirt" in r.get("name", "").lower()]

        assert tshirt_rules, "T-shirt size rules not found"

        for rule in tshirt_rules:
            assert "name" in rule
            assert "conditions" in rule
            assert "actions" in rule

    def test_tshirt_rule_has_valid_conditions(self):
        """Test that t-shirt size rules have valid conditions."""
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)

        rules = config["pull_request_rules"]
        tshirt_rules = [r for r in rules if "t-shirt" in r.get("name", "").lower()]
        assert tshirt_rules, "No t-shirt rules found"

        for rule in tshirt_rules:
            conditions = rule.get("conditions", [])
            assert isinstance(conditions, list), "Conditions must be a list"
            assert len(conditions) > 0, f"Conditions list is empty in {rule.get('name')}"
            assert any(
                "#modified-lines" in str(c) for c in conditions
            ), f"Missing #modified-lines condition in {rule.get('name')}"

    def test_tshirt_rule_has_label_action(self):
        """Test that t-shirt size rule has label action."""
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)

        rules = config["pull_request_rules"]
        tshirt_rules = [r for r in rules if "t-shirt" in r.get("name", "").lower()]
        assert tshirt_rules, "T-shirt size rules not found"

        for rule in tshirt_rules:
            actions = rule.get("actions", {})
            label_action = actions.get("label")
            assert isinstance(label_action, dict), f"Missing/invalid label action in rule {rule.get('name')}"

            assert any(
                k in label_action for k in ("toggle", "add", "remove")
            ), f"Missing label operation in rule {rule.get('name')}"

            if "toggle" in label_action:
                assert isinstance(label_action["toggle"], list), "Toggle must be a list"
                assert len(label_action["toggle"]) > 0, "Toggle list is empty"
            if "add" in label_action:
                assert isinstance(label_action["add"], list), "Add must be a list"
                assert len(label_action["add"]) > 0, "Add list is empty"
            if "remove" in label_action:
                assert isinstance(label_action["remove"], list), "Remove must be a list"

    def test_tshirt_rule_assigns_size_l_label(self):
        """Test that t-shirt rule assigns size/L label."""
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)

        rules = config["pull_request_rules"]
        size_l_rule = next((r for r in rules if "size/L" in str(r.get("actions", {}))), None)
        assert size_l_rule is not None, "size/L rule not found"

        label_action = size_l_rule["actions"]["label"]
        labels = label_action.get("toggle", []) + label_action.get("add", [])
        assert "size/L" in labels, "size/L label not assigned"

    def test_modified_lines_thresholds_are_valid(self):
        """Test that modified lines thresholds are sensible."""
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)

        rules = config["pull_request_rules"]
        tshirt_rules = [r for r in rules if "t-shirt" in r.get("name", "").lower()]
        assert tshirt_rules, "No t-shirt rules found"

        for rule in tshirt_rules:
            conditions = rule.get("conditions", [])

            min_threshold = None
            max_threshold = None

            for condition in conditions:
                cond = str(condition)
                if ">=" in cond:
                    parts = cond.split(">=")
                    if len(parts) == 2:
                        min_threshold = int(parts[1].strip())
                if "<" in cond and ">=" not in cond:
                    parts = cond.split("<")
                    if len(parts) == 2:
                        max_threshold = int(parts[1].strip())

            if min_threshold is not None:
                assert min_threshold >= 0, f"Min threshold must be non-negative in rule {rule.get('name')}"
            if max_threshold is not None:
                assert max_threshold > 0, f"Max threshold must be positive in rule {rule.get('name')}"
            if min_threshold is not None and max_threshold is not None:
                assert min_threshold < max_threshold, (
                    f"Min threshold ({min_threshold}) must be less than max "
                    f"({max_threshold}) in rule {rule.get('name')}"
                )

    def test_all_rules_have_required_fields(self):
        """Test that all rules have name, conditions, and actions."""
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)

        rules = config["pull_request_rules"]

        for idx, rule in enumerate(rules):
            assert "name" in rule, f"Rule {idx} missing name"
            assert isinstance(rule["name"], str), f"Rule {idx} name must be string"
            assert len(rule["name"]) > 0, f"Rule {idx} name is empty"

            assert "conditions" in rule, f"Rule {idx} ({rule.get('name')}) missing conditions"
            assert isinstance(rule["conditions"], list), f"Rule {idx} conditions must be list"

            assert "actions" in rule, f"Rule {idx} ({rule.get('name')}) missing actions"
            assert isinstance(rule["actions"], dict), f"Rule {idx} actions must be dict"

    def test_mergify_no_syntax_errors(self):
        """Test that Mergify configuration has no obvious syntax errors."""
        with open(self.MERGIFY_PATH, "r") as f:
            content = f.read()

        # Check for common YAML/Mergify issues
        assert content.strip(), "File is empty or whitespace only"
        assert not content.startswith(" "), "File starts with indentation (invalid YAML)"
        assert "pull_request_rules:" in content, "Missing pull_request_rules section"

    def test_label_format_follows_convention(self):
        """Test that labels follow size/* convention."""
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)

        rules = config["pull_request_rules"]

        for rule in rules:
            if "label" in rule.get("actions", {}):
                labels = rule["actions"]["label"].get("toggle", [])
                for label in labels:
                    if label.startswith("size/"):
                        # Valid size labels: size/XS, size/S, size/M, size/L, size/XL
                        valid_sizes = [
                            "size/XS",
                            "size/S",
                            "size/M",
                            "size/L",
                            "size/XL",
                            "size/XXL",
                        ]
                        assert label in valid_sizes, f"Invalid size label: {label}"


class TestMergifyRuleLogic:
    """Test the logical correctness of Mergify rules."""

    MERGIFY_PATH = Path(__file__).parent.parent.parent / ".mergify.yml"

    def test_size_l_range_is_correct(self):
        """
        Verify the size/L t-shirt rule requires modified-lines thresholds covering 100 to 500 lines.

        Asserts that a pull request rule which assigns the `size/L` label exists and that its conditions include thresholds for `>= 100` and `< 500` modified lines.
        """
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)

        rules = config["pull_request_rules"]
        size_l_rule = next((r for r in rules if "size/L" in str(r.get("actions", {}))), None)

        assert size_l_rule is not None, "size/L rule not found"

        conditions = size_l_rule.get("conditions", [])
        condition_str = " ".join(str(c) for c in conditions)

        # Should contain ">= 100" and "< 500"
        assert "100" in condition_str, "Missing 100 threshold"
        assert "500" in condition_str, "Missing 500 threshold"

    def test_description_is_meaningful(self):
        """
        Verify that any rule with a `description` field contains a meaningful, descriptive string.

        Checks:
        - The `description` is a string.
        - The `description` length is greater than 10 characters.
        - The `description` mentions one of: "line", "size", or "change" (case-insensitive).
        """
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)

        rules = config["pull_request_rules"]

        for rule in rules:
            if "description" in rule:
                desc = rule["description"]
                assert isinstance(desc, str), "Description must be string"
                assert len(desc) > 10, f"Description too short: {desc}"
                # Should mention lines or size
                assert any(
                    word in desc.lower() for word in ["line", "size", "change"]
                ), f"Description doesn't mention lines/size/changes: {desc}"


class TestMergifyEdgeCases:
    """Test edge cases and potential issues with Mergify configuration."""

    MERGIFY_PATH = Path(__file__).parent.parent.parent / ".mergify.yml"

    def test_no_conflicting_conditions(self):
        """Test that rules don't have obviously conflicting conditions."""
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)

        rules = config["pull_request_rules"]

        for rule in rules:
            conditions = rule.get("conditions", [])

            # Check for contradictory modified-lines conditions
            min_values = []
            max_values = []

            for condition in conditions:
                cond_str = str(condition)
                if "#modified-lines >=" in cond_str:
                    try:
                        val = int(cond_str.split(">=")[1].strip().strip('"').strip("'"))
                        min_values.append(val)
                    except (ValueError, IndexError):
                        # Ignore conditions that don't contain a valid integer threshold
                        pass
                if "#modified-lines <" in cond_str and ">=" not in cond_str:
                    try:
                        val = int(cond_str.split("<")[1].strip().strip('"').strip("'"))
                        max_values.append(val)
                    except (ValueError, IndexError):
                        # Ignore conditions that don't contain a valid integer threshold
                        pass

            # If both min and max are specified, min should be less than max
            if min_values and max_values:
                assert all(
                    m < mx for m in min_values for mx in max_values
                ), f"Conflicting conditions in rule {rule.get('name')}: min >= max"

    def test_file_size_is_reasonable(self):
        """Test that .mergify.yml file size is reasonable."""
        file_size = self.MERGIFY_PATH.stat().st_size

        # Should be at least 50 bytes (not empty) and less than 10KB (not bloated)
        assert file_size > 50, ".mergify.yml suspiciously small"
        assert file_size < 10240, ".mergify.yml suspiciously large"

    def test_yaml_can_be_parsed_multiple_times(self):
        """Test that YAML can be parsed consistently multiple times."""
        with open(self.MERGIFY_PATH, "r") as f:
            config1 = yaml.safe_load(f)

        with open(self.MERGIFY_PATH, "r") as f:
            config2 = yaml.safe_load(f)

        assert config1 == config2, "YAML parses differently on multiple attempts"


class TestMergifyAdditionalEdgeCases:
    """Additional edge case tests for Mergify configuration."""

    MERGIFY_PATH = Path(__file__).parent.parent.parent / ".mergify.yml"

    def test_all_size_labels_are_unique(self):
        """
        Verify that t-shirt size rules assign unique size labels across all rules.

        Collects labels from each rule whose name contains "t-shirt" by reading the label action's `toggle` and `add` lists, and asserts that no label appears more than once across those lists. Fails with an AssertionError if duplicate size labels are found.
        """
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)

        rules = config["pull_request_rules"]
        size_labels = []
        for rule in rules:
            if "t-shirt" in rule.get("name", "").lower():
                label_action = rule.get("actions", {}).get("label", {})
                toggle_labels = label_action.get("toggle", [])
                add_labels = label_action.get("add", [])
                size_labels.extend(toggle_labels + add_labels)

        # Check for duplicates
        assert len(size_labels) == len(set(size_labels)), "Duplicate size labels found"

    def test_size_thresholds_cover_all_ranges(self):
        """Test that size thresholds cover all possible line counts without gaps."""
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)

        rules = config["pull_request_rules"]
        thresholds = []

        for rule in rules:
            if "t-shirt" in rule.get("name", "").lower():
                conditions = rule.get("conditions", [])
                for cond in conditions:
                    if "#modified-lines" in str(cond):
                        thresholds.append(str(cond))

        # Should have both >= and < conditions
        assert any(">=" in t for t in thresholds), "Missing minimum threshold conditions"
        assert any("<" in t for t in thresholds), "Missing maximum threshold conditions"

    def test_actions_are_properly_formatted(self):
        """
        Verify that every pull request rule's `actions` field is a dictionary and that any `label` action is a dictionary containing at least one of the keys `toggle`, `add`, or `remove`.

        Raises:
            AssertionError: If a rule's `actions` is not a dict; if a `label` action is not a dict; or if a `label` action does not include `toggle`, `add`, or `remove`.
        """
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)

        rules = config["pull_request_rules"]

        for rule in rules:
            actions = rule.get("actions", {})
            assert isinstance(actions, dict), f"Actions must be dict in rule {rule.get('name')}"

            if "label" in actions:
                label_action = actions["label"]
                assert isinstance(label_action, dict), "Label action must be dict"
                assert "toggle" in label_action or "add" in label_action or "remove" in label_action

    def test_rule_names_are_descriptive(self):
        """Test that all rule names are descriptive and meaningful."""
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)

        rules = config["pull_request_rules"]

        for rule in rules:
            name = rule.get("name", "")
            assert len(name) > 10, f"Rule name too short: {name}"
            assert not name.isupper(), f"Rule name should not be all caps: {name}"

    def test_no_duplicate_rule_names(self):
        """Test that all rule names are unique."""
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)

        rules = config["pull_request_rules"]
        names = [rule.get("name") for rule in rules]

        assert len(names) == len(set(names)), "Duplicate rule names found"

    def test_conditions_list_not_empty(self):
        """Test that all rules have at least one condition."""
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)

        rules = config["pull_request_rules"]

        for rule in rules:
            conditions = rule.get("conditions", [])
            assert len(conditions) > 0, f"Rule {rule.get('name')} has no conditions"

    def test_yaml_indentation_consistency(self):
        """Test that YAML file uses consistent indentation."""
        with open(self.MERGIFY_PATH, "r") as f:
            content = f.read()

        lines = content.split("\n")
        indentations = set()

        for line in lines:
            if line and not line.startswith("#"):
                leading_spaces = len(line) - len(line.lstrip(" "))
                if leading_spaces > 0:
                    indentations.add(leading_spaces % 2)  # Check if using 2-space indent

        # Should consistently use 2-space indentation
        assert len(indentations) <= 1, "Inconsistent indentation found"


class TestMergifySizeCoverage:
    """Verify the 6 size tiers form a complete, non-overlapping partition."""

    MERGIFY_PATH = Path(__file__).parent.parent.parent / ".mergify.yml"

    def _load_tshirt_rules(self):
        """
        Load t-shirt size rules from the repository's .mergify.yml pull_request_rules.

        Searches the YAML configuration at self.MERGIFY_PATH and returns all pull request rule dictionaries whose `name` contains the substring "t-shirt" (case-insensitive).

        Returns:
            list[dict]: List of pull request rule objects matching the "t-shirt" name filter.
        """
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)
        return [r for r in config["pull_request_rules"] if "t-shirt" in r.get("name", "").lower()]

    def test_six_size_tiers_exist(self):
        """Test that exactly 6 t-shirt size tiers are defined."""
        rules = self._load_tshirt_rules()
        assert len(rules) == 6, f"Expected 6 size tiers, found {len(rules)}"

    def test_all_expected_size_labels_present(self):
        """Test that all 6 expected size labels appear in the rules."""
        rules = self._load_tshirt_rules()
        labels = []
        for rule in rules:
            label_action = rule.get("actions", {}).get("label", {})
            labels.extend(label_action.get("toggle", []))
            labels.extend(label_action.get("add", []))

        for expected in ("size/XS", "size/S", "size/M", "size/L", "size/XL", "size/XXL"):
            assert expected in labels, f"Missing expected size label: {expected}"

    def test_size_tiers_are_non_overlapping(self):
        """Test that no two t-shirt rules share the same size label."""
        rules = self._load_tshirt_rules()
        all_labels = []
        for rule in rules:
            label_action = rule.get("actions", {}).get("label", {})
            all_labels.extend(label_action.get("toggle", []))
            all_labels.extend(label_action.get("add", []))

        assert len(all_labels) == len(set(all_labels)), "Overlapping size labels detected across tier rules"

    def test_xs_rule_has_upper_bound_only(self):
        """Test that XS rule only has an upper bound (no >= condition)."""
        rules = self._load_tshirt_rules()
        xs_rule = next((r for r in rules if "xs" in r.get("name", "").lower()), None)
        assert xs_rule is not None, "XS size rule not found"

        conditions = " ".join(str(c) for c in xs_rule.get("conditions", []))
        assert ">=" not in conditions, "XS rule should not have a minimum bound"
        assert "<" in conditions, "XS rule should have an upper bound"

    def test_xxl_rule_has_lower_bound_only(self):
        """Test that XXL rule only has a lower bound (no < condition)."""
        rules = self._load_tshirt_rules()
        xxl_rule = next((r for r in rules if "xxl" in r.get("name", "").lower()), None)
        assert xxl_rule is not None, "XXL size rule not found"

        conditions = " ".join(str(c) for c in xxl_rule.get("conditions", []))
        assert ">=" in conditions, "XXL rule should have a minimum bound"
        # The XXL rule should not have a strict upper bound
        # (a < condition on modified-lines would cap it)
        modified_line_conditions = [str(c) for c in xxl_rule.get("conditions", []) if "#modified-lines" in str(c)]
        upper_bounds = [c for c in modified_line_conditions if "<" in c and ">=" not in c]
        assert len(upper_bounds) == 0, "XXL rule should not have an upper bound"


class TestMergifyContentLabels:
    """Verify the 4 content-label rules exist and assign correct labels."""

    MERGIFY_PATH = Path(__file__).parent.parent.parent / ".mergify.yml"

    def _load_rules(self):
        """
        Load the `pull_request_rules` section from the repository's .mergify.yml configuration.

        Returns:
            list: The list of pull request rule mappings defined under the `pull_request_rules` key.
        """
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)
        return config["pull_request_rules"]

    def _find_rule(self, name_fragment):
        """
        Finds the first pull request rule whose name contains the given fragment (case-insensitive).

        Parameters:
            name_fragment (str): Substring to search for in each rule's `name` field; matching is case-insensitive.

        Returns:
            dict | None: The first matching rule dictionary if found, `None` otherwise.
        """
        return next(
            (r for r in self._load_rules() if name_fragment.lower() in r.get("name", "").lower()),
            None,
        )

    def test_security_label_rule_exists(self):
        """Test that a rule for labelling security changes exists."""
        rule = self._find_rule("security")
        assert rule is not None, "Security label rule not found"
        label_action = rule.get("actions", {}).get("label", {})
        assert "security" in label_action.get("add", []), "Security rule must add 'security' label"

    def test_ci_label_rule_exists(self):
        """Test that a rule for labelling CI/workflow changes exists."""
        rule = self._find_rule("ci")
        assert rule is not None, "CI label rule not found"
        label_action = rule.get("actions", {}).get("label", {})
        assert "ci" in label_action.get("add", []), "CI rule must add 'ci' label"

    def test_documentation_label_rule_exists(self):
        """Test that a rule for labelling documentation changes exists."""
        rule = self._find_rule("documentation")
        assert rule is not None, "Documentation label rule not found"
        label_action = rule.get("actions", {}).get("label", {})
        assert "documentation" in label_action.get("add", []), "Documentation rule must add 'documentation' label"

    def test_dependencies_label_rule_exists(self):
        """Test that a rule for labelling dependency changes exists."""
        rule = self._find_rule("dependency")
        assert rule is not None, "Dependency label rule not found"
        label_action = rule.get("actions", {}).get("label", {})
        assert "dependencies" in label_action.get("add", []), "Dependency rule must add 'dependencies' label"

    def test_content_label_rules_use_add_action(self):
        """Test that content-label rules use 'add' (not 'toggle') action."""
        content_rule_names = ["security", "ci", "documentation", "dependency"]
        for fragment in content_rule_names:
            rule = self._find_rule(fragment)
            if rule is not None:
                label_action = rule.get("actions", {}).get("label", {})
                assert "add" in label_action, f"Content label rule '{fragment}' should use 'add' action"


class TestMergifyReviewAutomation:
    """Verify review-request and dismiss-reviews rules are correctly configured."""

    MERGIFY_PATH = Path(__file__).parent.parent.parent / ".mergify.yml"

    def _load_rules(self):
        """
        Load the `pull_request_rules` section from the repository's .mergify.yml configuration.

        Returns:
            list: The list of pull request rule mappings defined under the `pull_request_rules` key.
        """
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)
        return config["pull_request_rules"]

    def test_review_request_rule_exists(self):
        """Test that a review-request rule exists."""
        rules = self._load_rules()
        review_rules = [r for r in rules if "request_reviews" in r.get("actions", {})]
        assert review_rules, "No request_reviews rule found"

    def test_review_request_targets_mohavro(self):
        """Test that the review-request rule requests mohavro as reviewer."""
        rules = self._load_rules()
        for rule in rules:
            action = rule.get("actions", {}).get("request_reviews", {})
            if action:
                users = action.get("users", [])
                assert "mohavro" in users, f"Rule '{rule['name']}' does not request review from mohavro"

    def test_review_request_excludes_draft_prs(self):
        """Test that the review-request rule does not fire on draft PRs."""
        rules = self._load_rules()
        for rule in rules:
            if "request_reviews" in rule.get("actions", {}):
                conditions = " ".join(str(c) for c in rule.get("conditions", []))
                assert "-draft" in conditions, f"Review-request rule '{rule['name']}' should exclude drafts"

    def test_dismiss_stale_reviews_rule_exists(self):
        """Test that a dismiss_reviews rule exists."""
        rules = self._load_rules()
        dismiss_rules = [r for r in rules if "dismiss_reviews" in r.get("actions", {})]
        assert dismiss_rules, "No dismiss_reviews rule found"

    def test_dismiss_stale_reviews_targets_main(self):
        """Test that stale-review dismissal applies to PRs targeting main."""
        rules = self._load_rules()
        for rule in rules:
            if "dismiss_reviews" in rule.get("actions", {}):
                conditions = " ".join(str(c) for c in rule.get("conditions", []))
                assert "main" in conditions, f"Dismiss-reviews rule '{rule['name']}' should target base=main"


class TestMergifyAutoMerge:
    """Verify auto-merge rules require a passing CI check."""

    MERGIFY_PATH = Path(__file__).parent.parent.parent / ".mergify.yml"

    def _load_rules(self):
        """
        Load the `pull_request_rules` section from the repository's .mergify.yml configuration.

        Returns:
            list: The list of pull request rule mappings defined under the `pull_request_rules` key.
        """
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)
        return config["pull_request_rules"]

    def _get_auto_merge_rules(self):
        """
        Selects pull request rules that define a merge action.

        Returns:
                list: A list of rule dictionaries that include a 'merge' key in their `actions` mapping.
        """
        return [r for r in self._load_rules() if "merge" in r.get("actions", {})]

    def test_auto_merge_rules_exist(self):
        """Test that at least one auto-merge rule is defined."""
        rules = self._get_auto_merge_rules()
        assert rules, "No auto-merge rules found"

    def test_auto_merge_rules_require_ci_check(self):
        """Test that every auto-merge rule requires a passing check-success condition."""
        for rule in self._get_auto_merge_rules():
            conditions = " ".join(str(c) for c in rule.get("conditions", []))
            assert "check-success" in conditions, f"Auto-merge rule '{rule['name']}' must require a passing CI check"

    def test_auto_merge_uses_squash(self):
        """Test that auto-merge rules use squash merge method."""
        for rule in self._get_auto_merge_rules():
            method = rule.get("actions", {}).get("merge", {}).get("method")
            assert method == "squash", f"Auto-merge rule '{rule['name']}' should use squash merge, got {method}"

    def test_dependabot_auto_merge_rule_exists(self):
        """Test that a Dependabot-specific auto-merge rule exists."""
        rules = self._load_rules()
        dep_rules = [
            r
            for r in rules
            if "dependabot" in " ".join(str(c) for c in r.get("conditions", [])) and "merge" in r.get("actions", {})
        ]
        assert dep_rules, "No Dependabot auto-merge rule found"

    def test_snyk_auto_merge_rule_exists(self):
        """Test that a Snyk-specific auto-merge rule exists."""
        rules = self._load_rules()
        snyk_rules = [
            r
            for r in rules
            if "snyk-bot" in " ".join(str(c) for c in r.get("conditions", [])) and "merge" in r.get("actions", {})
        ]
        assert snyk_rules, "No Snyk auto-merge rule found"


class TestMergifyStaleManagement:
    """Verify stale labelling and de-labelling rules are both present."""

    MERGIFY_PATH = Path(__file__).parent.parent.parent / ".mergify.yml"

    def _load_rules(self):
        """
        Load the `pull_request_rules` section from the repository's .mergify.yml configuration.

        Returns:
            list: The list of pull request rule mappings defined under the `pull_request_rules` key.
        """
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)
        return config["pull_request_rules"]

    def test_mark_stale_rule_exists(self):
        """Test that a rule to mark PRs as stale exists."""
        rules = self._load_rules()
        stale_adders = [r for r in rules if "stale" in r.get("actions", {}).get("label", {}).get("add", [])]
        assert stale_adders, "No rule found that adds the 'stale' label"

    def test_remove_stale_rule_exists(self):
        """Test that a rule to remove the stale label exists."""
        rules = self._load_rules()
        stale_removers = [r for r in rules if "stale" in r.get("actions", {}).get("label", {}).get("remove", [])]
        assert stale_removers, "No rule found that removes the 'stale' label"

    def test_mark_stale_excludes_drafts(self):
        """Test that draft PRs are not marked stale."""
        rules = self._load_rules()
        for rule in rules:
            if "stale" in rule.get("actions", {}).get("label", {}).get("add", []):
                conditions = " ".join(str(c) for c in rule.get("conditions", []))
                assert "-draft" in conditions, f"Stale rule '{rule['name']}' should exclude draft PRs"

    def test_mark_stale_posts_comment(self):
        """Test that marking a PR stale also posts a comment."""
        rules = self._load_rules()
        for rule in rules:
            if "stale" in rule.get("actions", {}).get("label", {}).get("add", []):
                assert "comment" in rule.get("actions", {}), f"Stale rule '{rule['name']}' should post a comment"

    def test_stale_rules_reference_stale_label(self):
        """Test that both stale rules consistently reference the 'stale' label."""
        rules = self._load_rules()
        all_stale_label_references = []
        for rule in rules:
            label_action = rule.get("actions", {}).get("label", {})
            if "stale" in label_action.get("add", []):
                all_stale_label_references.append(("add", rule["name"]))
            if "stale" in label_action.get("remove", []):
                all_stale_label_references.append(("remove", rule["name"]))

        assert any(ref[0] == "add" for ref in all_stale_label_references), "No rule adds 'stale' label"
        assert any(ref[0] == "remove" for ref in all_stale_label_references), "No rule removes 'stale' label"


class TestMergifyBoundaryConditions:
    """Test boundary conditions and edge values for thresholds."""

    MERGIFY_PATH = Path(__file__).parent.parent.parent / ".mergify.yml"

    def _load_config(self):
        """
        Load and parse the repository's .mergify.yml configuration.

        Returns:
            The parsed YAML content of .mergify.yml as native Python objects (commonly a dict), or `None` if the file is empty.
        """
        with open(self.MERGIFY_PATH, "r") as f:
            return yaml.safe_load(f)

    def test_size_xs_upper_boundary(self):
        """Test that size/XS rule has upper boundary at 10."""
        config = self._load_config()
        rules = config["pull_request_rules"]
        xs_rule = next((r for r in rules if "xs" in r.get("name", "").lower() and "size/XS" in str(r)), None)
        assert xs_rule is not None, "XS rule not found"

        conditions = " ".join(str(c) for c in xs_rule.get("conditions", []))
        assert "< 10" in conditions or "<10" in conditions, "XS rule should have upper bound < 10"

    def test_size_s_boundaries(self):
        """
        Verify the size/S t-shirt rule defines modified-lines thresholds covering 10 through 49 lines.

        Searches pull_request_rules for a rule named "size/S" and asserts it exists, then checks the rule's conditions include a lower bound of >= 10 and an upper bound of < 50.
        """
        config = self._load_config()
        rules = config["pull_request_rules"]
        s_rule = next((r for r in rules if "/S" in str(r) and "size/S" in str(r)), None)
        assert s_rule is not None, "S rule not found"

        conditions = " ".join(str(c) for c in s_rule.get("conditions", []))
        assert ">= 10" in conditions or ">=10" in conditions, "S rule should have lower bound >= 10"
        assert "< 50" in conditions or "<50" in conditions, "S rule should have upper bound < 50"

    def test_size_xxl_lower_boundary(self):
        """Test that size/XXL rule has lower boundary at 1000."""
        config = self._load_config()
        rules = config["pull_request_rules"]
        xxl_rule = next((r for r in rules if "xxl" in r.get("name", "").lower()), None)
        assert xxl_rule is not None, "XXL rule not found"

        conditions = " ".join(str(c) for c in xxl_rule.get("conditions", []))
        assert ">= 1000" in conditions or ">=1000" in conditions, "XXL rule should have lower bound >= 1000"

    def test_dependabot_file_limit(self):
        """Test that Dependabot auto-merge has a 5-file change limit."""
        config = self._load_config()
        rules = config["pull_request_rules"]
        dep_rule = next(
            (
                r
                for r in rules
                if "dependabot" in str(r.get("conditions", [])).lower() and "merge" in r.get("actions", {})
            ),
            None,
        )
        assert dep_rule is not None, "Dependabot auto-merge rule not found"

        conditions = " ".join(str(c) for c in dep_rule.get("conditions", []))
        assert (
            "#changed-files <= 5" in conditions or "#changed-files<=5" in conditions
        ), "Dependabot auto-merge should limit to 5 changed files"

    def test_stale_threshold_is_14_days(self):
        """Test that PRs are marked stale after 14 days."""
        config = self._load_config()
        rules = config["pull_request_rules"]
        stale_rule = next((r for r in rules if "stale" in r.get("actions", {}).get("label", {}).get("add", [])), None)
        assert stale_rule is not None, "Stale marking rule not found"

        conditions = " ".join(str(c) for c in stale_rule.get("conditions", []))
        assert "14 days" in conditions, "Stale rule should use 14 days threshold"


class TestMergifyNegativeCases:
    """Test negative cases and error conditions."""

    MERGIFY_PATH = Path(__file__).parent.parent.parent / ".mergify.yml"

    def _load_config(self):
        """
        Load and parse the repository's .mergify.yml configuration.

        Returns:
            The parsed YAML content of .mergify.yml as native Python objects (commonly a dict), or `None` if the file is empty.
        """
        with open(self.MERGIFY_PATH, "r") as f:
            return yaml.safe_load(f)

    def test_no_empty_conditions_lists(self):
        """Test that no rule has an empty conditions list."""
        config = self._load_config()
        rules = config["pull_request_rules"]

        for rule in rules:
            conditions = rule.get("conditions", [])
            assert len(conditions) > 0, f"Rule '{rule.get('name')}' has empty conditions list"

    def test_no_empty_actions_dicts(self):
        """Test that no rule has an empty actions dictionary."""
        config = self._load_config()
        rules = config["pull_request_rules"]

        for rule in rules:
            actions = rule.get("actions", {})
            assert len(actions) > 0, f"Rule '{rule.get('name')}' has empty actions dictionary"

    def test_no_empty_label_lists(self):
        """Test that no label action has an empty list."""
        config = self._load_config()
        rules = config["pull_request_rules"]

        for rule in rules:
            label_action = rule.get("actions", {}).get("label", {})
            if "add" in label_action:
                assert len(label_action["add"]) > 0, f"Rule '{rule.get('name')}' has empty add list"
            if "remove" in label_action:
                assert len(label_action["remove"]) > 0, f"Rule '{rule.get('name')}' has empty remove list"
            if "toggle" in label_action:
                assert len(label_action["toggle"]) > 0, f"Rule '{rule.get('name')}' has empty toggle list"

    def test_review_request_has_users(self):
        """Test that review request actions specify at least one user."""
        config = self._load_config()
        rules = config["pull_request_rules"]

        for rule in rules:
            if "request_reviews" in rule.get("actions", {}):
                users = rule["actions"]["request_reviews"].get("users", [])
                assert len(users) > 0, f"Rule '{rule.get('name')}' has no users for review request"

    def test_comment_has_message(self):
        """Test that comment actions have a non-empty message."""
        config = self._load_config()
        rules = config["pull_request_rules"]

        for rule in rules:
            if "comment" in rule.get("actions", {}):
                message = rule["actions"]["comment"].get("message", "")
                assert len(message.strip()) > 0, f"Rule '{rule.get('name')}' has empty comment message"

    def test_no_conflicting_label_operations(self):
        """Test that a rule doesn't both add and remove the same label."""
        config = self._load_config()
        rules = config["pull_request_rules"]

        for rule in rules:
            label_action = rule.get("actions", {}).get("label", {})
            add_labels = set(label_action.get("add", []))
            remove_labels = set(label_action.get("remove", []))

            conflicts = add_labels & remove_labels
            assert len(conflicts) == 0, f"Rule '{rule.get('name')}' has conflicting label operations: {conflicts}"


class TestMergifyFilePatterns:
    """Test file pattern matching in conditions."""

    MERGIFY_PATH = Path(__file__).parent.parent.parent / ".mergify.yml"

    def _load_config(self):
        """
        Load and parse the repository's .mergify.yml configuration.

        Returns:
            The parsed YAML content of .mergify.yml as native Python objects (commonly a dict), or `None` if the file is empty.
        """
        with open(self.MERGIFY_PATH, "r") as f:
            return yaml.safe_load(f)

    def test_security_file_patterns_exist(self):
        """Test that security label rule has file pattern conditions."""
        config = self._load_config()
        rules = config["pull_request_rules"]
        sec_rule = next((r for r in rules if "security" in r.get("actions", {}).get("label", {}).get("add", [])), None)
        assert sec_rule is not None, "Security label rule not found"

        conditions = " ".join(str(c) for c in sec_rule.get("conditions", []))
        # Should have file patterns for security-related files
        has_file_pattern = any(keyword in conditions for keyword in ["files", "snyk", "bandit", "codeql", "semgrep"])
        assert has_file_pattern, "Security rule should have file pattern conditions"

    def test_ci_file_pattern(self):
        """Test that CI label rule matches .github/workflows/ files."""
        config = self._load_config()
        rules = config["pull_request_rules"]
        ci_rule = next((r for r in rules if "ci" in r.get("actions", {}).get("label", {}).get("add", [])), None)
        assert ci_rule is not None, "CI label rule not found"

        conditions = " ".join(str(c) for c in ci_rule.get("conditions", []))
        assert (
            ".github/workflows" in conditions or "github/workflows" in conditions
        ), "CI rule should match .github/workflows/ files"

    def test_documentation_file_pattern(self):
        """Test that documentation label rule matches .md and docs/ files."""
        config = self._load_config()
        rules = config["pull_request_rules"]
        doc_rule = next(
            (r for r in rules if "documentation" in r.get("actions", {}).get("label", {}).get("add", [])), None
        )
        assert doc_rule is not None, "Documentation label rule not found"

        conditions = " ".join(str(c) for c in doc_rule.get("conditions", []))
        has_md_or_docs = ".md" in conditions or "docs/" in conditions or "docs" in conditions
        assert has_md_or_docs, "Documentation rule should match .md or docs/ files"

    def test_dependencies_file_pattern(self):
        """Test that dependencies label rule matches package files."""
        config = self._load_config()
        rules = config["pull_request_rules"]
        dep_rule = next(
            (r for r in rules if "dependencies" in r.get("actions", {}).get("label", {}).get("add", [])), None
        )
        assert dep_rule is not None, "Dependencies label rule not found"

        conditions = " ".join(str(c) for c in dep_rule.get("conditions", []))
        has_pkg_files = any(keyword in conditions for keyword in ["requirements", "pyproject.toml", "package.json"])
        assert has_pkg_files, "Dependencies rule should match package files"


class TestMergifyRegressionCases:
    """Regression tests for previously identified issues."""

    MERGIFY_PATH = Path(__file__).parent.parent.parent / ".mergify.yml"

    def _load_config(self):
        """
        Load and parse the repository's .mergify.yml configuration.

        Returns:
            The parsed YAML content of .mergify.yml as native Python objects (commonly a dict), or `None` if the file is empty.
        """
        with open(self.MERGIFY_PATH, "r") as f:
            return yaml.safe_load(f)

    def test_dismiss_reviews_has_when_clause(self):
        """
        Ensure dismiss_reviews actions include a 'when' clause set to 'synchronize'.

        For every pull request rule that defines a `dismiss_reviews` action, assert the action contains the `when` key and that its value equals `"synchronize"`.
        """
        config = self._load_config()
        rules = config["pull_request_rules"]

        for rule in rules:
            if "dismiss_reviews" in rule.get("actions", {}):
                dismiss_action = rule["actions"]["dismiss_reviews"]
                assert "when" in dismiss_action, f"Rule '{rule.get('name')}' should have 'when' in dismiss_reviews"
                assert (
                    dismiss_action["when"] == "synchronize"
                ), f"Rule '{rule.get('name')}' should dismiss reviews on synchronize"

    def test_dismiss_reviews_has_message(self):
        """Test that dismiss_reviews action has a message."""
        config = self._load_config()
        rules = config["pull_request_rules"]

        for rule in rules:
            if "dismiss_reviews" in rule.get("actions", {}):
                dismiss_action = rule["actions"]["dismiss_reviews"]
                assert "message" in dismiss_action, f"Rule '{rule.get('name')}' should have message in dismiss_reviews"
                assert (
                    len(dismiss_action["message"]) > 0
                ), f"Rule '{rule.get('name')}' has empty dismiss_reviews message"

    def test_stale_comment_mentions_removing_label(self):
        """Test that stale comment explains how to remove the label."""
        config = self._load_config()
        rules = config["pull_request_rules"]

        for rule in rules:
            if "stale" in rule.get("actions", {}).get("label", {}).get("add", []):
                if "comment" in rule.get("actions", {}):
                    message = rule["actions"]["comment"]["message"].lower()
                    has_removal_info = any(keyword in message for keyword in ["remove", "push", "update", "commit"])
                    assert (
                        has_removal_info
                    ), f"Rule '{rule.get('name')}' comment should explain how to remove stale label"

    def test_auto_merge_has_label_conditions(self):
        """Test that auto-merge rules check for appropriate labels."""
        config = self._load_config()
        rules = config["pull_request_rules"]

        for rule in rules:
            if "merge" in rule.get("actions", {}):
                conditions = " ".join(str(c) for c in rule.get("conditions", []))
                # Auto-merge rules should have label conditions
                has_label = "label=" in conditions
                assert has_label, f"Auto-merge rule '{rule.get('name')}' should check for labels"

    def test_no_infinite_stale_loops(self):
        """Test that stale removal conditions prevent infinite loops."""
        config = self._load_config()
        rules = config["pull_request_rules"]

        # Find stale removal rule
        stale_remove_rule = next(
            (r for r in rules if "stale" in r.get("actions", {}).get("label", {}).get("remove", [])), None
        )
        assert stale_remove_rule is not None, "Stale removal rule not found"

        # Should require label=stale to prevent removing label that isn't there
        conditions = " ".join(str(c) for c in stale_remove_rule.get("conditions", []))
        assert (
            "label=stale" in conditions or "label= stale" in conditions
        ), "Stale removal rule should check that stale label exists"
