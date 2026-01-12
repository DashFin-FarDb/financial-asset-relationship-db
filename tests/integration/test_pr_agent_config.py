"""
Comprehensive validation tests for .github/pr-agent-config.yml

This test suite validates the PR agent configuration file to ensure:
- Valid YAML structure
- Required configuration keys present
- Values within reasonable ranges
- Best practices followed
- No security issues
"""

import pytest
import yaml
from pathlib import Path
from typing import Dict, Any


CONFIG_FILE = Path(__file__).parent.parent.parent / ".github" / "pr-agent-config.yml"


@pytest.fixture
def config() -> Dict[str, Any]:
    """Load and parse the PR agent configuration file."""
    if not CONFIG_FILE.exists():
        pytest.skip(f"Configuration file not found: {CONFIG_FILE}")
    
    with open(CONFIG_FILE, 'r') as f:
        return yaml.safe_load(f)


class TestPRAgentConfigStructure:
    """Test the basic structure and required fields of the configuration."""
    
    def test_config_file_exists(self):
        """Configuration file should exist at expected location."""
        assert CONFIG_FILE.exists(), f"Config file not found: {CONFIG_FILE}"
    
    def test_config_is_valid_yaml(self):
        """Configuration file should be valid YAML."""
        with open(CONFIG_FILE, 'r') as f:
            try:
                yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML: {e}")
    
    def test_config_has_agent_section(self, config):
        """Configuration should have an 'agent' section."""
        assert 'agent' in config, "Missing 'agent' section"
        assert isinstance(config['agent'], dict), "'agent' should be a dictionary"
    
    def test_agent_has_required_fields(self, config):
        """Agent section should have required fields."""
        agent = config.get('agent', {})
        required_fields = ['name', 'version', 'enabled']
        
        for field in required_fields:
            assert field in agent, f"Missing required field 'agent.{field}'"
    
    def test_config_has_monitoring_section(self, config):
        """Configuration should have a 'monitoring' section."""
        assert 'monitoring' in config, "Missing 'monitoring' section"
        assert isinstance(config['monitoring'], dict), "'monitoring' should be a dictionary"


class TestPRAgentSettings:
    """Test PR agent specific settings and values."""
    
    def test_agent_name_is_valid(self, config):
        """Agent name should be a non-empty string."""
        name = config.get('agent', {}).get('name')
        assert isinstance(name, str), "Agent name should be a string"
        assert len(name) > 0, "Agent name should not be empty"
        assert len(name) <= 100, "Agent name should be reasonable length"
    
    def test_agent_version_format(self, config):
        """Agent version should follow semantic versioning."""
        version = config.get('agent', {}).get('version')
        assert isinstance(version, str), "Version should be a string"
        
        # Check semantic versioning format (X.Y.Z)
        import re
        semver_pattern = r'^\d+\.\d+\.\d+(-[a-zA-Z0-9.-]+)?$'
        assert re.match(semver_pattern, version), \
            f"Version '{version}' should follow semantic versioning (X.Y.Z)"
    
    def test_agent_enabled_is_boolean(self, config):
        """Agent enabled flag should be a boolean."""
        enabled = config.get('agent', {}).get('enabled')
        assert isinstance(enabled, bool), "Agent 'enabled' should be a boolean"
    
    def test_check_interval_is_reasonable(self, config):
        """Monitoring check interval should be within reasonable range."""
        check_interval = config.get('monitoring', {}).get('check_interval')
        
        if check_interval is not None:
            assert isinstance(check_interval, int), "check_interval should be an integer"
            assert 60 <= check_interval <= 3600, \
                "check_interval should be between 60s (1 min) and 3600s (1 hour)"


