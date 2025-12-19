"""
Validation tests for PR agent configuration changes.

Tests the simplified PR agent configuration, ensuring:
- Version downgrade from 1.1.0 to 1.0.0
- Removal of context chunking features
- Removal of tiktoken dependencies
- Simplified configuration structure
"""

import pytest
import yaml
from pathlib import Path


class DuplicateKeyLoader(yaml.SafeLoader):
    """Custom YAML loader that detects duplicate keys.
    
    Extends SafeLoader to maintain security while adding duplicate key detection.
    """
    pass


def _check_duplicate_keys(loader, node, deep=False):
    """Check for duplicate keys in YAML mappings."""
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping", node.start_mark,
                f"found duplicate key ({key})", key_node.start_mark
            )
        value = loader.construct_object(value_node, deep=deep)
        mapping[key] = value
    return mapping


DuplicateKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _check_duplicate_keys
)


class TestPRAgentConfigSimplification:
    """Test PR agent config simplification changes."""
    
    @pytest.fixture
    def pr_agent_config(self):
        """
        Load and parse the PR agent YAML configuration from .github/pr-agent-config.yml.
        
        Returns:
            The parsed YAML content as a Python mapping or sequence (typically a dict), or `None` if the file is empty.
        """
        config_path = Path(".github/pr-agent-config.yml")
        if not config_path.exists():
            pytest.fail(f"Config file not found: {config_path}")
        with open(config_path, 'r', encoding='utf-8') as f:
            try:
                cfg = yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in config: {e}")
        if cfg is None or not isinstance(cfg, dict):
            pytest.fail("Config must be a YAML mapping (dict) and not empty")
        return cfg
            pytest.fail(f"Config file not found: {config_path}")
        with open(config_path, 'r', encoding='utf-8') as f:
            try:
                cfg = yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in config: {e}")
        if cfg is None or not isinstance(cfg, dict):
            pytest.fail("Config must be a YAML mapping (dict) and not empty")
        return cfg
    
    def test_version_reverted_to_1_0_0(self, pr_agent_config):
        """Check that the PR agent's configured version is '1.0.0'."""
        assert pr_agent_config['agent']['version'] == '1.0.0'
    
    def test_no_context_configuration(self, pr_agent_config):
        """
        Assert that the 'agent' section does not contain a 'context' key.
        
        The test fails if the parsed PR agent configuration includes a 'context' key under the top-level 'agent' section.
        """
        agent_config = pr_agent_config['agent']
        assert 'context' not in agent_config
    
    def test_no_chunking_settings(self, pr_agent_config):
        """
        Assert the configuration contains no chunking-related settings.
        
        Checks that the keys 'chunking', 'chunk_size' and 'overlap_tokens' do not appear in the serialized configuration string (case-insensitive).
        """
        config_str = yaml.dump(pr_agent_config)
        assert 'chunking' not in config_str.lower()
                if key in mapping:
                    raise yaml.YAMLError(f"Duplicate key detected: {key!r}")
                mapping[key] = loader.construct_object(value_node, deep=deep)
                return mapping

                # Register constructors once for mappings (and ordered mappings if supported)
                DuplicateKeyLoader.add_constructor(
                    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
                    construct_mapping_no_dups
                )
                if hasattr(yaml.resolver.BaseResolver, 'DEFAULT_OMAP_TAG'):
                    DuplicateKeyLoader.add_constructor(
                        yaml.resolver.BaseResolver.DEFAULT_OMAP_TAG,
                        construct_mapping_no_dups
                    )
            DuplicateKeyLoader.add_constructor(
                yaml.resolver.BaseResolver.DEFAULT_OMAP_TAG,
                construct_mapping_no_dups
            )

        with open(config_path, 'r', encoding='utf-8') as f:
            try:
                yaml.load(f, Loader=DuplicateKeyLoader)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML syntax: {e}")
    
    def test_no_duplicate_keys(self):
        """Verify no duplicate keys in config."""
        config_path = Path(".github/pr-agent-config.yml")

        with open(config_path, 'r') as f:
            content = f.read()

        # Check for duplicate keys by tracking full hierarchical paths
        lines = content.split('\n')
        with open(config_path, 'r') as f:
            try:
                config = yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML syntax while checking duplicates: {e}")

        def find_duplicates(obj, path=""):
            duplicates = []
            if isinstance(obj, dict):
                keys_seen = set()
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    if key in keys_seen:
                        duplicates.append(current_path)
                    else:
                        keys_seen.add(key)
                    duplicates.extend(find_duplicates(value, current_path))
            elif isinstance(obj, list):
                for idx, item in enumerate(obj):
                    item_path = f"{path}[{idx}]" if path else f"[{idx}]"
                    duplicates.extend(find_duplicates(item, item_path))
            return duplicates

        duplicates = find_duplicates(config)
        if duplicates:
            pytest.fail(f"Duplicate keys found at paths: {', '.join(duplicates)}")
                key = line.split(':')[0].strip()

                # Skip list items (only when the first non-space character is '-')
                if line.lstrip().startswith('-'):
                    continue

                # Normalize indentation: expand tabs to spaces to avoid mixed indent issues
                expanded = line.expandtabs(2)
                indent = len(expanded) - len(expanded.lstrip(' '))
                # Ensure indentation uses only spaces (no stray tabs remain after expand)
                if '\t' in line:
                    pytest.fail("Tabs are not allowed for indentation in YAML config")
                # Pop stack entries that are at same or deeper indentation
                # (we've moved back up or sideways in the hierarchy)
                while path_stack and path_stack[-1][0] >= indent:
                    path_stack.pop()

                # Build full path from stack + current key
                parent_path = '.'.join(item[1] for item in path_stack)
                full_path = f"{parent_path}.{key}" if parent_path else key

                if full_path in seen_full_paths:
                    pytest.fail(f"Duplicate key at path '{full_path}'")
                seen_full_paths.add(full_path)

                # Push current key onto stack for potential children
                path_stack.append((indent, key))
    
    def test_consistent_indentation(self):
        """Verify consistent 2-space indentation."""
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, 'r', encoding='utf-8') as f:
            try:
                yaml.load(f, Loader=NoDuplicateKeyLoader)
            except yaml.YAMLError as e:
                pytest.fail(f"Duplicate key detected or invalid YAML: {e}")
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, 'r') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines, 1):
            if line.strip() and not line.strip().startswith('#'):
                indent = len(line) - len(line.lstrip())
                if indent > 0:
                    assert indent % 2 == 0, \
                        f"Line {i} has inconsistent indentation: {indent} spaces"


