"""
Comprehensive validation tests for PR Agent configuration file.

This module tests the pr-agent-config.yml configuration file structure,
values, and best practices, with focus on recent simplifications:
- Removal of complex context chunking
- Simplified token management
- Streamlined monitoring settings

Tests cover:
- YAML syntax and structure
- Configuration value validation
- Security considerations
- Performance settings
- Fallback configurations
"""

import pytest
import yaml
from pathlib import Path
from typing import Dict, Any


class TestPRAgentConfigStructure:
    """Test the basic structure of PR agent configuration."""
    
    @pytest.fixture
    def config_path(self) -> Path:
        """Get path to PR agent config file."""
        return Path(__file__).parent.parent.parent / '.github' / 'pr-agent-config.yml'
    
    @pytest.fixture
    def config(self, config_path: Path) -> Dict[str, Any]:
        """Load PR agent configuration."""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            pytest.fail(f"Failed to load pr-agent-config.yml: {e}")
    
    def test_config_file_exists(self, config_path: Path):
        """Test that PR agent config file exists."""
        assert config_path.exists(), "PR agent config file should exist"
    
    def test_config_is_valid_yaml(self, config_path: Path):
        """Test that config file is valid YAML."""
        with open(config_path, 'r') as f:
            try:
                yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in pr-agent-config.yml: {e}")
    
    def test_config_has_required_sections(self, config: Dict[str, Any]):
        """Test that config has required top-level sections."""
        required_sections = {'agent', 'monitoring'}
        
        for section in required_sections:
            assert section in config, f"Config should have '{section}' section"
    
    def test_agent_section_structure(self, config: Dict[str, Any]):
        """Test that agent section has correct structure."""
        agent = config.get('agent', {})
        
        assert 'name' in agent, "Agent section should have 'name'"
        assert 'version' in agent, "Agent section should have 'version'"
        assert 'enabled' in agent, "Agent section should have 'enabled'"


class TestPRAgentConfigSimplification:
    """Test that PR agent config has been simplified as intended."""
    
    @pytest.fixture
    def config(self) -> Dict[str, Any]:
        """Load PR agent configuration."""
        config_path = Path(__file__).parent.parent.parent / '.github' / 'pr-agent-config.yml'
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_no_complex_context_chunking_config(self, config: Dict[str, Any]):
        """Test that complex context chunking configuration has been removed."""
        agent = config.get('agent', {})
        
        # Should not have complex context management
        assert 'context' not in agent or not agent['context'].get('chunking'), (
            "Complex context chunking should be removed for simplification"
        )
        
        # Should not have summarization config
        assert 'context' not in agent or not agent['context'].get('summarization'), (
            "Complex summarization config should be removed"
        )
    
    def test_no_tiktoken_references(self, config: Dict[str, Any]):
        """Test that tiktoken-specific configuration has been removed."""
        config_str = str(config).lower()
        
        assert 'tiktoken' not in config_str, (
            "tiktoken references should be removed from simplified config"
        )
    
    def test_simplified_limits_section(self, config: Dict[str, Any]):
        """Test that limits section has been simplified."""
        limits = config.get('limits', {})
        
        # Should not have complex fallback strategies
        if 'fallback' in limits:
            fallback = limits['fallback']
            
            # Should not have chunking-specific fallbacks
            assert 'on_context_overflow' not in fallback or \
                   fallback['on_context_overflow'] != 'chunk_and_summarize', (
                "Complex chunking fallback should be simplified"
            )


