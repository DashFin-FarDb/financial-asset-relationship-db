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
            if isinstance(action_config, dict) and "type" in action_config:
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

class TestPRAgentConfigEdgeCases:
    """Test suite for edge cases in PR agent configuration."""
    
    def test_config_version_is_semantic(self):
        """Test that version follows semantic versioning."""
        config = load_config()
        version = config.get('agent', {}).get('version', '')
        
        # Should match semver pattern (X.Y.Z)
        import re
        semver_pattern = r'^\d+\.\d+\.\d+$'
        assert re.match(semver_pattern, version), (
            f"Version '{version}' does not follow semantic versioning (X.Y.Z)"
        )
    
    def test_config_has_no_version_1_1_references(self):
        """Test that config doesn't reference removed 1.1.0 features."""
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should not mention version 1.1.0 (rolled back to 1.0.0)
        assert '1.1.0' not in content, (
            "Config should not reference version 1.1.0 (simplified to 1.0.0)"
        )
    
    def test_config_monitoring_intervals_are_reasonable(self):
        """Test that monitoring intervals are within reasonable bounds."""
        config = load_config()
        monitoring = config.get('monitoring', {})
        
        # Check check_interval (30 minutes = 1800 seconds)
        check_interval = monitoring.get('check_interval', 0)
        assert 300 <= check_interval <= 7200, (
            f"check_interval {check_interval}s should be between 5min and 2hr"
        )
        
        # Check timeout (5 minutes = 300 seconds)
        timeout = monitoring.get('timeout', 0)
        assert 60 <= timeout <= 1800, (
            f"timeout {timeout}s should be between 1min and 30min"
        )
        
        # Timeout should be less than check_interval
        assert timeout < check_interval, (
            "timeout should be less than check_interval to prevent overlaps"
        )
    
    def test_config_max_retries_is_reasonable(self):
        """Test that max_retries is set to a reasonable value."""
        config = load_config()
        max_retries = config.get('monitoring', {}).get('max_retries', 0)
        
        assert 1 <= max_retries <= 10, (
            f"max_retries {max_retries} should be between 1 and 10"
        )
    
    def test_config_coverage_thresholds_are_valid(self):
        """Test that code coverage thresholds are valid percentages."""
        config = load_config()
        quality = config.get('quality', {})
        
        python_cov = quality.get('python', {}).get('min_coverage', 0)
        typescript_cov = quality.get('typescript', {}).get('min_coverage', 0)
        
        assert 0 <= python_cov <= 100, (
            f"Python min_coverage {python_cov} must be 0-100"
        )
        assert 0 <= typescript_cov <= 100, (
            f"TypeScript min_coverage {typescript_cov} must be 0-100"
        )
        
        # Should be reasonable thresholds (not too low, not 100%)
        assert python_cov >= 70, "Python coverage threshold should be at least 70%"
        assert typescript_cov >= 60, "TypeScript coverage threshold should be at least 60%"
    
    def test_config_max_line_length_matches_quality_settings(self):
        """Test that max_line_length is consistent with linter settings."""
        config = load_config()
        max_line_length = config.get('quality', {}).get('general', {}).get('max_line_length', 0)
        
        # Should match black's default (88) or be close
        assert max_line_length in [80, 88, 100, 120], (
            f"max_line_length {max_line_length} should be a standard value "
            "(80, 88, 100, or 120)"
        )
    
    def test_config_priority_keywords_are_comprehensive(self):
        """Test that priority keywords cover common review scenarios."""
        config = load_config()
        priorities = config.get('comment_parsing', {}).get('priority_keywords', {})
        
        assert 'high' in priorities, "Should have 'high' priority keywords"
        assert 'medium' in priorities, "Should have 'medium' priority keywords"
        assert 'low' in priorities, "Should have 'low' priority keywords"
        
        # High priority should include security keywords
        high_keywords = [k.lower() for k in priorities.get('high', [])]
        assert 'security' in high_keywords, "High priority should include 'security'"
        assert 'critical' in high_keywords, "High priority should include 'critical'"
    
    def test_config_triggers_are_strings(self):
        """Test that all triggers are string values."""
        config = load_config()
        triggers = config.get('comment_parsing', {}).get('triggers', [])
        
        assert isinstance(triggers, list), "triggers should be a list"
        for trigger in triggers:
            assert isinstance(trigger, str), (
                f"All triggers should be strings, found {type(trigger)}"
            )
            assert len(trigger) > 0, "Triggers should not be empty strings"
    
    def test_config_ignore_patterns_are_valid(self):
        """Test that ignore patterns are valid strings."""
        config = load_config()
        patterns = config.get('comment_parsing', {}).get('ignore_patterns', [])
        
        assert isinstance(patterns, list), "ignore_patterns should be a list"
        for pattern in patterns:
            assert isinstance(pattern, str), (
                f"All ignore patterns should be strings, found {type(pattern)}"
            )