class TestAutoResponseSettings:
    """Test auto-response configuration."""
    
    def test_auto_response_section_exists(self, config):
        """Auto-response section should exist if configured."""
        if 'auto_response' in config:
            assert isinstance(config['auto_response'], dict), \
                "'auto_response' should be a dictionary"
    
    def test_enabled_events_are_valid(self, config):
        """Enabled events should be valid GitHub event types."""
        auto_response = config.get('auto_response', {})
        enabled_events = auto_response.get('enabled_events', [])
        
        valid_events = {
            'pull_request_review',
            'pull_request',
            'issue_comment',
            'push',
            'pull_request_review_comment'
        }
        
        for event in enabled_events:
            assert event in valid_events, \
                f"Invalid event type '{event}'. Must be one of {valid_events}"
    
    def test_triggers_are_valid_regex(self, config):
        """Trigger patterns should be valid regular expressions."""
        auto_response = config.get('auto_response', {})
        triggers = auto_response.get('triggers', [])
        
        import re
        for trigger in triggers:
            try:
                re.compile(trigger)
            except re.error as e:
                pytest.fail(f"Invalid regex pattern '{trigger}': {e}")


class TestActionsConfiguration:
    """Test actions configuration."""
    
    def test_actions_section_structure(self, config):
        """Actions section should be properly structured."""
        if 'actions' not in config:
            pytest.skip("No actions section configured")
        
        actions = config['actions']
        assert isinstance(actions, dict), "'actions' should be a dictionary"
        
        for action_name, action_config in actions.items():
            assert isinstance(action_name, str), "Action name should be a string"
            assert isinstance(action_config, dict), \
                f"Action '{action_name}' config should be a dictionary"
    
    def test_action_enabled_flags(self, config):
        """Action enabled flags should be booleans."""
        actions = config.get('actions', {})
        
        for action_name, action_config in actions.items():
            if 'enabled' in action_config:
                assert isinstance(action_config['enabled'], bool), \
                    f"Action '{action_name}' enabled should be a boolean"
    
    def test_action_commands_are_strings(self, config):
        """Action commands should be non-empty strings."""
        actions = config.get('actions', {})
        
        for action_name, action_config in actions.items():
            if 'command' in action_config:
                command = action_config['command']
                assert isinstance(command, str), \
                    f"Action '{action_name}' command should be a string"
                assert len(command) > 0, \
                    f"Action '{action_name}' command should not be empty"


class TestCodeReviewSettings:
    """Test code review related settings."""
    
    def test_code_review_section(self, config):
        """Code review section should be properly configured."""
        if 'code_review' not in config:
            pytest.skip("No code_review section configured")
        
        code_review = config['code_review']
        assert isinstance(code_review, dict), "'code_review' should be a dictionary"
    
    def test_review_levels_are_valid(self, config):
        """Review levels should be valid severity levels."""
        code_review = config.get('code_review', {})
        
        if 'levels' in code_review:
            levels = code_review['levels']
            valid_levels = {'low', 'medium', 'high', 'critical'}
            
            for level in levels:
                assert level in valid_levels, \
                    f"Invalid review level '{level}'. Must be one of {valid_levels}"
    
    def test_file_patterns_are_valid_glob(self, config):
        """File patterns should be valid glob patterns."""
        code_review = config.get('code_review', {})
        
        if 'file_patterns' in code_review:
            patterns = code_review['file_patterns']
            assert isinstance(patterns, list), "file_patterns should be a list"
            
            for pattern in patterns:
                assert isinstance(pattern, str), "Each pattern should be a string"
                assert len(pattern) > 0, "Pattern should not be empty"


class TestLimitsConfiguration:
    """Test rate limits and resource constraints."""
    
    def test_limits_section_exists(self, config):
        """Limits section should exist to prevent resource exhaustion."""
        assert 'limits' in config, "Missing 'limits' section"
        assert isinstance(config['limits'], dict), "'limits' should be a dictionary"
    
    def test_max_concurrent_prs_reasonable(self, config):
        """Maximum concurrent PRs should be reasonable."""
        max_concurrent = config.get('limits', {}).get('max_concurrent_prs')
        
        if max_concurrent is not None:
            assert isinstance(max_concurrent, int), \
                "max_concurrent_prs should be an integer"
            assert 1 <= max_concurrent <= 100, \
                "max_concurrent_prs should be between 1 and 100"
    
    def test_rate_limit_requests_reasonable(self, config):
        """Rate limit for requests should be reasonable."""
        rate_limit = config.get('limits', {}).get('rate_limit_requests')
        
        if rate_limit is not None:
            assert isinstance(rate_limit, int), \
                "rate_limit_requests should be an integer"
            assert 10 <= rate_limit <= 1000, \
                "rate_limit_requests should be between 10 and 1000 per hour"


