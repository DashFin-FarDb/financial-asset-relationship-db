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
        tshirt_rule = next(
            (r for r in rules if "t-shirt" in r.get("name", "").lower()), None
        )

        assert tshirt_rule is not None, "T-shirt size rule not found"
        assert "name" in tshirt_rule
        assert "conditions" in tshirt_rule
        assert "actions" in tshirt_rule

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

        # Check for modified-lines conditions
        has_min_lines = any("#modified-lines >=" in str(c) for c in conditions)
        has_max_lines = any("#modified-lines <" in str(c) for c in conditions)
        assert has_min_lines, "Missing minimum modified-lines condition"
        assert has_max_lines, "Missing maximum modified-lines condition"

    def test_tshirt_rule_has_label_action(self):
        """Test that t-shirt size rule has label action."""
        with open(self.MERGIFY_PATH, "r") as f:
            config = yaml.safe_load(f)

        rules = config["pull_request_rules"]
        tshirt_rule = next(
            (r for r in rules if "t-shirt" in r.get("name", "").lower()), None
        )

        actions = tshirt_rule.get("actions", {})
        assert "label" in actions, "Missing label action"

        label_action = actions["label"]
        assert "toggle" in label_action, "Missing toggle in label action"
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