class TestPRAgentConfigSimplificationValidation:
    """Test suite validating that configuration simplifications were properly applied."""
    
    def test_config_no_context_section(self):
        """Test that config doesn't contain context management section."""
        config = load_config()
        
        # Agent section should not have context subsection
        agent = config.get('agent', {})
        assert 'context' not in agent, (
            "Config should not have agent.context section (simplified)"
        )
    
    def test_config_no_chunking_settings(self):
        """Test that config doesn't contain chunking settings."""
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should not contain chunking-related terms
        chunking_terms = ['chunking', 'chunk_size', 'overlap_tokens', 'max_tokens']
        for term in chunking_terms:
            assert term not in content, (
                f"Config should not contain '{term}' (chunking was removed)"
            )
    
    def test_config_no_summarization_settings(self):
        """Test that config doesn't contain summarization settings."""
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'summarization' not in content, (
            "Config should not contain summarization settings (simplified)"
        )
        assert 'max_summary_tokens' not in content, (
            "Config should not contain max_summary_tokens (simplified)"
        )
    
    def test_config_no_context_limits(self):
        """Test that limits section doesn't contain context processing limits."""
        config = load_config()
        limits = config.get('limits', {})
        
        # Should not have context-specific limits
        assert 'max_files_per_chunk' not in limits, (
            "limits should not have max_files_per_chunk (simplified)"
        )
        assert 'max_diff_lines' not in limits, (
            "limits should not have max_diff_lines (simplified)"
        )
        assert 'max_comment_length' not in limits, (
            "limits should not have max_comment_length (simplified)"
        )
    
    def test_config_no_fallback_strategies(self):
        """Test that limits section doesn't contain fallback strategies."""
        config = load_config()
        limits = config.get('limits', {})
        
        assert 'fallback' not in limits, (
            "limits should not have fallback section (simplified)"
        )
    
    def test_config_structure_is_flat(self):
        """Test that config structure is simpler without deep nesting."""
        config = load_config()
        
        # Check maximum nesting depth
        def max_depth(d, current_depth=1):
            if not isinstance(d, dict):
                return current_depth
            if not d:
                return current_depth
            return max(max_depth(v, current_depth + 1) for v in d.values())
        
        depth = max_depth(config)
        assert depth <= 4, (
            f"Config nesting depth {depth} is too deep. "
            "Simplified config should have depth <= 4"
        )


class TestPRAgentConfigNegativeScenarios:
    """Test suite for negative scenarios in PR agent configuration."""
    
    def test_config_with_invalid_version_format(self, tmp_path):
        """Test detection of invalid version format."""
        invalid_config = tmp_path / "config.yml"
        invalid_config.write_text("""
agent:
  name: "Test"
  version: "invalid.version.format.with.extra.parts"
  enabled: true
""")
        
        config = yaml.safe_load(open(invalid_config))
        version = config['agent']['version']
        
        import re
        assert not re.match(r'^\d+\.\d+\.\d+$', version), (
            "Test setup: version should be invalid"
        )
    
    def test_config_with_negative_timeout(self, tmp_path):
        """Test detection of negative timeout values."""
        invalid_config = tmp_path / "config.yml"
        invalid_config.write_text("""
monitoring:
  timeout: -100
""")
        
        config = yaml.safe_load(open(invalid_config))
        timeout = config['monitoring']['timeout']
        assert timeout < 0, "Test setup: timeout should be negative"
    
    def test_config_with_coverage_over_100(self, tmp_path):
        """Test detection of invalid coverage thresholds."""
        invalid_config = tmp_path / "config.yml"
        invalid_config.write_text("""
quality:
  python:
    min_coverage: 150
""")
        
        config = yaml.safe_load(open(invalid_config))
        coverage = config['quality']['python']['min_coverage']
        assert coverage > 100, "Test setup: coverage should be > 100"
    
    def test_config_with_empty_triggers_list(self, tmp_path):
        """Test detection of empty triggers list."""
        invalid_config = tmp_path / "config.yml"
        invalid_config.write_text("""
comment_parsing:
  triggers: []
""")
        
        config = yaml.safe_load(open(invalid_config))
        triggers = config['comment_parsing']['triggers']
        assert len(triggers) == 0, "Test setup: triggers should be empty"