class TestPRAgentConfigValues:
    """Test specific configuration values and their validity."""
    
    @pytest.fixture
    def config(self) -> Dict[str, Any]:
        """Load PR agent configuration."""
        config_path = Path(__file__).parent.parent.parent / '.github' / 'pr-agent-config.yml'
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_agent_version_format(self, config: Dict[str, Any]):
        """Test that agent version follows semantic versioning."""
        version = config['agent']['version']
        
        # Should be in format X.Y.Z
        parts = version.split('.')
        assert len(parts) == 3, f"Version should be semantic (X.Y.Z): {version}"

        for part in parts:
            assert part.isdigit(), f"Version parts should be numeric: {version}"
    
    def test_monitoring_intervals_are_reasonable(self, config: Dict[str, Any]):
        """Test that monitoring intervals are reasonable."""
        monitoring = config.get('monitoring', {})
        
        if 'check_interval' in monitoring:
            interval = monitoring['check_interval']
            assert isinstance(interval, int), "Check interval should be integer"
            assert 60 <= interval <= 7200, (
                f"Check interval should be between 1 min and 2 hours: {interval}"
            )
    
    def test_rate_limits_are_reasonable(self, config: Dict[str, Any]):
        """Test that rate limits are configured reasonably."""
        limits = config.get('limits', {})
        
        if 'rate_limit_requests' in limits:
            rate_limit = limits['rate_limit_requests']
            assert isinstance(rate_limit, int), "Rate limit should be integer"
            assert rate_limit > 0, "Rate limit should be positive"
            assert rate_limit <= 5000, f"Rate limit seems too high: {rate_limit}"
    
    def test_max_concurrent_prs_is_reasonable(self, config: Dict[str, Any]):
        """Test that max concurrent PRs is reasonable."""
        limits = config.get('limits', {})
        
        if 'max_concurrent_prs' in limits:
            max_prs = limits['max_concurrent_prs']
            assert isinstance(max_prs, int), "Max concurrent PRs should be integer"
            assert 1 <= max_prs <= 20, (
                f"Max concurrent PRs should be between 1-20: {max_prs}"
            )


class TestPRAgentConfigSecurity:
    """Test security-related configuration."""
    
    @pytest.fixture
    def config(self) -> Dict[str, Any]:
        """Load PR agent configuration."""
        config_path = Path(__file__).parent.parent.parent / '.github' / 'pr-agent-config.yml'
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_no_hardcoded_secrets(self, config: Dict[str, Any]):
        """Test that no secrets are hardcoded in config using recursive inspection."""
        import re
        secret_key_patterns = ['password', 'api_key', 'apikey', 'token', 'secret', 'auth', 'credential', 'key']
        safe_markers = ('${{', '${', 'PLACEHOLDER', '<placeholder>')
        # Simple regexes for suspicious values (not exhaustive)
        long_token_re = re.compile(r'[A-Za-z0-9_\-]{32,}')
        base64_like_re = re.compile(r'^[A-Za-z0-9+/]{32,}={0,2}$')

        def is_safe_placeholder(val: str) -> bool:
            v = val.strip()
            if any(m in v for m in safe_markers):
                return True
            # Common dummy values
            if v.lower() in {'', 'none', 'null', 'changeme', 'example', 'sample'}:
                return True
            return False

        def value_looks_secret(val: str) -> bool:
            if not val or is_safe_placeholder(val):
                return False
            # Disallow obvious inline literals that look like secrets
            if long_token_re.search(val) or base64_like_re.match(val):
                return True
            return False

        def contains_hardcoded_secret(obj) -> bool:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    k_l = str(k).lower()
                    # If key name suggests secret, ensure value is not a literal
                    if any(p in k_l for p in secret_key_patterns):
                        if isinstance(v, str) and value_looks_secret(v):
                            return True
                        # Non-string values for secret-like keys should typically be empty/None
                        if v not in (None, '') and not isinstance(v, (str, dict, list)):
                            return True
                    if contains_hardcoded_secret(v):
                        return True
            elif isinstance(obj, list):
                for item in obj:
                    if contains_hardcoded_secret(item):
                        return True
            else:
                # Scalar at top-level or within structures: only flag if it strongly looks like a secret
                if isinstance(obj, str) and value_looks_secret(obj):
                    return True
            return False

        assert not contains_hardcoded_secret(config), "Potential hardcoded secret detected in config"
    
    def test_debug_mode_is_disabled(self, config: Dict[str, Any]):
        """Test that debug mode is disabled in production config."""
        debug = config.get('debug', {})
        
        if 'enabled' in debug:
            assert not debug['enabled'], (
                "Debug mode should be disabled in production config"
            )


