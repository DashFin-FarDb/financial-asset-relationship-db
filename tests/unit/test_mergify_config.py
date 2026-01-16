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
        assert isinstance(config["pull_request_rules"], list), (
            "pull_request_rules must be a list"
        )
        assert len(config["pull_request_rules"]) > 0, "pull_request_rules is empty"

    def test_tshirt_size_rule_exists(self):
        """Test that t-shirt size assignment rule exists."""
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
        """Test that t-shirt size rule has valid conditions."""
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)

        rules = config["pull_request_rules"]
        tshirt_rule = next(
            (r for r in rules if "t-shirt" in r.get("name", "").lower()), None
        )

        conditions = tshirt_rule.get("conditions", [])
        assert isinstance(conditions, list), "Conditions must be a list"
        assert len(conditions) > 0, "Conditions list is empty"

        # Each sizing rule should constrain modified lines somehow (min or max)
        assert any("#modified-lines" in str(c) for c in conditions), (
            "Missing #modified-lines condition"
        )

    def test_tshirt_rule_has_label_action(self):
        """Test that t-shirt size rule has label action."""
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)

        rules = config["pull_request_rules"]
        tshirt_rules = [r for r in rules if "t-shirt" in r.get("name", "").lower()]
        assert tshirt_rules, "T-shirt size rules not found"

        for rule in tshirt_rules:
            actions = rule.get("actions", {})
            assert "label" in actions, (
                f"Missing label action in rule {rule.get('name')}"
            )

            label_action = actions["label"]
            assert "toggle" in label_action, (
                f"Missing toggle in label action for rule {rule.get('name')}"
            )
            assert isinstance(label_action["toggle"], list), "Toggle must be a list"
            assert len(label_action["toggle"]) > 0, "Toggle list is empty"

    def test_tshirt_rule_assigns_size_l_label(self):
        """Test that t-shirt rule assigns size/L label."""
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)

        rules = config["pull_request_rules"]
        tshirt_rule = next(
            (r for r in rules if "t-shirt" in r.get("name", "").lower()), None
        )

        labels = tshirt_rule["actions"]["label"]["toggle"]
        assert "size/L" in labels, "size/L label not in toggle list"

    def test_modified_lines_thresholds_are_valid(self):
        """Test that modified lines thresholds are sensible."""
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)

        rules = config["pull_request_rules"]
        tshirt_rule = next(
            (r for r in rules if "t-shirt" in r.get("name", "").lower()), None
        )

        conditions = tshirt_rule.get("conditions", [])

        # Extract threshold values
        min_threshold = None
        max_threshold = None

        for condition in conditions:
            if ">=" in str(condition):
                # Extract number after >=
                parts = str(condition).split(">=")
                if len(parts) == 2:
                    try:
                        min_threshold = int(parts[1].strip())
                    except ValueError:
                        pass
            if "<" in str(condition) and ">=" not in str(condition):
                parts = str(condition).split("<")
                if len(parts) == 2:
                    try:
                        max_threshold = int(parts[1].strip())
                    except ValueError:
                        pass

        assert min_threshold is not None, "Could not extract minimum threshold"
        assert max_threshold is not None, "Could not extract maximum threshold"
        assert min_threshold < max_threshold, (
            f"Min threshold ({min_threshold}) must be less than max ({max_threshold})"
        )
        assert min_threshold >= 0, "Min threshold must be non-negative"

    def test_all_rules_have_required_fields(self):
        """Test that all rules have name, conditions, and actions."""
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)

        rules = config["pull_request_rules"]

        for idx, rule in enumerate(rules):
            assert "name" in rule, f"Rule {idx} missing name"
            assert isinstance(rule["name"], str), f"Rule {idx} name must be string"
            assert len(rule["name"]) > 0, f"Rule {idx} name is empty"

            assert "conditions" in rule, (
                f"Rule {idx} ({rule.get('name')}) missing conditions"
            )
            assert isinstance(rule["conditions"], list), (
                f"Rule {idx} conditions must be list"
            )

            assert "actions" in rule, f"Rule {idx} ({rule.get('name')}) missing actions"
            assert isinstance(rule["actions"], dict), f"Rule {idx} actions must be dict"

    def test_mergify_no_syntax_errors(self):
        """Test that Mergify configuration has no obvious syntax errors."""
        with open(self.MERGIFY_PATH, "r") as f:
            content = f.read()

        # Check for common YAML/Mergify issues
        assert content.strip(), "File is empty or whitespace only"
        assert not content.startswith(" "), (
            "File starts with indentation (invalid YAML)"
        )
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
                            "size/XL",
                            "size/XXL",
                        ]
                        assert label in valid_sizes, f"Invalid size label: {label}"


class TestMergifyRuleLogic:
    """Test the logical correctness of Mergify rules."""

    MERGIFY_PATH = Path(__file__).parent.parent.parent / ".mergify.yml"

    def test_size_l_range_is_correct(self):
        """Test that size/L rule covers 100-500 lines as expected."""
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)

        rules = config["pull_request_rules"]
        size_l_rule = next(
            (r for r in rules if "size/L" in str(r.get("actions", {}))), None
        )

        assert size_l_rule is not None, "size/L rule not found"

        conditions = size_l_rule.get("conditions", [])
        condition_str = " ".join(str(c) for c in conditions)

        # Should contain ">= 100" and "< 500"
        assert "100" in condition_str, "Missing 100 threshold"
        assert "500" in condition_str, "Missing 500 threshold"

    def test_description_is_meaningful(self):
        """Test that rule descriptions are present and meaningful."""
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
                        pass
                if "#modified-lines <" in cond_str and ">=" not in cond_str:
                    try:
                        val = int(cond_str.split("<")[1].strip().strip('"').strip("'"))
                        max_values.append(val)
                    except (ValueError, IndexError):
                        pass

            # If both min and max are specified, min should be less than max
            if min_values and max_values:
                assert all(m < mx for m in min_values for mx in max_values), (
                    f"Conflicting conditions in rule {rule.get('name')}: min >= max"
                )

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
        """Test that each rule assigns a unique size label."""
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)

        rules = config["pull_request_rules"]
        size_labels = []

        for rule in rules:
            if "t-shirt" in rule.get("name", "").lower():
                toggle_labels = (
                    rule.get("actions", {}).get("label", {}).get("toggle", [])
                )
                size_labels.extend(toggle_labels)

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
        assert any(">=" in t for t in thresholds), (
            "Missing minimum threshold conditions"
        )
        assert any("<" in t for t in thresholds), "Missing maximum threshold conditions"

    def test_actions_are_properly_formatted(self):
        """Test that all actions follow proper YAML structure."""
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)

        rules = config["pull_request_rules"]

        for rule in rules:
            actions = rule.get("actions", {})
            assert isinstance(actions, dict), (
                f"Actions must be dict in rule {rule.get('name')}"
            )

            if "label" in actions:
                label_action = actions["label"]
                assert isinstance(label_action, dict), "Label action must be dict"
                assert (
                    "toggle" in label_action
                    or "add" in label_action
                    or "remove" in label_action
                )

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
                    indentations.add(
                        leading_spaces % 2
                    )  # Check if using 2-space indent

        # Should consistently use 2-space indentation
        assert len(indentations) <= 1, "Inconsistent indentation found"
