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
        def construct_mapping_no_dups(loader, node, deep=False, path_stack=None, seen_full_paths=None):
            if path_stack is None:
                path_stack = []
            if seen_full_paths is None:
                seen_full_paths = set()

            if not isinstance(node, yaml.MappingNode):
                return loader.construct_object(node, deep=deep)

            mapping = {}
            merges = []

            for key_node, value_node in node.value:
                key = loader.construct_object(key_node, deep=deep)
                try:
                    hash(key)
                except TypeError as exc:
                    raise yaml.YAMLError(f"Unhashable key encountered: {key!r}") from exc

                # Collect YAML merge keys to process after normal keys
                if key == '<<':
                    merges.append(value_node)
                    continue

                # Build and check full hierarchical path for duplicates
                full_path = tuple(path_stack + [key])
                if full_path in seen_full_paths:
                    raise yaml.YAMLError(f"Duplicate key at path '{'.'.join(map(str, full_path))}'")
                seen_full_paths.add(full_path)

                # Recursively construct child mappings while tracking path
                if isinstance(value_node, yaml.MappingNode):
                    value = construct_mapping_no_dups(
                        loader,
                        value_node,
                        deep=deep,
                        path_stack=list(full_path),
                        seen_full_paths=seen_full_paths
                    )
                else:
                    value = loader.construct_object(value_node, deep=deep)

                if key in mapping:
                    raise yaml.YAMLError(f"Duplicate key detected: {key!r}")
                mapping[key] = value

            # Handle merges, also respecting hierarchical paths
            for merge_node in merges:
                merged = loader.construct_object(merge_node, deep=deep)
                sources = merged if isinstance(merged, list) else [merged]

                for m in sources:
                    if not isinstance(m, dict):
                        raise yaml.YAMLError(f"Unsupported merge node type: {type(m).__name__}")
                    for mk, mv in m.items():
                        if mk in mapping:
                            raise yaml.YAMLError(f"Duplicate key detected via merge: {mk!r}")
                        full_path = tuple(path_stack + [mk])
                        if full_path in seen_full_paths:
                            raise yaml.YAMLError(f"Duplicate key at path '{'.'.join(map(str, full_path))}' via merge")
                        seen_full_paths.add(full_path)
                        mapping[mk] = mv

            return mapping
        DuplicateKeyLoader.add_constructor(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            construct_mapping_no_dups
        )
        if hasattr(yaml.resolver.BaseResolver, 'DEFAULT_OMAP_TAG'):
            DuplicateKeyLoader.add_constructor(
                yaml.resolver.BaseResolver.DEFAULT_OMAP_TAG,
                construct_mapping_no_dups
            )

        with open(config_path, 'r', encoding='utf-8') as f:
            try:
                yaml.load(f, Loader=DuplicateKeyLoader)
            except yaml.YAMLError as e:
                pytest.fail(f"Duplicate key detected or YAML error: {e}")
            else:
                with open(config_path, 'r', encoding='utf-8') as f2:
                    if not any(line.strip() and not line.lstrip().startswith('#') for line in f2):
                        pytest.fail("YAML file is empty or contains only comments.")
    def test_no_duplicate_keys(self):
        """Verify no duplicate keys in config."""
            for key_node, value_node in node.value:
                key = loader.construct_object(key_node, deep=deep)
                try:
                    hash(key)
                class DuplicateKeyLoader(yaml.SafeLoader):
                    pass
                    raise yaml.YAMLError(f"Unhashable key encountered: {key!r}") from exc

                # Collect YAML merge keys to process after normal keys
                if key == '<<':
                    merges.append(value_node)
                    continue

                # Build and validate full hierarchical path for this key
                full_path = tuple(path_stack + [key])
                if full_path in seen_full_paths:
                    raise yaml.YAMLError(f"Duplicate key at path '{'.'.join(map(str, full_path))}'")
                seen_full_paths.add(full_path)

                # Recursively construct child mappings while tracking full path
                if isinstance(value_node, yaml.MappingNode):
                    value = construct_mapping_no_dups(
                        loader,
                        value_node,
                        deep=deep,
                        path_stack=list(full_path),
                        seen_full_paths=seen_full_paths,
                    )
                else:
                    value = loader.construct_object(value_node, deep=deep)

                # Detect duplicates within the same mapping level
                if key in mapping:
                    raise yaml.YAMLError(f"Duplicate key detected: {key!r}")
                mapping[key] = value

            # Handle merges while respecting hierarchical paths
            for merge_node in merges:
                merged = loader.construct_object(merge_node, deep=deep)
                sources = merged if isinstance(merged, list) else [merged]

                for m in sources:
                    if not isinstance(m, dict):
                        raise yaml.YAMLError(f"Unsupported merge node type: {type(m).__name__}")
                    for mk, mv in m.items():
                        # Disallow overriding existing mapping keys from merge
                        if mk in mapping:
                            raise yaml.YAMLError(f"Duplicate key detected via merge: {mk!r}")
                        merge_full_path = tuple(path_stack + [mk])
                        if merge_full_path in seen_full_paths:
                            raise yaml.YAMLError(f"Duplicate key at path '{'.'.join(map(str, merge_full_path))}' via merge")
                        seen_full_paths.add(merge_full_path)
                        mapping[mk] = mv
        DuplicateKeyLoader.add_constructor(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            construct_mapping_no_dups
        )
        # Ensure ordered mappings also use the duplicate key check if present
        if hasattr(yaml.resolver.BaseResolver, 'DEFAULT_OMAP_TAG'):
            DuplicateKeyLoader.add_constructor(
                yaml.resolver.BaseResolver.DEFAULT_OMAP_TAG,
                construct_mapping_no_dups
            )

        with open(config_path, 'r', encoding='utf-8') as f:
            try:
                yaml.load(f, Loader=DuplicateKeyLoader)
            except yaml.YAMLError as e:
                pytest.fail(f"Duplicate key detected or YAML error: {e}")
            else:
                # Ensure a document exists (avoid passing on empty content)
                with open(config_path, 'r', encoding='utf-8') as f:
                    if not any(line.strip() and not line.lstrip().startswith('#') for line in f):
                        pytest.fail("YAML file is empty or contains only comments.")
                # Removed unreachable legacy code related to manual path tracking.
                if full_path in seen_full_paths:
                    pytest.fail(f"Duplicate key at path '{full_path}'")
                seen_full_paths.add(full_path)

                # Push current key onto stack for potential children
                path_stack.append((indent, key))
    
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
                assert isinstance(check_interval, int)
                assert check_interval > 0
                assert check_interval < 86400  # Less than 24 hours


if __name__ == "__main__":
    pytest.main([__file__, "-v"])