class TestPRAgentConfigPerformance:
    """Test performance-related configuration."""
    
    @pytest.fixture
    def config(self) -> Dict[str, Any]:
        """Load PR agent configuration."""
        config_path = Path(__file__).parent.parent.parent / '.github' / 'pr-agent-config.yml'
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_timeouts_are_configured(self, config: Dict[str, Any]):
        """Test that appropriate timeouts are configured."""
        # Check various sections for timeout configurations
        config_str = str(config)
        
        # Should have some timeout configurations
        has_timeout_config = 'timeout' in config_str.lower()
        
        # This is informational - timeouts may be in workflow instead
        if not has_timeout_config:
            pytest.fail("Config should define at least one timeout configuration")
    
    def test_caching_strategy_if_present(self, config: Dict[str, Any]):
        """Test that caching configuration is reasonable if present."""
        cache = config.get('cache', {})
        
        if 'enabled' in cache and cache['enabled']:
            # Should have TTL configured
            assert 'ttl' in cache or 'ttl_seconds' in cache, (
                "Cache should have TTL configured"
            )
            
            if 'ttl' in cache:
                ttl = cache['ttl']
                assert 60 <= ttl <= 86400, (
                    f"Cache TTL should be between 1 min and 24 hours: {ttl}"
                )
            if 'ttl_seconds' in cache:
                ttl = cache['ttl_seconds']
                assert 60 <= ttl <= 86400, (
                    f"Cache TTL should be between 1 min and 24 hours: {ttl}"
                )


class TestPRAgentConfigMaintainability:
    """Test configuration maintainability and documentation."""
    
    @pytest.fixture
    def config_path(self) -> Path:
        """Get path to PR agent config file."""
        return Path(__file__).parent.parent.parent / '.github' / 'pr-agent-config.yml'
    
    def test_config_has_comments(self, config_path: Path):
        """Test that config file has explanatory comments."""
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Should have at least some comment lines
        comment_lines = [line for line in content.split('\n') 
                        if line.strip().startswith('#')]
        
        assert len(comment_lines) >= 3, (
            "Config should have comments explaining settings"
        )
    
    def test_config_sections_are_organized(self, config_path: Path):
        """Test that config sections are logically organized."""
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Key sections should appear in logical order
        expected_order = ['agent', 'monitoring', 'notifications', 'limits', 'debug']
        
        positions = {}
        for section in expected_order:
            pos = content.find(f'\n{section}:')
            if pos != -1:
                positions[section] = pos
        
        # Sections that exist should be in expected order
        if len(positions) > 1:
            sorted_sections = sorted(positions.items(), key=lambda x: x[1])
            section_names = [s[0] for s in sorted_sections]
            
            # Check if order matches expected (allowing for missing sections)
            expected_filtered = [s for s in expected_order if s in section_names]
            
            for i, section in enumerate(section_names):
                expected_index = expected_filtered.index(section)
                assert expected_index == i, (
                    f"Config sections should be in logical order. "
                    f"Expected {section} at position {expected_index}, but found at position {i}. "
                    f"Expected order: {expected_filtered}, Actual order: {section_names}")

class TestPRAgentConfigBackwardCompatibility:
    """Test that config maintains necessary backward compatibility."""
    
    @pytest.fixture
    def config(self) -> Dict[str, Any]:
        """Load PR agent configuration."""
        config_path = Path(__file__).parent.parent.parent / '.github' / 'pr-agent-config.yml'
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_agent_name_is_preserved(self, config: Dict[str, Any]):
        """Test that agent name is preserved for identification."""
        agent = config.get('agent', {})
        name = agent.get('name', '')
        
        assert name, "Agent should have a name for identification"
        assert 'PR Agent' in name or 'agent' in name.lower(), (
            f"Agent name should be recognizable: {name}"
        )
    
    def test_enabled_flag_is_present(self, config: Dict[str, Any]):
        """Test that enabled flag exists for easy toggling."""
        agent = config.get('agent', {})
        
        assert 'enabled' in agent, (
            "Agent should have 'enabled' flag for easy toggling"
        )
        assert isinstance(agent['enabled'], bool), (
            "'enabled' should be a boolean value"
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v'])