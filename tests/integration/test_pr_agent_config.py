"""
Comprehensive validation tests for PR Agent configuration.

This module validates the pr-agent-config.yml file structure, ensuring
proper configuration after recent simplifications that removed context
chunking features.
"""

import pytest
import yaml
from pathlib import Path
from typing import Any, Dict


PR_AGENT_CONFIG_PATH = Path(__file__).parent.parent.parent / ".github" / "pr-agent-config.yml"


def load_pr_agent_config() -> Dict[str, Any]:
    """
    Load and parse the PR Agent configuration file.
    
    Returns:
        Dict containing the parsed configuration.
    
    Raises:
        FileNotFoundError: If the configuration file doesn't exist.
        yaml.YAMLError: If the YAML is invalid.
    """
    if not PR_AGENT_CONFIG_PATH.exists():
        pytest.skip(f"PR Agent config not found at {PR_AGENT_CONFIG_PATH}")
    
    with open(PR_AGENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


class TestPRAgentConfigStructure:
    """Test the basic structure and required fields of PR Agent configuration."""
    
    def test_config_file_exists(self):
        """Verify the PR Agent configuration file exists."""
        assert PR_AGENT_CONFIG_PATH.exists(), \
            f"PR Agent config file should exist at {PR_AGENT_CONFIG_PATH}"
    
    def test_config_is_valid_yaml(self):
        """Verify the configuration file contains valid YAML."""
        try:
            config = load_pr_agent_config()
            assert config is not None, "Configuration should not be empty"
        except yaml.YAMLError as e:
            pytest.fail(f"Configuration file contains invalid YAML: {e}")
    
    def test_has_agent_section(self):
        """Verify the configuration has an agent section."""
        config = load_pr_agent_config()
        assert "agent" in config, "Configuration must have an 'agent' section"
        assert isinstance(config["agent"], dict), "'agent' section must be a dictionary"
    
    def test_agent_has_required_fields(self):
        """Verify agent section has required fields."""
        config = load_pr_agent_config()
        agent = config.get("agent", {})
        
        required_fields = ["name", "version", "enabled"]
        for field in required_fields:
            assert field in agent, f"Agent section must have '{field}' field"
    
    def test_agent_version_format(self):
        """Verify agent version follows semantic versioning."""
        config = load_pr_agent_config()
        version = config.get("agent", {}).get("version", "")
        
        # Should match X.Y.Z format
        import re
        semver_pattern = r'^\d+\.\d+\.\d+$'
        assert re.match(semver_pattern, version), \
            f"Version '{version}' should follow semantic versioning (X.Y.Z)"
    
    def test_agent_enabled_is_boolean(self):
        """Verify enabled field is a boolean."""
        config = load_pr_agent_config()
        enabled = config.get("agent", {}).get("enabled")
        
        assert isinstance(enabled, bool), \
            f"'enabled' should be a boolean, got {type(enabled).__name__}"


class TestPRAgentConfigMonitoring:
    """Test monitoring configuration section."""
    
    def test_has_monitoring_section(self):
        """Verify monitoring section exists."""
        config = load_pr_agent_config()
        assert "monitoring" in config, "Configuration should have 'monitoring' section"
    
    def test_monitoring_check_interval_is_positive(self):
        """Verify check interval is a positive integer."""
        config = load_pr_agent_config()
        monitoring = config.get("monitoring", {})
        check_interval = monitoring.get("check_interval")
        
        assert isinstance(check_interval, int), \
            "check_interval should be an integer"
        assert check_interval > 0, \
            "check_interval should be positive"
    
    def test_monitoring_interval_is_reasonable(self):
        """Verify monitoring interval is within reasonable bounds (5 min to 24 hours)."""
        config = load_pr_agent_config()
        monitoring = config.get("monitoring", {})
        check_interval = monitoring.get("check_interval", 0)
        
        min_interval = 300  # 5 minutes
        max_interval = 86400  # 24 hours
        
        assert min_interval <= check_interval <= max_interval, \
            f"check_interval ({check_interval}s) should be between {min_interval}s and {max_interval}s"


class TestPRAgentConfigActions:
    """Test action configuration section."""
    
    def test_has_actions_section(self):
        """Verify actions section exists and is a dictionary."""
        config = load_pr_agent_config()
        assert "actions" in config, "Configuration should have 'actions' section"
        assert isinstance(config["actions"], dict), "'actions' should be a dictionary"
    
    def test_action_triggers_are_lists(self):
        """Verify action triggers are defined as lists."""
        config = load_pr_agent_config()
        actions = config.get("actions", {})
        
        for action_name, action_config in actions.items():
            if isinstance(action_config, dict) and "triggers" in action_config:
                assert isinstance(action_config["triggers"], list), \
                    f"Action '{action_name}' triggers should be a list"
    
    def test_actions_have_valid_types(self):
        """Verify each action has a valid type field."""
        config = load_pr_agent_config()
        actions = config.get("actions", {})
        
        valid_types = ["review", "comment", "label", "merge", "test"]
        
        for action_name, action_config in actions.items():
            if "type" in action_config:
                action_type = action_config["type"]
                assert action_type in valid_types, \
                    f"Action '{action_name}' has invalid type '{action_type}'"


class TestPRAgentConfigReviewSettings:
    """Test review-related configuration."""
    
    def test_review_settings_exist(self):
        """Verify review settings are present."""
        config = load_pr_agent_config()
        assert "review" in config, "Configuration should have 'review' section"
    
    def test_auto_review_is_boolean(self):
        """Verify auto_review setting is a boolean if present."""
        config = load_pr_agent_config()
        review = config.get("review", {})
        
        if "auto_review" in review:
            assert isinstance(review["auto_review"], bool), \
                "auto_review should be a boolean"
    
    def test_approval_count_is_valid(self):
        """Verify required approval count is a positive integer."""
        config = load_pr_agent_config()
        review = config.get("review", {})
        
        if "required_approvals" in review:
            approvals = review["required_approvals"]
            assert isinstance(approvals, int), \
                "required_approvals should be an integer"
            assert approvals > 0, \
                "required_approvals should be positive"
            assert approvals <= 10, \
                "required_approvals should be reasonable (<= 10)"


class TestPRAgentConfigLabels:
    """Test label configuration."""
    
    def test_labels_section_structure(self):
        """Verify labels section has proper structure."""
        config = load_pr_agent_config()
        
        if "labels" in config:
            labels = config["labels"]
            assert isinstance(labels, (dict, list)), \
                "labels should be a dictionary or list"
    
    def test_label_definitions_are_valid(self):
        """Verify label definitions contain required fields."""
        config = load_pr_agent_config()
        
        if "labels" in config and isinstance(config["labels"], dict):
            for label_name, label_config in config["labels"].items():
                if isinstance(label_config, dict):
                    # Label config should have color and/or description
                    assert "color" in label_config or "description" in label_config, \
                        f"Label '{label_name}' should have color or description"


class TestPRAgentConfigLimits:
    """Test rate limits and resource constraints."""
    
    def test_has_limits_section(self):
        """Verify limits section exists."""
        config = load_pr_agent_config()
        assert "limits" in config, "Configuration should have 'limits' section"
    
    def test_concurrent_prs_limit_is_positive(self):
        """Verify max concurrent PRs is a positive integer."""
        config = load_pr_agent_config()
        limits = config.get("limits", {})
        
        if "max_concurrent_prs" in limits:
            max_prs = limits["max_concurrent_prs"]
            assert isinstance(max_prs, int), \
                "max_concurrent_prs should be an integer"
            assert max_prs > 0, \
                "max_concurrent_prs should be positive"
    
    def test_rate_limit_is_reasonable(self):
        """Verify rate limit is within reasonable bounds."""
        config = load_pr_agent_config()
        limits = config.get("limits", {})
        
        if "rate_limit_requests" in limits:
            rate_limit = limits["rate_limit_requests"]
            assert isinstance(rate_limit, int), \
                "rate_limit_requests should be an integer"
            assert 1 <= rate_limit <= 5000, \
                f"rate_limit_requests ({rate_limit}) should be between 1 and 5000"


class TestPRAgentConfigNoObsoleteFields:
    """Test that obsolete configuration fields have been removed."""
    
    def test_no_context_chunking_config(self):
        """Verify context chunking configuration has been removed."""
        config = load_pr_agent_config()
        agent = config.get("agent", {})
        
        # These fields should NOT exist after simplification
        obsolete_fields = ["context"]
        
        for field in obsolete_fields:
            assert field not in agent, \
                f"Obsolete field 'agent.{field}' should be removed from configuration"
    
    def test_no_chunking_limits(self):
        """Verify chunking-related limits have been removed."""
        config = load_pr_agent_config()
        limits = config.get("limits", {})
        
        obsolete_limit_fields = [
            "max_files_per_chunk",
            "max_diff_lines",
            "max_comment_length",
            "fallback"
        ]
        
        for field in obsolete_limit_fields:
            assert field not in limits, \
                f"Obsolete field 'limits.{field}' should be removed from configuration"


class TestPRAgentConfigConsistency:
    """Test internal consistency of configuration."""
    
    def test_no_duplicate_keys(self):
        """Verify configuration has no duplicate YAML keys."""
        if not PR_AGENT_CONFIG_PATH.exists():
            pytest.skip("PR Agent config not found")
        
        with open(PR_AGENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Use custom loader to detect duplicates
        duplicates = []
        
        class DuplicateKeySafeLoader(yaml.SafeLoader):
            pass
        
        def constructor_with_dup_check(loader, node):
            mapping = {}
            for key_node, value_node in node.value:
                key = loader.construct_object(key_node, deep=False)
                if key in mapping:
                    duplicates.append(key)
                mapping[key] = loader.construct_object(value_node, deep=False)
            return mapping
        
        DuplicateKeySafeLoader.add_constructor(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            constructor_with_dup_check
        )
        
        try:
            yaml.load(content, Loader=DuplicateKeySafeLoader)
        except yaml.YAMLError:
            pass
        
        assert len(duplicates) == 0, \
            f"Configuration has duplicate keys: {', '.join(duplicates)}"
    
    def test_config_follows_yaml_best_practices(self):
        """Verify configuration follows YAML best practices."""
        if not PR_AGENT_CONFIG_PATH.exists():
            pytest.skip("PR Agent config not found")
        
        with open(PR_AGENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for common YAML anti-patterns
        lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            # Check for tabs (should use spaces)
            assert '\t' not in line, \
                f"Line {i} contains tabs; use spaces for indentation"
            
            # Check for trailing whitespace
            if line.rstrip() != line and line.strip():  # Allow empty lines
                pytest.fail(f"Line {i} has trailing whitespace")


class TestPRAgentConfigFilePermissions:
    """Test file permissions and accessibility."""
    
    def test_config_file_is_readable(self):
        """Verify configuration file is readable."""
        assert PR_AGENT_CONFIG_PATH.exists(), \
            "Configuration file should exist"
        assert PR_AGENT_CONFIG_PATH.is_file(), \
            "Configuration path should be a file"
        
        # Try to read the file
        try:
            with open(PR_AGENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
                f.read()
        except PermissionError:
            pytest.fail("Configuration file is not readable")
    
    def test_config_file_size_is_reasonable(self):
        """Verify configuration file size is reasonable (not too large or empty)."""
        if not PR_AGENT_CONFIG_PATH.exists():
            pytest.skip("PR Agent config not found")
        
        file_size = PR_AGENT_CONFIG_PATH.stat().st_size
        
        assert file_size > 0, "Configuration file should not be empty"
        assert file_size < 1_000_000, \
            "Configuration file should be less than 1MB"


class TestPRAgentConfigDocumentation:
    """Test configuration documentation and comments."""
    
    def test_config_has_comments(self):
        """Verify configuration file has explanatory comments."""
        if not PR_AGENT_CONFIG_PATH.exists():
            pytest.skip("PR Agent config not found")
        
        with open(PR_AGENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Count comment lines
        comment_lines = [line for line in content.split('\n') if line.strip().startswith('#')]
        
        assert len(comment_lines) > 0, \
            "Configuration should have explanatory comments"
    
    def test_config_sections_are_documented(self):
        """Verify major sections have documentation comments."""
        if not PR_AGENT_CONFIG_PATH.exists():
            pytest.skip("PR Agent config not found")
        
        with open(PR_AGENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for section markers (comments before major sections)
        major_sections = ["agent", "monitoring", "actions", "review", "limits"]
        
        for section in major_sections:
            # Look for the section in the file
            if f"{section}:" in content:
                # Verify there's a comment near this section
                section_index = content.find(f"{section}:")
                preceding_content = content[max(0, section_index - 200):section_index]
                
                has_comment = '#' in preceding_content
                assert has_comment, \
                    f"Section '{section}' should have explanatory comments"