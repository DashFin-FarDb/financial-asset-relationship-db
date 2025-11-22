"""
Comprehensive validation tests for .github/pr-agent-config.yml

This test suite validates the PR Agent configuration file to ensure it contains
valid settings, proper structure, and no deprecated or conflicting options.
Tests the configuration after removal of context chunking features.
"""

import pytest
import yaml
from pathlib import Path
from typing import Any, Dict


CONFIG_FILE = Path(__file__).parent.parent.parent / ".github" / "pr-agent-config.yml"


@pytest.fixture
def config_content() -> Dict[str, Any]:
    """Load pr-agent-config.yml content."""
    if not CONFIG_FILE.exists():
        pytest.skip("pr-agent-config.yml not found")
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


@pytest.fixture
def config_lines() -> list:
    """Get config file as list of lines."""
    if not CONFIG_FILE.exists():
        pytest.skip("pr-agent-config.yml not found")
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return f.readlines()


class TestPRAgentConfigStructure:
    """Test suite for PR Agent configuration structure."""
    
    def test_config_file_exists(self):
        """Test that pr-agent-config.yml exists."""
        assert CONFIG_FILE.exists(), "pr-agent-config.yml should exist"
    
    def test_config_valid_yaml(self):
        """Test that config file contains valid YAML."""
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            try:
                yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML syntax: {e}")
    
    def test_config_not_empty(self, config_content: Dict[str, Any]):
        """Test that config file is not empty."""
        assert config_content, "Configuration should not be empty"
    
    def test_has_agent_section(self, config_content: Dict[str, Any]):
        """Test that config has an 'agent' section."""
        assert 'agent' in config_content, "Config should have 'agent' section"
    
    def test_agent_has_required_fields(self, config_content: Dict[str, Any]):
        """Test that agent section has required fields."""
        agent = config_content.get('agent', {})
        assert 'name' in agent, "Agent should have 'name' field"
        assert 'version' in agent, "Agent should have 'version' field"
        assert 'enabled' in agent, "Agent should have 'enabled' field"


class TestPRAgentConfigValues:
    """Test suite for PR Agent configuration values."""
    
    def test_agent_name_is_string(self, config_content: Dict[str, Any]):
        """Test that agent name is a non-empty string."""
        agent_name = config_content.get('agent', {}).get('name')
        assert isinstance(agent_name, str), "Agent name should be a string"
        assert len(agent_name) > 0, "Agent name should not be empty"
    
    def test_agent_version_format(self, config_content: Dict[str, Any]):
        """Test that agent version follows semantic versioning."""
        version = config_content.get('agent', {}).get('version')
        assert isinstance(version, str), "Version should be a string"
        
        # Should match semver pattern (major.minor.patch)
        import re
        semver_pattern = r'^\d+\.\d+\.\d+$'
        assert re.match(semver_pattern, version), (
            f"Version '{version}' should follow semantic versioning (e.g., '1.0.0')"
        )
    
    def test_agent_enabled_is_boolean(self, config_content: Dict[str, Any]):
        """Test that enabled field is a boolean."""
        enabled = config_content.get('agent', {}).get('enabled')
        assert isinstance(enabled, bool), "Enabled field should be a boolean"
    
    def test_monitoring_check_interval_reasonable(self, config_content: Dict[str, Any]):
        """Test that monitoring check interval is reasonable (not too frequent)."""
        monitoring = config_content.get('monitoring', {})
        if 'check_interval' in monitoring:
            interval = monitoring['check_interval']
            assert isinstance(interval, int), "Check interval should be an integer"
            assert interval >= 60, "Check interval should be at least 60 seconds"
            assert interval <= 86400, "Check interval should be at most 24 hours"
    
    def test_timeout_values_reasonable(self, config_content: Dict[str, Any]):
        """Test that timeout values are reasonable."""
        monitoring = config_content.get('monitoring', {})
        if 'timeout' in monitoring:
            timeout = monitoring['timeout']
            assert isinstance(timeout, int), "Timeout should be an integer"
            assert timeout >= 30, "Timeout should be at least 30 seconds"
            assert timeout <= 3600, "Timeout should be at most 1 hour"