class TestPRAgentConfigConsistency:
    """Test suite for internal consistency in PR agent configuration."""
    
    def test_config_tool_names_match_quality_section(self):
        """Test that tool names are consistent between quality sections."""
        config = load_config()
        quality = config.get('quality', {})
        
        # Check Python tools
        python = quality.get('python', {})
        assert python.get('linter') == 'flake8', "Should use flake8 for Python linting"
        assert python.get('formatter') == 'black', "Should use black for Python formatting"
        assert python.get('test_runner') == 'pytest', "Should use pytest for Python tests"
        
        # Check TypeScript tools
        typescript = quality.get('typescript', {})
        assert typescript.get('linter') == 'eslint', "Should use eslint for TypeScript linting"
        assert typescript.get('test_runner') == 'jest', "Should use jest for TypeScript tests"
    
    def test_config_commit_templates_follow_conventional_commits(self):
        """Test that commit templates follow conventional commit format."""
        config = load_config()
        templates = config.get('git', {}).get('commit_templates', {})
        
        # Check common commit types
        for commit_type in ['fix', 'feat']:
            if commit_type in templates:
                template = templates[commit_type]
                assert template.startswith(f"{commit_type}:"), (
                    f"Commit template for '{commit_type}' should start with '{commit_type}:'"
                )
                assert '{description}' in template, (
                    f"Commit template for '{commit_type}' should include {{description}} placeholder"
                )
    
    def test_config_require_approval_files_are_critical(self):
        """Test that require_approval_for includes critical files."""
        config = load_config()
        require_approval = config.get('actions', {}).get('require_approval_for', [])
        
        # Should include critical configuration files
        critical_files = [
            'package.json',
            'requirements.txt',
            'Dockerfile',
        ]
        
        for critical_file in critical_files:
            assert any(critical_file in path for path in require_approval), (
                f"Should require approval for changes to {critical_file}"
            )
    
    def test_config_max_changes_limits_are_consistent(self):
        """Test that max changes limits are logically consistent."""
        config = load_config()
        actions = config.get('actions', {})
        
        max_changes = actions.get('max_changes_per_pr', 0)
        max_files = actions.get('max_files_per_commit', 0)
        
        # max_files_per_commit should be less than max_changes_per_pr
        if max_changes > 0 and max_files > 0:
            assert max_files <= max_changes, (
                f"max_files_per_commit ({max_files}) should be <= "
                f"max_changes_per_pr ({max_changes})"
            )


