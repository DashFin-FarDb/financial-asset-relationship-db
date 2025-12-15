"""
Tests for PR Agent configuration file validation.

Validates the pr-agent-config.yml simplification changes that removed
complex context chunking configuration and reverted to simpler settings.
"""

import pytest
import yaml
from pathlib import Path
from typing import Dict, Any


class TestPRAgentConfigSimplification:
    """Test PR Agent config simplification changes."""
    
    @pytest.fixture
    def config(self) -> Dict[str, Any]:
        """Load PR agent configuration."""
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def test_version_reverted_to_1_0_0(self, config):
        """Verify version was reverted from 1.1.0 to 1.0.0."""
        assert config['agent']['version'] == "1.0.0", \
            "Version should be 1.0.0 after simplification"
    
    def test_context_config_removed(self, config):
        """Verify complex context management config was removed."""
        agent_config = config.get('agent', {})
        
        # Should not have context chunking configuration
        assert 'context' not in agent_config, \
            "Complex context configuration should be removed"
    
    def test_no_chunking_settings(self, config):
        """Verify chunking settings were removed."""
        config_str = yaml.dump(config).lower()
        
        # These settings should not exist
        assert 'max_tokens' not in config_str
        assert 'chunk_size' not in config_str
        assert 'overlap_tokens' not in config_str
        assert 'summarization_threshold' not in config_str
    
    def test_no_tiktoken_references(self, config):
        """Verify tiktoken references were removed."""
        config_str = yaml.dump(config).lower()
        assert 'tiktoken' not in config_str
    
    def test_no_fallback_strategies(self, config):
        """Verify fallback strategies were removed."""
        limits_config = config.get('limits', {})
        assert 'fallback' not in limits_config, \
            "Fallback strategies should be removed"
    
    def test_basic_config_structure_intact(self, config):
        """Verify basic config structure is still valid."""
        assert 'agent' in config
        assert 'name' in config['agent']
        assert 'enabled' in config['agent']
    
    def test_monitoring_config_preserved(self, config):
        """Verify monitoring settings are still present."""
        assert 'monitoring' in config
        assert isinstance(config['monitoring'], dict)
    
    def test_limits_simplified(self, config):
        """Verify limits section was simplified."""
        limits = config.get('limits', {})
        
        # Should not have complex context processing limits
        assert 'max_files_per_chunk' not in limits
        assert 'max_diff_lines' not in limits
        assert 'max_comment_length' not in limits


class TestPRAgentConfigYAMLValidity:
    """Test YAML validity and format."""
    
    def test_valid_yaml_syntax(self):
        """Verify config file has valid YAML syntax."""
        config_path = Path(".github/pr-agent-config.yml")
        
        with open(config_path, 'r') as f:
            try:
                config = yaml.safe_load(f)
                assert config is not None
                assert isinstance(config, dict)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML syntax: {e}")
    
    def test_no_duplicate_keys(self):
        """Verify no duplicate keys in config."""
        config_path = Path(".github/pr-agent-config.yml")
        
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Check for obvious duplicate patterns, scoped per top-level section
        lines = content.split('\n')
        section_keys = {}
        top_level_keys = set()
        current_section = None

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            if ':' not in line:
                continue

            # Get indentation and key name
            indent = len(line) - len(line.lstrip(' '))
            key = line.split(':', 1)[0].strip()

            # Handle top-level keys (no indentation)
            if indent == 0:
                if key in top_level_keys:
                    pytest.fail(f"Duplicate top-level key '{key}'")
                top_level_keys.add(key)
                current_section = key
                continue

            # Skip list items like "- key: value"
            if key.startswith('-'):
                key = key.lstrip('-').strip()

            if current_section is None:
                continue

            section = section_keys.setdefault(current_section, set())
            level_key = (indent, key)
            if level_key in section:
                pytest.fail(
                    f"Duplicate key '{key}' at indentation {indent} in section '{current_section}'"
                )
            section.add(level_key)
    
    def test_consistent_indentation(self):
        """Verify consistent 2-space indentation."""
        config_path = Path(".github/pr-agent-config.yml")
        
        with open(config_path, 'r') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines, 1):
            if line.strip() and line[0] == ' ':
                spaces = len(line) - len(line.lstrip(' '))
                assert spaces % 2 == 0, \
                    f"Line {i}: Inconsistent indentation (not multiple of 2)"


class TestPRAgentConfigSecurity:
    """Security-focused tests for PR agent config."""
    
    def test_no_hardcoded_credentials(self):
        """Verify no hardcoded credentials in config."""
        config_path = Path(".github/pr-agent-config.yml")
        
        with open(config_path, 'r') as f:
            content = f.read().lower()
        
        # Check for potential credential patterns
        sensitive_patterns = [
            'password',
            'api_key',
            'secret',
            'token',
        ]
        
        for pattern in sensitive_patterns:
            if pattern in content:
                # Make sure it's a key name, not a value
                lines = [l for l in content.split('\n') if pattern in l]
                for line in lines:
                    if ':' in line:
                        parts = line.split(':', 1)
                        if len(parts) > 1:
                            value = parts[1].strip()
                            # Should not have actual credential values
                            assert len(value) < 10 or value.startswith('$'), \
                                f"Potential hardcoded {pattern} found"
    
    def test_safe_configuration_values(self):
        """Verify configuration values are safe."""
        config_path = Path(".github/pr-agent-config.yml")
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Check that numeric limits are reasonable
        if 'monitoring' in config:
            check_interval = config['monitoring'].get('check_interval')
            if check_interval:
            if check_interval is not None:
                assert check_interval > 0
                assert check_interval < 86400  # Less than 24 hours


if __name__ == "__main__":
    pytest.main([__file__, "-v"])