class TestPRAgentConfigContextRemoval:
    """Test suite validating context chunking features were properly removed."""
    
    def test_no_context_section(self, config_content: Dict[str, Any]):
        """Test that context configuration section was removed."""
        agent = config_content.get('agent', {})
        assert 'context' not in agent, (
            "Agent should not have 'context' section after context chunking removal"
        )
    
    def test_no_chunking_settings(self, config_content: Dict[str, Any]):
        """Test that chunking-related settings were removed."""
        config_str = yaml.dump(config_content)
        
        chunking_keywords = ['chunk', 'chunking', 'max_tokens', 'overlap_tokens']
        found_keywords = [kw for kw in chunking_keywords if kw in config_str.lower()]
        
        assert len(found_keywords) == 0, (
            f"Config should not contain chunking keywords: {found_keywords}"
        )
    
    def test_no_tiktoken_references(self, config_content: Dict[str, Any]):
        """Test that tiktoken references were removed."""
        config_str = yaml.dump(config_content).lower()
        assert 'tiktoken' not in config_str, "Config should not reference tiktoken"
    
    def test_no_summarization_settings(self, config_content: Dict[str, Any]):
        """Test that summarization settings were removed."""
        config_str = yaml.dump(config_content).lower()
        assert 'summarization' not in config_str, "Config should not have summarization settings"


class TestPRAgentConfigTriggers:
    """Test suite for comment parsing triggers."""
    
    def test_has_comment_parsing_section(self, config_content: Dict[str, Any]):
        """Test that config has comment parsing configuration."""
        assert 'comment_parsing' in config_content, "Config should have comment_parsing section"
    
    def test_triggers_are_list(self, config_content: Dict[str, Any]):
        """Test that triggers are defined as a list."""
        triggers = config_content.get('comment_parsing', {}).get('triggers', [])
        assert isinstance(triggers, list), "Triggers should be a list"
    
    def test_triggers_are_strings(self, config_content: Dict[str, Any]):
        """Test that all triggers are strings."""
        triggers = config_content.get('comment_parsing', {}).get('triggers', [])
        for trigger in triggers:
            assert isinstance(trigger, str), f"Trigger '{trigger}' should be a string"
    
    def test_has_reasonable_number_of_triggers(self, config_content: Dict[str, Any]):
        """Test that there are a reasonable number of triggers (not too many or too few)."""
        triggers = config_content.get('comment_parsing', {}).get('triggers', [])
        assert len(triggers) >= 2, "Should have at least 2 triggers defined"
        assert len(triggers) <= 20, "Should not have more than 20 triggers (likely misconfigured)"
    
    def test_triggers_not_empty_strings(self, config_content: Dict[str, Any]):
        """Test that no trigger is an empty string."""
        triggers = config_content.get('comment_parsing', {}).get('triggers', [])
        for trigger in triggers:
            assert len(trigger.strip()) > 0, "Triggers should not be empty strings"


class TestPRAgentConfigPriorityKeywords:
    """Test suite for priority keyword configuration."""
    
    def test_has_priority_keywords(self, config_content: Dict[str, Any]):
        """Test that priority keywords are defined."""
        comment_parsing = config_content.get('comment_parsing', {})
        if 'priority_keywords' in comment_parsing:
            keywords = comment_parsing['priority_keywords']
            assert isinstance(keywords, dict), "Priority keywords should be a dict"
    
    def test_priority_levels_valid(self, config_content: Dict[str, Any]):
        """Test that priority levels are valid (high, medium, low)."""
        priority_keywords = config_content.get('comment_parsing', {}).get('priority_keywords', {})
        valid_levels = {'high', 'medium', 'low'}
        
        for level in priority_keywords.keys():
            assert level in valid_levels, (
                f"Priority level '{level}' should be one of: {valid_levels}"
            )
    
    def test_priority_keywords_are_lists(self, config_content: Dict[str, Any]):
        """Test that each priority level contains a list of keywords."""
        priority_keywords = config_content.get('comment_parsing', {}).get('priority_keywords', {})
        
        for level, keywords in priority_keywords.items():
            assert isinstance(keywords, list), (
                f"Keywords for priority '{level}' should be a list"
            )
            assert len(keywords) > 0, (
                f"Priority level '{level}' should have at least one keyword"
            )


