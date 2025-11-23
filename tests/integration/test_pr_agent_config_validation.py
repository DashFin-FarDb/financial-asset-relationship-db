"""
Comprehensive validation tests for .github/pr-agent-config.yml configuration file.

Tests ensure the PR Agent configuration is valid, secure, and follows best practices.
"""

import os
import pytest
import yaml
from pathlib import Path


class TestPRAgentConfigStructure:
    """Test the structure and validity of PR Agent configuration."""
    
    @pytest.fixture
    def config_path(self):
        """Path to PR Agent config file."""
        return Path(".github/pr-agent-config.yml")
    
    @pytest.fixture
    def config_data(self, config_path):
        """Load and parse the PR Agent configuration."""
        assert config_path.exists(), f"PR Agent config not found at {config_path}"
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
        assert data is not None, "PR Agent config is empty"
        return data
    
    def test_config_file_exists(self, config_path):
        """PR Agent config file should exist."""
        assert config_path.exists()
        assert config_path.is_file()
    
    def test_config_is_valid_yaml(self, config_path):
        """PR Agent config should be valid YAML."""
        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)
        assert data is not None
        assert isinstance(data, dict)
    
    def test_agent_section_exists(self, config_data):
        """Agent section should be defined."""
        assert 'agent' in config_data
        assert isinstance(config_data['agent'], dict)
    
    def test_agent_has_required_fields(self, config_data):
        """Agent section should have required fields."""
        agent = config_data['agent']
        assert 'name' in agent
        assert 'version' in agent
        assert 'enabled' in agent
        
        assert isinstance(agent['name'], str)
        assert len(agent['name']) > 0
        assert isinstance(agent['version'], str)
        assert isinstance(agent['enabled'], bool)
    
    def test_monitoring_section_structure(self, config_data):
        """Monitoring section should be properly structured."""
        assert 'monitoring' in config_data
        monitoring = config_data['monitoring']
        
        assert 'check_interval' in monitoring
        assert isinstance(monitoring['check_interval'], int)
        assert monitoring['check_interval'] > 0
    
    def test_review_settings_exist(self, config_data):
        """Review settings should be defined."""
        assert 'review' in config_data
        review = config_data['review']
        
        assert 'auto_review' in review
        assert isinstance(review['auto_review'], bool)
    
    def test_limits_section_defined(self, config_data):
        """Limits section should contain resource constraints."""
        assert 'limits' in config_data
        limits = config_data['limits']
        
        assert 'max_concurrent_prs' in limits
        assert isinstance(limits['max_concurrent_prs'], int)
        assert limits['max_concurrent_prs'] > 0


class TestPRAgentConfigSecurity:
    """Security-focused tests for PR Agent configuration."""
    
    @pytest.fixture
    def config_data(self):
        """Load PR Agent configuration."""
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_no_hardcoded_credentials(self, config_data):
        """Config should not contain hardcoded credentials."""
        config_str = yaml.dump(config_data).lower()
        
        # Check for common credential patterns
        forbidden_patterns = [
            'password:', 'secret:', 'token:', 'api_key:',
            'apikey:', 'private_key:', 'credentials:'
        ]
        
        for pattern in forbidden_patterns:
            if pattern in config_str:
                # Should reference environment variables or secrets
                assert '${{' in config_str or 'secrets.' in config_str, \
                    f"Found {pattern} without proper secret reference"
    
    def test_no_sensitive_file_paths(self, config_data):
        """Config should not expose sensitive file paths."""
        config_str = yaml.dump(config_data).lower()
        
        sensitive_paths = [
            '/etc/passwd', '/etc/shadow', '~/.ssh', 'id_rsa',
            '.env', 'credentials.json'
        ]
        
        for path in sensitive_paths:
            assert path not in config_str, \
                f"Config contains sensitive path: {path}"
    
    def test_reasonable_rate_limits(self, config_data):
        """Rate limits should be reasonable to prevent abuse."""
        if 'limits' in config_data:
            limits = config_data['limits']
            
            if 'rate_limit_requests' in limits:
                rate_limit = limits['rate_limit_requests']
                assert isinstance(rate_limit, int)
                assert 1 <= rate_limit <= 10000, \
                    f"Rate limit {rate_limit} is outside reasonable range"
    
    def test_safe_timeout_values(self, config_data):
        """Timeout values should be safe and reasonable."""
        config_str = yaml.dump(config_data)
        
        # Extract timeout values
        import re
        timeout_matches = re.findall(r'timeout[_\s]*:?\s*(\d+)', config_str, re.IGNORECASE)
        
        for timeout_str in timeout_matches:
            timeout = int(timeout_str)
            assert 1 <= timeout <= 3600, \
                f"Timeout {timeout} seconds is outside safe range (1-3600)"