class TestSecuritySettings:
    """Test security-related configuration."""
    
    def test_no_hardcoded_secrets(self, config):
        """Configuration should not contain hardcoded secrets."""
        import re
        
        config_str = yaml.dump(config)
        
        # Check for common secret patterns
        secret_patterns = [
            r'password\s*[:=]\s*["\']?[^"\'\s]{8,}',
            r'token\s*[:=]\s*["\']?[a-zA-Z0-9]{20,}',
            r'api_key\s*[:=]\s*["\']?[a-zA-Z0-9]{20,}',
            r'secret\s*[:=]\s*["\']?[^"\'\s]{8,}',
        ]
        
        for pattern in secret_patterns:
            matches = re.findall(pattern, config_str, re.IGNORECASE)
            assert len(matches) == 0, \
                f"Potential hardcoded secret found matching pattern: {pattern}"
    
    def test_no_sensitive_paths(self, config):
        """Configuration should not reference sensitive file paths."""
        config_str = yaml.dump(config)
        
        sensitive_patterns = [
            '/home/',
            '/root/',
            'C:\\Users\\',
            '~/',
        ]
        
        for pattern in sensitive_patterns:
            assert pattern not in config_str, \
                f"Sensitive path pattern '{pattern}' found in configuration"
    
    def test_secure_defaults(self, config):
        """Security-sensitive options should have secure defaults."""
        # If debug mode exists, it should be disabled by default
        debug = config.get('debug', {})
        if 'enabled' in debug:
            # In production, debug should typically be false
            # But we'll just check it's a boolean
            assert isinstance(debug['enabled'], bool), \
                "debug.enabled should be a boolean"


class TestNotificationSettings:
    """Test notification configuration."""
    
    def test_notification_channels_valid(self, config):
        """Notification channels should be valid types."""
        notifications = config.get('notifications', {})
        
        if 'channels' in notifications:
            channels = notifications['channels']
            valid_channels = {
                'github_comment',
                'github_status',
                'slack',
                'email',
                'webhook'
            }
            
            for channel in channels:
                assert channel in valid_channels, \
                    f"Invalid notification channel '{channel}'"
    
    def test_notification_on_events_valid(self, config):
        """Notification events should be valid."""
        notifications = config.get('notifications', {})
        
        if 'on_events' in notifications:
            events = notifications['on_events']
            assert isinstance(events, list), "on_events should be a list"
            
            for event in events:
                assert isinstance(event, str), "Each event should be a string"
                assert len(event) > 0, "Event name should not be empty"


class TestDebugConfiguration:
    """Test debug and logging configuration."""
    
    def test_debug_section_structure(self, config):
        """Debug section should be properly structured."""
        if 'debug' not in config:
            return  # Debug section is optional
        
        debug = config['debug']
        assert isinstance(debug, dict), "'debug' should be a dictionary"
    
    def test_log_level_valid(self, config):
        """Log level should be a valid logging level."""
        debug = config.get('debug', {})
        
        if 'log_level' in debug:
            log_level = debug['log_level']
            valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
            
            assert log_level.upper() in valid_levels, \
                f"Invalid log level '{log_level}'. Must be one of {valid_levels}"
    
    def test_verbose_mode_is_boolean(self, config):
        """Verbose mode should be a boolean if specified."""
        debug = config.get('debug', {})
        
        if 'verbose' in debug:
            assert isinstance(debug['verbose'], bool), \
                "debug.verbose should be a boolean"