class TestPRAgentConfigSecurity:
    """Test security aspects of configuration."""
    
    @pytest.fixture
    def pr_agent_config(self):
        """
        Load and parse the PR agent YAML configuration from .github/pr-agent-config.yml.
        
        Returns:
            The parsed YAML content as a Python mapping or sequence (typically a dict), or `None` if the file is empty.
    def test_no_hardcoded_credentials(self, pr_agent_config):
        """
        Recursively scan configuration values for suspected secrets.

        This inspects values (not just serialized text) and traverses nested dicts/lists.
        The heuristic flags:
          - Long high-entropy strings (e.g., tokens)
          - Obvious secret prefixes/suffixes
          - Inline credentials in URLs (e.g., scheme://user:pass@host)
        """
        import re
        import math

        # Heuristic to detect inline creds in URLs (user:pass@)
        inline_creds_re = re.compile(r'^[a-zA-Z][a-zA-Z0-9+.-]*://[^/@:\s]+:[^/@\s]+@', re.IGNORECASE)

        # Common secret-like prefixes or markers
        secret_markers = (
            'secret', 'token', 'apikey', 'api_key', 'access_key', 'private_key',
            'pwd', 'password', 'auth', 'bearer '
        )

        def shannon_entropy(s: str) -> float:
            if not s:
                return 0.0
            # Limit to a reasonable window to avoid skew from extremely long text
            sample = s[:256]
            freq = {}
            for ch in sample:
                freq[ch] = freq.get(ch, 0) + 1
            ent = 0.0
            length = len(sample)
            for c in freq.values():
                p = c / length
                ent -= p * math.log2(p)
            return ent

        def looks_like_secret(val: str) -> bool:
            v = val.strip()
            if not v:
                return False
            # Common placeholders considered safe
            placeholders = {'<token>', '<secret>', 'changeme', 'your-token-here', 'dummy', 'placeholder', 'null', 'none'}
            if v.lower() in placeholders:
                return False
            # Inline credentials in URL
            if inline_creds_re.search(v):
                return True
            # Bearer tokens or obvious markers
            if any(m in v.lower() for m in secret_markers):
                # If marker appears and string is not trivially short, treat as suspicious
                if len(v) >= 12:
                    return True
    def test_no_hardcoded_credentials(self, pr_agent_config):
        """
        Recursively scan configuration values and keys for suspected secrets.
        - Flags high-entropy or secret-like string values.
        - Ensures sensitive keys only use safe placeholders.
        """
        import re
        import math
        import yaml

        # Heuristic to detect inline creds in URLs (user:pass@)
        inline_creds_re = re.compile(r'^[a-zA-Z][a-zA-Z0-9+.-]*://[^/@:\s]+:[^/@\s]+@', re.IGNORECASE)

        # Common secret-like prefixes or markers
        secret_markers = (
            'secret', 'token', 'apikey', 'api_key', 'access_key', 'private_key',
            'pwd', 'password', 'auth', 'bearer '
        )

        def shannon_entropy(s: str) -> float:
            if not s:
                return 0.0
            sample = s[:256]
            freq = {}
            for ch in sample:
                freq[ch] = freq.get(ch, 0) + 1
            ent = 0.0
            length = len(sample)
            for c in freq.values():
                p = c / length
                ent -= p * math.log2(p)
            return ent

        def looks_like_secret(val: str) -> bool:
            v = val.strip()
            if not v:
                return False
            placeholders = {'<token>', '<secret>', 'changeme', 'your-token-here', 'dummy', 'placeholder', 'null', 'none'}
            if v.lower() in placeholders:
                return False
            if inline_creds_re.search(v):
                return True
            if any(m in v.lower() for m in secret_markers) and len(v) >= 12:
                return True
            # Base64/URL-safe like long strings
            if re.fullmatch(r'[A-Za-z0-9_\-]{20,}', v) and shannon_entropy(v) >= 3.5:
                return True
            # Hex-encoded long strings (e.g., keys)
            if re.fullmatch(r'[A-Fa-f0-9]{32,}', v):
                return True
            return False

        # Walk values to detect secret-like strings
        def walk_values(obj, path="root"):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    walk_values(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    walk_values(item, f"{path}[{i}]")
            elif isinstance(obj, str):
                if looks_like_secret(obj):
                    pytest.fail(f"Suspected secret value at '{path}': {obj[:20]}...")
            # Non-string scalars ignored

        walk_values(pr_agent_config)

        # Enforce safe placeholders for sensitive keys
        sensitive_patterns = [
            'password', 'secret', 'token', 'api_key', 'apikey', 'access_key', 'private_key'
        ]
        safe_placeholders = {None, 'null', 'webhook'}

        def check_sensitive_keys(node, path="root"):
            if isinstance(node, dict):
                for k, v in node.items():
                    key_l = str(k).lower()
                    new_path = f"{path}.{k}"
                    if any(p in key_l for p in sensitive_patterns):
                        assert v in safe_placeholders, f"Potential hardcoded credential at '{new_path}'"
                    check_sensitive_keys(v, new_path)
            elif isinstance(node, list):
                for idx, item in enumerate(node):
                    check_sensitive_keys(item, f"{path}[{idx}]")
            # primitives ignored

        check_sensitive_keys(pr_agent_config)

        # Final serialized scan to ensure sensitive markers aren't embedded in values
        config_str = yaml.dump(pr_agent_config)
        for pat in sensitive_patterns:
            # If marker appears in the string, ensure we also see an allowed placeholder somewhere
            if pat in config_str:
                assert (' null' in config_str) or ('webhook' in config_str), \
                    f"Potential hardcoded credential found around pattern: {pat}"
            if re.fullmatch(r'[A-Za-z0-9_\-]{20,}', v):
                # High entropy threshold suggests secret
                if shannon_entropy(v) >= 3.5:
                    return True
            # Hex-encoded long strings (e.g., keys)
            if re.fullmatch(r'[A-Fa-f0-9]{32,}', v):
                return True
            return False

        def walk(obj, path="root"):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    key_path = f"{path}.{k}"
                    walk(v, key_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    walk(item, f"{path}[{i}]")
            elif isinstance(obj, str):
                if looks_like_secret(obj):
                    pytest.fail(f"Suspected secret value at '{path}': {obj[:20]}...")
            # Non-string scalars (int/bool/None/float) are ignored

        walk(pr_agent_config)
        """
        Traverse the parsed YAML and ensure that any key containing sensitive indicators
        has a safe placeholder value (None, 'null', or 'webhook').
        """
        sensitive_patterns = [
            sensitive_patterns = [
                'password', 'secret', 'token', 'api_key', 'apikey',
                'access_key', 'private_key'
            ]

            allowed_placeholders = {'null', 'none', 'placeholder'}

            def value_contains_secret(val: str) -> bool:
                low = val.lower()
                # ignore common placeholders and templated variables
                if low in allowed_placeholders or ('${' in val and '}' in val):
                    return False
                return any(pat in low for pat in sensitive_patterns)

            def scan_for_secrets(node, path="root"):
                if isinstance(node, dict):
                    for k, v in node.items():
                        scan_for_secrets(v, f"{path}.{k}")
                elif isinstance(node, list):
                    for idx, item in enumerate(node):
                        scan_for_secrets(item, f"{path}[{idx}]")
                elif isinstance(node, str):
                    assert not value_contains_secret(node), \
                        f"Potential hardcoded credential value at {path}"
                # Non-string scalars (int, float, bool, None) are safe to ignore

            scan_for_secrets(pr_agent_config)
            'access_key', 'private_key'
        ]

        safe_placeholders = {None, 'null', 'webhook'}

        def check_node(node, path=""):
            if isinstance(node, dict):
                for k, v in node.items():
                    key_l = str(k).lower()
                    new_path = f"{path}.{k}" if path else str(k)
                    if any(p in key_l for p in sensitive_patterns):
                        assert v in safe_placeholders, f"Potential hardcoded credential at '{new_path}'"
                    check_node(v, new_path)
            elif isinstance(node, list):
                for idx, item in enumerate(node):
                    check_node(item, f"{path}[{idx}]")
            # primitives are ignored unless hit via a sensitive key above

        check_node(pr_agent_config)
            'access_key', 'private_key'
        ]
        
        for pattern in sensitive_patterns:
            if pattern in config_str:
                # Should only appear in field names, not values
                assert 'null' in config_str or 'webhook' in config_str, \
                    f"Potential hardcoded credential found: {pattern}"
    
    def test_safe_configuration_values(self, pr_agent_config):
        """
        Assert that key numeric limits in the PR agent configuration fall within safe bounds.
        
        Checks that:
        - `limits['max_execution_time']` is less than or equal to 3600 seconds.
        - `limits['max_concurrent_prs']` is less than or equal to 10.
        - `limits['rate_limit_requests']` is less than or equal to 1000.
        """
        limits = pr_agent_config['limits']
        
        # Check for reasonable numeric limits
        assert limits['max_execution_time'] <= 3600, "Execution time too high"
        assert limits['max_concurrent_prs'] <= 10, "Too many concurrent PRs"
        assert limits['rate_limit_requests'] <= 1000, "Rate limit too high"


class TestPRAgentConfigRemovedComplexity:
    """Test that complex features were properly removed."""
    
    @pytest.fixture
    def pr_agent_config_content(self):
        """
        Return the contents of .github/pr-agent-config.yml as a string.
        
        Reads the PR agent configuration file from the repository root and returns its raw text.
        
        Returns:
            str: Raw YAML content of .github/pr-agent-config.yml.
        """
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, 'r') as f:
            return f.read()
    
    def test_no_summarization_settings(self, pr_agent_config_content):
        """Verify summarization settings removed."""
        assert 'summarization' not in pr_agent_config_content.lower()
        assert 'max_summary_tokens' not in pr_agent_config_content
    
    def test_no_token_management(self, pr_agent_config_content):
        """Verify token management settings removed."""
        assert 'max_tokens' not in pr_agent_config_content
        assert 'context_length' not in pr_agent_config_content
    
    def test_no_llm_model_references(self, pr_agent_config_content):
        """
        Ensure no explicit LLM model identifiers appear in the raw PR agent configuration.
        
        Parameters:
            pr_agent_config_content (str): Raw contents of .github/pr-agent-config.yml used for pattern checks.
        """
        assert 'gpt-3.5-turbo' not in pr_agent_config_content
        assert 'gpt-4' not in pr_agent_config_content