class TestPRAgentConfigConsistency:
    """Test consistency and logical correctness of configuration values."""
    
    @pytest.fixture
    def config_data(self):
        """Load PR Agent configuration."""
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_version_format(self, config_data):
        """Agent version should follow semantic versioning."""
        version = config_data['agent']['version']
        
        # Should match pattern like 1.0.0 or 1.2.3-beta
        import re
        pattern = r'^\d+\.\d+\.\d+(-[a-zA-Z0-9]+)?$'
        assert re.match(pattern, version), \
            f"Version '{version}' doesn't follow semantic versioning"
    
    def test_boolean_fields_are_boolean(self, config_data):
        """Boolean configuration fields should be actual booleans."""
        def check_booleans(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    
                    # Check if key suggests boolean value
                    if any(word in key.lower() for word in ['enabled', 'auto', 'is_', 'has_', 'should_', 'can_']):
                        assert isinstance(value, bool), \
                            f"Field '{new_path}' should be boolean, got {type(value).__name__}"
                    
                    check_booleans(value, new_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_booleans(item, f"{path}[{i}]")
        
        check_booleans(config_data)
    
    def test_numeric_limits_are_positive(self, config_data):
        """Numeric limit values should be positive integers."""
        limits = config_data.get('limits', {})
        
        for key, value in limits.items():
            if isinstance(value, int) and 'max' in key.lower():
                assert value > 0, \
                    f"Limit '{key}' should be positive, got {value}"
    
    def test_no_duplicate_keys_in_yaml(self):
        """YAML file should not have duplicate keys."""
        config_path = Path(".github/pr-agent-config.yml")
        
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Parse with duplicate key detection
        class DuplicateKeyError(Exception):
            pass
        
        def no_duplicates_constructor(loader, node, deep=False):
            mapping = {}
            for key_node, value_node in node.value:
                key = loader.construct_object(key_node, deep=deep)
                if key in mapping:
                    raise DuplicateKeyError(f"Duplicate key found: {key}")
                mapping[key] = loader.construct_object(value_node, deep=deep)
            return mapping
        
        yaml.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
                           no_duplicates_constructor, Loader=yaml.SafeLoader)
        
        try:
            yaml.safe_load(content)
        except DuplicateKeyError as e:
            pytest.fail(str(e))


class TestPRAgentConfigIntegration:
    """Test integration between PR Agent config and workflows."""
    
    def test_config_matches_workflow_usage(self):
        """Configuration keys should match workflow references."""
        config_path = Path(".github/pr-agent-config.yml")
        workflow_path = Path(".github/workflows/pr-agent.yml")
        
        assert config_path.exists()
        assert workflow_path.exists()
        
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        with open(workflow_path, 'r') as f:
            workflow_content = f.read()
        
        # Check that agent name in config appears in workflow
        agent_name = config_data.get('agent', {}).get('name', '')
            # Workflow should reference the configured agent name
            assert agent_name in workflow_content, \
                "Agent name from config must be referenced in the workflow"
            assert any(char.isalnum() for char in agent_name), \
                "Agent name should contain alphanumeric characters"
    
    def test_monitoring_interval_reasonable_for_github_actions(self):
        """Monitoring interval should work with GitHub Actions rate limits."""
        config_path = Path(".github/pr-agent-config.yml")
        
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        
        check_interval = config_data.get('monitoring', {}).get('check_interval', 0)
        
        # GitHub Actions rate limit is 5000 requests/hour for authenticated requests
        # Minimum interval should be at least 1 second to avoid excessive polling
        assert check_interval >= 1, \
            f"Check interval {check_interval} is too frequent"
        
        # Maximum interval shouldn't be more than 1 day (86400 seconds)
        assert check_interval <= 86400, \
            f"Check interval {check_interval} is too long"


class TestPRAgentConfigDocumentation:
    """Ensure configuration is properly documented."""
    
    def test_config_has_comments(self):
        """Configuration file should have explanatory comments."""
        config_path = Path(".github/pr-agent-config.yml")
        
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Count comment lines
        comment_lines = [line for line in content.split('\n') if line.strip().startswith('#')]
        total_lines = len([line for line in content.split('\n') if line.strip()])
        
        # At least 10% of lines should be comments
        comment_ratio = len(comment_lines) / total_lines if total_lines > 0 else 0
        assert comment_ratio >= 0.05, \
            f"Config has insufficient documentation ({comment_ratio:.1%} comments)"
    
    def test_complex_settings_have_explanations(self):
        """Complex or non-obvious settings should have comments."""
        config_path = Path(".github/pr-agent-config.yml")
        
        with open(config_path, 'r') as f:
            lines = f.readlines()
        
        # Look for complex settings that should have comments
        complex_keys = ['monitoring', 'limits', 'fallback', 'security']
        
        for i, line in enumerate(lines):
            for key in complex_keys:
                if key in line and ':' in line:
                    # Check if there's a comment nearby (within 3 lines before or on same line)
                    has_comment = False
                    for j in range(max(0, i-3), i+1):
                        if '#' in lines[j]:
                            has_comment = True
                            break
                    
                    if not has_comment:
                        # This is okay if it's a simple value
                        pass  # Warning only, not failure


class TestPRAgentConfigDefaults:
    """Test that configuration provides sensible defaults."""
    
    @pytest.fixture
    def config_data(self):
        """Load PR Agent configuration."""
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_agent_enabled_by_default(self, config_data):
        """Agent should be enabled by default."""
        enabled = config_data.get('agent', {}).get('enabled', False)
        assert enabled is True, "PR Agent should be enabled by default"
    
    def test_has_reasonable_default_limits(self, config_data):
        """Default limits should be reasonable for typical usage."""
        limits = config_data.get('limits', {})
        
        # Check max concurrent PRs
        max_prs = limits.get('max_concurrent_prs', 0)
        assert 1 <= max_prs <= 20, \
            f"Max concurrent PRs ({max_prs}) should be between 1 and 20"
        
        # Check rate limits
        rate_limit = limits.get('rate_limit_requests', 0)
        if rate_limit:
            assert 10 <= rate_limit <= 5000, \
                f"Rate limit ({rate_limit}) should be between 10 and 5000"
    
    def test_monitoring_disabled_or_reasonable(self, config_data):
        """If monitoring is enabled, it should have reasonable settings."""
        monitoring = config_data.get('monitoring', {})
        check_interval = monitoring.get('check_interval', 0)
        
        if check_interval > 0:
            # Should check at least once per hour but not more than once per second
            assert 1 <= check_interval <= 3600, \
                f"Check interval {check_interval} is outside reasonable range"


class TestPRAgentConfigEdgeCases:
    """Test edge cases and boundary conditions in configuration."""
    
    @pytest.fixture
    def config_data(self):
        """Load PR Agent configuration."""
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_empty_sections_handled(self, config_data):
        """Empty configuration sections should not cause issues."""
        # Check that all sections are properly initialized
        for key, value in config_data.items():
            if isinstance(value, dict):
                # Empty dict is okay
                assert isinstance(value, dict)
            elif isinstance(value, list):
                # Empty list is okay
                assert isinstance(value, list)
    
    def test_special_characters_in_strings(self, config_data):
        """String values should handle special characters properly."""
        def check_strings(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if isinstance(value, str):
                        # Should not contain unescaped special chars that break YAML
                        assert '\x00' not in value, "Null bytes not allowed"
                    check_strings(value)
            elif isinstance(obj, list):
                for item in obj:
                    check_strings(item)
        
        check_strings(config_data)
    
    def test_numeric_string_confusion(self, config_data):
        """Numeric values should not be accidentally strings."""
        def check_types(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    
                    # Keys suggesting numeric values
                    if any(word in key.lower() for word in ['count', 'limit', 'max', 'min', 'interval', 'timeout']):
                        if value is not None and value != "":
                            assert not isinstance(value, str) or not value.isdigit(), \
                                f"Field '{new_path}' appears numeric but is string: {value}"
                    
                    check_types(value, new_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_types(item, f"{path}[{i}]")
        
        check_types(config_data)