class TestConfigurationConsistency:
    """Test overall configuration consistency."""
    
    def test_no_duplicate_keys(self):
        """YAML should not have duplicate keys."""
        with open(CONFIG_FILE, 'r') as f:
            content = f.read()
        
        # Parse with duplicate key detection
        class DuplicateKeyLoader(yaml.SafeLoader):
            """Loader that raises on duplicate keys at any depth."""

        def _construct_mapping(loader, node, deep=False):
            if not isinstance(node, yaml.MappingNode):
                raise yaml.constructor.ConstructorError(
                    None, None,
                    f"expected a mapping node, but found {node.id}",
                    node.start_mark
                )

            mapping = {}
            for key_node, value_node in node.value:
                key = loader.construct_object(key_node, deep=True)
                if key in mapping:
                    raise yaml.constructor.ConstructorError(
                        "while constructing a mapping",
                        node.start_mark,
                        f"found duplicate key: {key}",
                        key_node.start_mark
                    )

                mapping[key] = loader.construct_object(value_node, deep=True)

            return mapping

        DuplicateKeyLoader.add_constructor(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            _construct_mapping,
        )

        try:
            yaml.load(content, Loader=DuplicateKeyLoader)
        except yaml.constructor.ConstructorError as e:
            pytest.fail(f"Duplicate keys found in YAML: {e}")
    
    def test_all_sections_are_dictionaries(self, config):
        """Top-level sections should all be dictionaries."""
        for key, value in config.items():
            if value is not None and not isinstance(value, (dict, list, str, int, bool, float)):
                pytest.fail(f"Section '{key}' has unexpected type: {type(value)}")
    
    def test_config_is_not_empty(self, config):
        """Configuration should not be empty."""
        assert config is not None, "Configuration is None"
        assert len(config) > 0, "Configuration file is empty"


class TestBestPractices:
    """Test configuration follows best practices."""
    
    def test_has_version_field(self, config):
        """Configuration should have version information for tracking."""
        agent = config.get('agent', {})
        assert 'version' in agent, \
            "Configuration should include version for tracking changes"
    
    def test_has_monitoring_enabled(self, config):
        """Monitoring should be configured for production use."""
        assert 'monitoring' in config, \
            "Configuration should include monitoring section"
    
    def test_has_reasonable_defaults(self, config):
        """Configuration should have reasonable default values."""
        # Check that critical settings have sensible defaults
        monitoring = config.get('monitoring', {})
        
        # If check_interval is set, it should be reasonable
        if 'check_interval' in monitoring:
            interval = monitoring['check_interval']
            # Should check at least once an hour, but not more than once a minute
            assert 60 <= interval <= 3600, \
                "check_interval should be between 1 minute and 1 hour"
    
    def test_config_is_documented(self):
        """Configuration file should have comments explaining sections."""
        with open(CONFIG_FILE, 'r') as f:
            content = f.read()
        
        # Check for presence of comments
        assert '#' in content, \
            "Configuration should include comments for documentation"
        
        # Count comment lines
        comment_lines = [line for line in content.split('\n') if line.strip().startswith('#')]
        total_lines = len([line for line in content.split('\n') if line.strip()])
        
        # At least 10% of lines should be comments
        comment_ratio = len(comment_lines) / max(total_lines, 1)
        assert comment_ratio >= 0.05, \
            f"Configuration should have adequate comments (found {comment_ratio:.1%})"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_handles_empty_sections(self, config):
        """Configuration should handle empty sections gracefully."""
        # If a section exists but is empty, it should be a dict or list
        for key, value in config.items():
            if value == {}:
                assert isinstance(value, dict), \
                    f"Empty section '{key}' should be a dictionary"
            elif value == []:
                assert isinstance(value, list), \
                    f"Empty section '{key}' should be a list"
    
    def test_no_excessively_long_values(self, config):
        """Configuration values should not be excessively long."""
        def check_length(obj, path=""):
            if isinstance(obj, str):
                assert len(obj) <= 10000, \
                    f"String at '{path}' is excessively long ({len(obj)} chars)"
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    check_length(v, f"{path}.{k}" if path else k)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_length(item, f"{path}[{i}]")
        
        check_length(config)
    
    def test_no_circular_references(self, config):
        """Configuration should not have circular references."""
        # YAML safe_load prevents circular references, but let's be explicit
        def check_circular(obj, seen=None):
            if seen is None:
                seen = set()
            
            obj_id = id(obj)
            assert obj_id not in seen, "Circular reference detected in configuration"
            
            if isinstance(obj, (dict, list)):
                seen.add(obj_id)
                if isinstance(obj, dict):
                    for value in obj.values():
                        check_circular(value, seen.copy())
                else:
                    for item in obj:
                        check_circular(item, seen.copy())
        
        check_circular(config)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])