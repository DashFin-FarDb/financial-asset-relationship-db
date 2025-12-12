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

        class DuplicateKeyLoader(yaml.SafeLoader):
            pass

        def construct_mapping_no_dups(loader, node, deep=False):
            """
            Custom YAML mapping constructor that validates keys before constructing values.
            
            Validates keys in two passes:
            1. First pass: validate all keys (hashability, None check, duplicates)
            2. Second pass: construct values only after all keys are validated
            
            This prevents issues where value construction fails before duplicate detection.
            """
            if not isinstance(node, yaml.MappingNode):
                return loader.construct_object(node, deep=deep)
            
            mapping = {}
            validated_keys = []
            
            # First pass: validate keys only
            for key_node, _ in node.value:
                key = loader.construct_object(key_node, deep=deep)
                
                # Check for None keys
                if key is None:
                    raise yaml.YAMLError("Null (None) key detected in YAML mapping.")
                
                # Check for non-hashable keys
                try:
                    hash(key)
                except TypeError:
                    raise yaml.YAMLError(
                        f"Non-hashable key detected: {key!r} (type: {type(key).__name__})"
                    )
                
                # Check for duplicate keys
                if key in mapping:
                    raise yaml.YAMLError(f"Duplicate key detected: {key}")
                
                mapping[key] = None
                validated_keys.append(key)
            
            # Second pass: construct values after keys are validated
            for (key_node, value_node), key in zip(node.value, validated_keys):
                mapping[key] = loader.construct_object(value_node, deep=deep)
            
            return mapping

        DuplicateKeyLoader.add_constructor(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            construct_mapping_no_dups
        )
        
        # Ensure ordered mappings also use the duplicate key check
        if hasattr(yaml.resolver.BaseResolver, 'DEFAULT_OMAP_TAG'):
            DuplicateKeyLoader.add_constructor(
                yaml.resolver.BaseResolver.DEFAULT_OMAP_TAG,
                construct_mapping_no_dups
            )

        with open(config_path, 'r', encoding='utf-8') as f:
            try:
                yaml.load(f, Loader=DuplicateKeyLoader)
            except yaml.YAMLError as e:
                error_msg = str(e).lower()
                if "duplicate" in error_msg or "duplicate key" in error_msg:
                    pytest.fail(f"Duplicate key detected in YAML config: {e}")
                else:
                    pytest.fail(f"YAML parsing error in config: {e}")

    def test_non_hashable_keys_detected(self):
        """Verify non-hashable keys are detected and raise appropriate errors."""

        class NonHashableKeyLoader(yaml.SafeLoader):
            pass

        def construct_mapping_no_dups(loader, node, deep=False):
            """Custom YAML mapping constructor with key validation."""
            if not isinstance(node, yaml.MappingNode):
                return loader.construct_object(node, deep=deep)
            
            mapping = {}
            validated_keys = []
            
            # First pass: validate keys only
            for key_node, _ in node.value:
                key = loader.construct_object(key_node, deep=deep)
                
                if key is None:
                    raise yaml.YAMLError("Null (None) key detected in YAML mapping.")
                
                try:
                    hash(key)
                except TypeError:
                    raise yaml.YAMLError(
                        f"Non-hashable key detected: {key!r} (type: {type(key).__name__})"
                    )
                
                if key in mapping:
                    raise yaml.YAMLError(f"Duplicate key detected: {key}")
                
                mapping[key] = None
                validated_keys.append(key)
            
            # Second pass: construct values
            for (key_node, value_node), key in zip(node.value, validated_keys):
                mapping[key] = loader.construct_object(value_node, deep=deep)
            
            return mapping

        NonHashableKeyLoader.add_constructor(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            construct_mapping_no_dups
        )
        
        if hasattr(yaml.resolver.BaseResolver, 'DEFAULT_OMAP_TAG'):
            NonHashableKeyLoader.add_constructor(
                yaml.resolver.BaseResolver.DEFAULT_OMAP_TAG,
                construct_mapping_no_dups
            )

        # Test with a list key (non-hashable)
        yaml_content_list_key = "? [1, 2, 3]\n: invalid_list_key\nvalid_key: value\n"
        with pytest.raises(yaml.YAMLError, match="Non-hashable key detected"):
            yaml.load(yaml_content_list_key, Loader=NonHashableKeyLoader)

        # Test with a dict key (non-hashable)
        yaml_content_dict_key = "? {nested: dict}\n: invalid_dict_key\n"
        with pytest.raises(yaml.YAMLError, match="Non-hashable key detected"):
            yaml.load(yaml_content_dict_key, Loader=NonHashableKeyLoader)

        # Test with a None key (null)
        yaml_content_none_key = "? null\n: invalid_none_key\n"
        with pytest.raises(yaml.YAMLError, match=r"Null \(None\) key detected"):
            yaml.load(yaml_content_none_key, Loader=NonHashableKeyLoader)
    
    def test_consistent_indentation(self):
        """Verify config uses consistent 2-space indentation."""
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
                assert isinstance(check_interval, int)
                assert check_interval > 0
                assert check_interval < 86400  # Less than 24 hours


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
