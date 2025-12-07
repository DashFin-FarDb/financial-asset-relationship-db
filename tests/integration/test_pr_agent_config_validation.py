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
        """
        Load and return the PR agent configuration from .github/pr-agent-config.yml.
        
        Returns:
            dict: Parsed YAML content of the PR agent configuration as a dictionary.
        """
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def test_version_reverted_to_1_0_0(self, config):
        """
        Check that the agent version in the provided config equals "1.0.0".
        """
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
        """
        Check that the configuration includes a top-level `monitoring` section and that it is a mapping.
        
        Parameters:
            config (dict): Parsed YAML configuration loaded from .github/pr-agent-config.yml.
        """
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
        """
        Ensure the PR agent configuration file contains valid YAML.
        
        Fails the test if parsing raises a YAML error, or if the parsed document is empty or not a mapping.
        """
        config_path = Path(".github/pr-agent-config.yml")

        with open(config_path, 'r') as f:
            try:
                config = yaml.safe_load(f)
                assert config is not None
                assert isinstance(config, dict)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML syntax: {e}")

    def test_no_duplicate_keys(self):
        """
        Assert that the PR agent YAML configuration contains no duplicate or non-hashable mapping keys.
        
        Loads .github/pr-agent-config.yml with a custom YAML loader that raises a YAML error when it encounters duplicate mapping keys or unhashable keys (e.g., lists or dicts used as keys). Any YAML parsing errors or detected duplicates are converted into pytest failures with a descriptive message.
        """
        config_path = Path(".github/pr-agent-config.yml")

        class DuplicateKeyLoader(yaml.SafeLoader):
            pass

        def construct_mapping_no_dups(loader, node, deep=False):
            """
            Construct a Python mapping from a YAML mapping node while rejecting duplicate or unhashable keys.
            
            Parameters:
            	loader (yaml.Loader): The YAML loader used to construct Python objects from nodes.
            	node (yaml.Node): The YAML node to construct; if not a MappingNode the node is constructed normally and returned.
            	deep (bool): If True, construct objects deeply (pass through to loader.construct_object).
            
            Returns:
            	dict or any: A dict built from the mapping node when `node` is a MappingNode; otherwise the result of constructing `node` as provided by the loader.
            
            Raises:
            	yaml.YAMLError: If a mapping contains duplicate keys or a key that is not hashable.
            """
            if not isinstance(node, yaml.MappingNode):
                return loader.construct_object(node, deep=deep)
            mapping = {}
            for key_node, value_node in node.value:
                key = loader.construct_object(key_node, deep=deep)
                # Ensure key is hashable to avoid TypeError and provide a clear YAML error
                try:
                    hash(key)
                except TypeError:
                    raise yaml.YAMLError(f"Unhashable key detected in YAML mapping: {key!r}")
                if key in mapping:
                    raise yaml.YAMLError(f"Duplicate key detected: {key!r}")
                mapping[key] = loader.construct_object(value_node, deep=deep)
            return mapping

        # Register the constructor for mapping nodes
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
                # Check if this is specifically a duplicate key error
                error_msg = str(e).lower()
                if "duplicate" in error_msg:
                    pytest.fail(f"Duplicate key detected in YAML config: {e}")
                else:
                    pytest.fail(f"YAML parsing error in config: {e}")

    def test_non_hashable_keys_detected(self):
        """
        Detect non-hashable or null mapping keys in YAML and assert a yaml.YAMLError is raised.
        
        Uses a custom SafeLoader that rejects mapping keys which are None, not hashable, or duplicated, then writes small YAML snippets containing a list key, a dict key, and a null key to temporary files and verifies loading each raises yaml.YAMLError with an error message indicating the specific problem (non-hashable key with the offending type, or null key).
        """
        import tempfile
        import os

        class NonHashableKeyLoader(yaml.SafeLoader):
            pass

        def construct_mapping_check_hashable(loader, node, deep=False):
            """
            Construct a Python mapping from a YAML mapping node while validating keys.
            
            Constructs and returns a dict for the given YAML mapping node, ensuring each key is not None, is hashable, and is unique. If the provided node is not a mapping node the node is constructed normally via the loader.
            
            Parameters:
                loader: The YAML loader instance used to construct objects.
                node: The YAML node to construct; expected to be a MappingNode for mapping construction.
                deep (bool): If True, construct objects deeply (pass through to the loader).
            
            Returns:
                dict: A dictionary built from the mapping node's key/value pairs.
            
            Raises:
                yaml.YAMLError: If a mapping key is null, non-hashable or duplicated.
            """
            if not isinstance(node, yaml.MappingNode):
                return loader.construct_object(node, deep=deep)
            mapping = {}
            for key_node, value_node in node.value:
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
                    raise yaml.YAMLError(f"Duplicate key detected: {key!r}")
                mapping[key] = loader.construct_object(value_node, deep=deep)
            return mapping

        # Register the constructor for mapping nodes
        NonHashableKeyLoader.add_constructor(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            construct_mapping_check_hashable
        )

        # Test with non-hashable keys (lists and dicts)
        test_cases = [
            ("list key", "[1, 2, 3]: value"),
            ("dict key", "{a: 1}: value"),
            ("null key", "null: value"),
        ]

        for test_name, yaml_content in test_cases:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
                f.write(yaml_content)
                temp_file = f.name

            try:
                with open(temp_file, 'r', encoding='utf-8') as f:
                    with pytest.raises(yaml.YAMLError) as exc_info:
                        yaml.load(f, Loader=NonHashableKeyLoader)
                
                # Verify the error message contains expected text
                error_msg = str(exc_info.value)
                if test_name == "list key":
                    assert "Non-hashable key detected" in error_msg
                    assert "list" in error_msg
                elif test_name == "dict key":
                    assert "Non-hashable key detected" in error_msg
                    assert "dict" in error_msg or "OrderedDict" in error_msg
                elif test_name == "null key":
                    assert "Null (None) key detected" in error_msg
            finally:
                os.unlink(temp_file)
    
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
        """
        Ensure the PR agent YAML contains no hardcoded credential values.
        
        Reads .github/pr-agent-config.yml, scans for mapping entries whose keys contain any of: "password", "api_key", "secret", or "token", and verifies that any corresponding value is a placeholder (a dollar-prefixed token, three or more asterisks, or "REDACTED", case-insensitive). The test fails if a matching key has a non-placeholder value, reporting the offending value.
        """
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
                lines = [line for line in content.split('\n') if pattern in line]
                for line in lines:
                    if ':' in line:
                        parts = line.split(':', 1)
                        if len(parts) > 1:
                            value = parts[1].strip()
                            # Flag if value is not a placeholder (e.g., $, ***, or REDACTED)
                            import re
                            placeholder_regex = re.compile(r'^\s*(\$\S*|(\*{3,})|REDACTED)\s*$', re.IGNORECASE)
                            assert placeholder_regex.match(value), \
                                f"Potential hardcoded {pattern} found: {value}"

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