class TestPRAgentConfigEdgeCasesAdditional:
    """Additional edge case tests for PR agent configuration."""
    
    def test_config_version_follows_semver(self):
        """Test that version follows semantic versioning format."""
        config = load_pr_agent_config()
        version = config.get('agent', {}).get('version', '')
        
        import re
        semver_pattern = r'^\d+\.\d+\.\d+$'
        assert re.match(semver_pattern, version), (
            f"Version '{version}' should follow semantic versioning (X.Y.Z)"
        )
    
    def test_config_no_version_1_1_0_references(self):
        """Test that config doesn't reference removed 1.1.0 features."""
        with open(PR_AGENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert '1.1.0' not in content, (
            "Config should not reference version 1.1.0 (simplified to 1.0.0)"
        )
    
    def test_config_monitoring_intervals_reasonable(self):
        """Test that monitoring intervals are within reasonable bounds."""
        config = load_pr_agent_config()
        monitoring = config.get('monitoring', {})
        
        check_interval = monitoring.get('check_interval', 0)
        assert 300 <= check_interval <= 7200, (
            f"check_interval {check_interval}s should be 5min-2hr"
        )
        
        timeout = monitoring.get('timeout', 0)
        assert 60 <= timeout <= 1800, (
            f"timeout {timeout}s should be 1min-30min"
        )
        
        assert timeout < check_interval, (
            "timeout should be less than check_interval"
        )
    
    def test_config_coverage_thresholds_valid(self):
        """Test that code coverage thresholds are valid percentages."""
        config = load_pr_agent_config()
        quality = config.get('quality', {})
        
        if 'python' in quality and 'min_coverage' in quality['python']:
            python_cov = quality['python']['min_coverage']
            assert 0 <= python_cov <= 100
            assert python_cov >= 70, "Python coverage should be >= 70%"
        
        if 'typescript' in quality and 'min_coverage' in quality['typescript']:
            typescript_cov = quality['typescript']['min_coverage']
            assert 0 <= typescript_cov <= 100
            assert typescript_cov >= 60, "TypeScript coverage should be >= 60%"


class TestPRAgentConfigSimplificationValidationAdditional:
    """Additional tests validating configuration simplifications."""
    
    def test_config_no_context_section(self):
        """Test that config doesn't have context management section."""
        config = load_pr_agent_config()
        agent = config.get('agent', {})
        
        assert 'context' not in agent, (
            "Config should not have agent.context section (simplified)"
        )
    
    def test_config_no_chunking_terms(self):
        """Test that config doesn't contain chunking-related terms."""
        with open(PR_AGENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        chunking_terms = ['chunking', 'chunk_size', 'overlap_tokens', 'max_tokens']
        for term in chunking_terms:
            assert term not in content, (
                f"Config should not contain '{term}' (chunking removed)"
            )
    
    def test_config_no_summarization_settings(self):
        """Test that config doesn't contain summarization settings."""
        with open(PR_AGENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'summarization' not in content
        assert 'max_summary_tokens' not in content
    
    def test_config_no_fallback_strategies(self):
        """Test that limits section doesn't have fallback strategies."""
        config = load_pr_agent_config()
        limits = config.get('limits', {})
        
        assert 'fallback' not in limits, (
            "limits should not have fallback section (simplified)"
        )
        assert 'max_files_per_chunk' not in limits
        assert 'max_diff_lines' not in limits


class TestPRAgentConfigConsistencyAdditional:
    """Additional internal consistency tests for PR agent configuration."""
    
    def test_config_tool_names_consistent(self):
        """Test that tool names are consistent in quality section."""
        config = load_pr_agent_config()
        quality = config.get('quality', {})
        
        if 'python' in quality:
            python = quality['python']
            if 'linter' in python:
                assert python['linter'] == 'flake8'
            if 'formatter' in python:
                assert python['formatter'] == 'black'
            if 'test_runner' in python:
                assert python['test_runner'] == 'pytest'
        
        if 'typescript' in quality:
            typescript = quality['typescript']
            if 'linter' in typescript:
                assert typescript['linter'] == 'eslint'
            if 'test_runner' in typescript:
                assert typescript['test_runner'] == 'jest'
    
    def test_config_max_changes_limits_logical(self):
        """Test that max changes limits are logically consistent."""
        config = load_pr_agent_config()
        actions = config.get('actions', {})
        
        max_changes = actions.get('max_changes_per_pr', 0)
        max_files = actions.get('max_files_per_commit', 0)
        
        if max_changes > 0 and max_files > 0:
            assert max_files <= max_changes, (
                f"max_files_per_commit ({max_files}) should be <= "
                f"max_changes_per_pr ({max_changes})"
            )


class TestPRAgentConfigEdgeCasesAdditional:
    """Additional edge case tests for PR agent configuration."""
    
    def test_config_version_follows_semver(self):
        """Test that version follows semantic versioning format."""
        config = load_pr_agent_config()
        version = config.get('agent', {}).get('version', '')
        
        import re
        semver_pattern = r'^\d+\.\d+\.\d+$'
        assert re.match(semver_pattern, version), (
            f"Version '{version}' should follow semantic versioning (X.Y.Z)"
        )
    
    def test_config_no_version_1_1_0_references(self):
        """Test that config doesn't reference removed 1.1.0 features."""
        with open(PR_AGENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert '1.1.0' not in content, (
            "Config should not reference version 1.1.0 (simplified to 1.0.0)"
        )
    
    def test_config_monitoring_intervals_reasonable(self):
        """Test that monitoring intervals are within reasonable bounds."""
        config = load_pr_agent_config()
        monitoring = config.get('monitoring', {})
        
        check_interval = monitoring.get('check_interval', 0)
        assert 300 <= check_interval <= 7200, (
            f"check_interval {check_interval}s should be 5min-2hr"
        )
        
        timeout = monitoring.get('timeout', 0)
        assert 60 <= timeout <= 1800, (
            f"timeout {timeout}s should be 1min-30min"
        )
        
        assert timeout < check_interval, (
            "timeout should be less than check_interval"
        )
    
    def test_config_coverage_thresholds_valid(self):
        """Test that code coverage thresholds are valid percentages."""
        config = load_pr_agent_config()
        quality = config.get('quality', {})
        
        if 'python' in quality and 'min_coverage' in quality['python']:
            python_cov = quality['python']['min_coverage']
            assert 0 <= python_cov <= 100
            assert python_cov >= 70, "Python coverage should be >= 70%"
        
        if 'typescript' in quality and 'min_coverage' in quality['typescript']:
            typescript_cov = quality['typescript']['min_coverage']
            assert 0 <= typescript_cov <= 100
            assert typescript_cov >= 60, "TypeScript coverage should be >= 60%"


class TestPRAgentConfigSimplificationValidationAdditional:
    """Additional tests validating configuration simplifications."""
    
    def test_config_no_context_section(self):
        """Test that config doesn't have context management section."""
        config = load_pr_agent_config()
        agent = config.get('agent', {})
        
        assert 'context' not in agent, (
            "Config should not have agent.context section (simplified)"
        )
    
    def test_config_no_chunking_terms(self):
        """Test that config doesn't contain chunking-related terms."""
        with open(PR_AGENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        chunking_terms = ['chunking', 'chunk_size', 'overlap_tokens', 'max_tokens']
        for term in chunking_terms:
            assert term not in content, (
                f"Config should not contain '{term}' (chunking removed)"
            )
    
    def test_config_no_summarization_settings(self):
        """Test that config doesn't contain summarization settings."""
        with open(PR_AGENT_CONFIG_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'summarization' not in content
        assert 'max_summary_tokens' not in content
    
    def test_config_no_fallback_strategies(self):
        """Test that limits section doesn't have fallback strategies."""
        config = load_pr_agent_config()
        limits = config.get('limits', {})
        
        assert 'fallback' not in limits, (
            "limits should not have fallback section (simplified)"
        )
        assert 'max_files_per_chunk' not in limits
        assert 'max_diff_lines' not in limits


class TestPRAgentConfigConsistencyAdditional:
    """Additional internal consistency tests for PR agent configuration."""
    
    def test_config_tool_names_consistent(self):
        """Test that tool names are consistent in quality section."""
        config = load_pr_agent_config()
        quality = config.get('quality', {})
        
        if 'python' in quality:
            python = quality['python']
            if 'linter' in python:
                assert python['linter'] == 'flake8'
            if 'formatter' in python:
                assert python['formatter'] == 'black'
            if 'test_runner' in python:
                assert python['test_runner'] == 'pytest'
        
        if 'typescript' in quality:
            typescript = quality['typescript']
            if 'linter' in typescript:
                assert typescript['linter'] == 'eslint'
            if 'test_runner' in typescript:
                assert typescript['test_runner'] == 'jest'
    
    def test_config_max_changes_limits_logical(self):
        """Test that max changes limits are logically consistent."""
        config = load_pr_agent_config()
        actions = config.get('actions', {})
        
        max_changes = actions.get('max_changes_per_pr', 0)
        max_files = actions.get('max_files_per_commit', 0)
        
        if max_changes > 0 and max_files > 0:
            assert max_files <= max_changes, (
                f"max_files_per_commit ({max_files}) should be <= "
                f"max_changes_per_pr ({max_changes})"
            )