class TestPRAgentConfigActions:
    """Test suite for actions configuration."""
    
    def test_has_actions_section(self, config_content: Dict[str, Any]):
        """Test that config has actions section."""
        assert 'actions' in config_content, "Config should have 'actions' section"
    
    def test_auto_acknowledge_is_boolean(self, config_content: Dict[str, Any]):
        """Test that auto_acknowledge is a boolean if present."""
        actions = config_content.get('actions', {})
        if 'auto_acknowledge' in actions:
            assert isinstance(actions['auto_acknowledge'], bool), (
                "auto_acknowledge should be a boolean"
            )


class TestPRAgentConfigLimits:
    """Test suite for rate limits and constraints."""
    
    def test_rate_limits_reasonable(self, config_content: Dict[str, Any]):
        """Test that rate limits are reasonable if defined."""
        limits = config_content.get('limits', {})
        
        if 'rate_limit_requests' in limits:
            rate_limit = limits['rate_limit_requests']
            assert isinstance(rate_limit, int), "Rate limit should be an integer"
            assert rate_limit > 0, "Rate limit should be positive"
            assert rate_limit <= 10000, "Rate limit seems unreasonably high"
    
    def test_max_concurrent_prs_reasonable(self, config_content: Dict[str, Any]):
        """Test that max concurrent PRs is reasonable."""
        limits = config_content.get('limits', {})
        
        if 'max_concurrent_prs' in limits:
            max_prs = limits['max_concurrent_prs']
            assert isinstance(max_prs, int), "Max concurrent PRs should be an integer"
            assert max_prs >= 1, "Should allow at least 1 concurrent PR"
            assert max_prs <= 50, "More than 50 concurrent PRs seems unreasonable"
    
    def test_no_obsolete_limit_settings(self, config_content: Dict[str, Any]):
        """Test that obsolete limit settings (from context chunking) were removed."""
        limits = config_content.get('limits', {})
        
        obsolete_settings = [
            'max_files_per_chunk',
            'max_diff_lines',
            'max_comment_length',
            'fallback'
        ]
        
        found_obsolete = [s for s in obsolete_settings if s in limits]
        assert len(found_obsolete) == 0, (
            f"Obsolete limit settings found: {found_obsolete}. "
            "These should have been removed with context chunking."
        )


class TestPRAgentConfigConsistency:
    """Test suite for configuration consistency and best practices."""
    
    def test_no_hardcoded_secrets(self, config_content: Dict[str, Any]):
        """Test that config doesn't contain hardcoded secrets or tokens."""
        config_str = str(config_content).lower()
        
        secret_patterns = ['password', 'secret', 'token', 'api_key', 'apikey']
        
        for pattern in secret_patterns:
            if pattern in config_str:
                # Make sure it's just a key name, not a value
                config_lines = yaml.dump(config_content).split('\n')
                for line in config_lines:
                    if pattern in line.lower() and ':' in line:
                        key, value = line.split(':', 1)
                        value_stripped = value.strip()
                        # Value should be empty, null, or a placeholder
                        if value_stripped and value_stripped not in ['null', '""', "''"]:
                            # Check if it's just a reference or placeholder
                            assert any(placeholder in value_stripped for placeholder in ['${{', 'example', 'your_']), (
                                f"Potential hardcoded secret in line: {line}"
                            )
    
    def test_config_follows_yaml_best_practices(self, config_lines: list):
        """Test that config file follows YAML best practices."""
        content = ''.join(config_lines)
        
        # Should have comments
        assert '#' in content, "Config should have explanatory comments"
        
        # Should not have tabs (YAML requires spaces)
        assert '\t' not in content, "Config should use spaces, not tabs"
    
    def test_config_version_is_current(self, config_content: Dict[str, Any]):
        """Test that config version is 1.0.0 (after context chunking removal)."""
        version = config_content.get('agent', {}).get('version')
        assert version == '1.0.0', (
            f"Config version should be '1.0.0' after context chunking removal, got '{version}'"
        )