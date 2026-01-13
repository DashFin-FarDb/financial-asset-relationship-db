"""
Validation tests for PR agent configuration changes.

Tests the simplified PR agent configuration, ensuring:
- Version downgrade from 1.1.0 to 1.0.0
- Removal of context chunking features
- Removal of tiktoken dependencies
- Simplified configuration structure
"""

import re
from pathlib import Path

import pytest
import yaml


class TestPRAgentConfigSimplification:
    """Test PR agent config simplification changes."""

    @staticmethod
    @pytest.fixture
    def pr_agent_config():
        """
        Load and parse the PR agent YAML configuration from .github/pr-agent-config.yml.

        If the file is missing, contains invalid YAML, or does not contain a top-level mapping, the fixture will call pytest.fail to abort the test.

        Returns:
            dict: The parsed YAML content as a Python mapping.
        """
        config_path = Path(".github/pr-agent-config.yml")
        if not config_path.exists():
            pytest.fail(f"Config file not found: {config_path}")
        with open(config_path, "r", encoding="utf-8") as f:
            try:
                cfg = yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in config: {e}")
        if cfg is None or not isinstance(cfg, dict):
            pytest.fail("Config must be a YAML mapping (dict) and not empty")
        return cfg

    def test_version_reverted_to_1_0_0(self, pr_agent_config):
        """Check that the PR agent's configured version is '1.0.0'."""
        assert pr_agent_config["agent"]["version"] == "1.0.0"

    def test_no_context_configuration(self, pr_agent_config):
        """
        Assert that the 'agent' section does not contain a 'context' key.

        The test fails if the parsed PR agent configuration includes a 'context' key under the top-level 'agent' section.
        """
        agent_config = pr_agent_config["agent"]
        assert "context" not in agent_config

    def test_no_chunking_settings(self, pr_agent_config):
        """
        Assert the configuration contains no chunking-related settings.

        Checks that the keys 'chunking', 'chunk_size' and 'overlap_tokens' do not appear in the serialized configuration string (case-insensitive).
        """
        config_str = yaml.dump(pr_agent_config)
        assert "chunking" not in config_str.lower()
        assert "chunk_size" not in config_str.lower()
        assert "overlap_tokens" not in config_str.lower()

    def test_no_tiktoken_references(self, pr_agent_config):
        """Verify tiktoken references removed."""
        config_str = yaml.dump(pr_agent_config)
        assert "tiktoken" not in config_str.lower()

    def test_no_fallback_strategies(self, pr_agent_config):
        """
        Ensure the top-level `limits` section does not contain a `fallback` key.
        """
        limits = pr_agent_config.get("limits", {})
        assert "fallback" not in limits

    def test_basic_config_structure_intact(self, pr_agent_config):
        """Verify basic configuration sections still present."""
        # Essential sections should remain
        assert "agent" in pr_agent_config
        assert "monitoring" in pr_agent_config
        assert "actions" in pr_agent_config
        assert "quality" in pr_agent_config
        assert "security" in pr_agent_config

    def test_monitoring_config_present(self, pr_agent_config):
        """
        Ensure the top-level monitoring section contains the keys 'check_interval', 'max_retries', and 'timeout'.

        Parameters:
            pr_agent_config (dict): Parsed PR agent configuration mapping.
        """
        monitoring = pr_agent_config["monitoring"]
        assert "check_interval" in monitoring
        assert "max_retries" in monitoring
        assert "timeout" in monitoring

    def test_limits_simplified(self, pr_agent_config):
        """Verify limits section simplified."""
        limits = pr_agent_config["limits"]

        # Should not have complex chunking limits
        assert "max_files_per_chunk" not in limits
        assert "max_diff_lines" not in limits

        # Should have basic limits
        assert "max_execution_time" in limits
        assert "max_concurrent_prs" in limits


class TestPRAgentConfigYAMLValidity:
    """Test YAML validity and structure."""

    def test_config_is_valid_yaml(self):
        """
        Fail the test if .github/pr-agent-config.yml contains invalid YAML.

        Attempts to parse the repository file at .github/pr-agent-config.yml and fails the test with the YAML parser error when parsing fails.
        """
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, "r") as f:
            try:
                yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"PR agent config has invalid YAML: {e}")

    def test_no_duplicate_keys(self):
        """
        Fail the test if any top-level YAML key appears more than once in the file.

        Scans .github/pr-agent-config.yml, ignores comment lines, and for each non-comment line treats the text before the first ':' as the key; the test fails if a key is encountered more than once.
        """
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, "r") as f:
            content = f.read()

        # Simple check for obvious duplicates
        lines = content.split("\n")
        seen_keys = set()
        for line in lines:
            if ":" in line and not line.strip().startswith("#"):
                key = line.split(":")[0].strip()
                if key in seen_keys:
                    pytest.fail(f"Duplicate key found: {key}")
                seen_keys.add(key)

    def test_consistent_indentation(self):
        """
        Verify that every non-empty, non-comment line in the PR agent YAML uses 2-space indentation increments.

        Raises an AssertionError indicating the line number when a line's leading spaces are not a multiple of two.
        """
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, "r") as f:
            lines = f.readlines()

        for i, line in enumerate(lines, 1):
            if line.strip() and not line.strip().startswith("#"):
                indent = len(line) - len(line.lstrip())
                if indent > 0:
                    assert indent % 2 == 0, f"Line {i} has inconsistent indentation: {indent} spaces"


class TestPRAgentConfigSecurity:
    """Test security aspects of configuration."""

    @staticmethod
    @pytest.fixture
    def pr_agent_config():
        """
        Load and parse the PR agent YAML configuration from .github/pr-agent-config.yml.

        Returns:
            dict: The parsed YAML content as a Python mapping.
        """
        config_path = Path(".github/pr-agent-config.yml")
        if not config_path.exists():
            pytest.fail(f"Config file not found: {config_path}")
        with open(config_path, "r", encoding="utf-8") as f:
            try:
                cfg = yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in config: {e}")
        if cfg is None or not isinstance(cfg, dict):
            pytest.fail("Config must be a YAML mapping (dict) and not empty")
        return cfg

    def test_config_values_have_no_hardcoded_credentials(self, pr_agent_config):
        """
        Recursively scan configuration values for suspected secrets.

        This inspects values (not just serialized text) and traverses nested dicts/lists.
        The heuristic flags:
          - Long high-entropy strings (e.g., tokens)
          - Obvious secret prefixes/suffixes
          - Inline credentials in URLs (e.g., scheme://user:pass@host)
        """

        def _iter_string_values(obj):
            if isinstance(obj, dict):
                for v in obj.values():
                    yield from _iter_string_values(v)
            elif isinstance(obj, list):
                for v in obj:
                    yield from _iter_string_values(v)
            elif isinstance(obj, str):
                yield obj

        suspected = []

        secret_prefixes = (
            "sk-",
            "AKIA",
            "SECRET_",
            "TOKEN_",
        )
        inline_cred_pattern = re.compile(r"://[^/@:\s]+:[^/@:\s]+@")

        for value in _iter_string_values(pr_agent_config):
            stripped = value.strip()
            if not stripped:
                continue

            # Long string heuristic (possible API keys or tokens)
            if len(stripped) >= 40:
                suspected.append(("long_string", stripped))
                continue

            # Obvious secret-like prefixes
            if any(stripped.startswith(p) for p in secret_prefixes):
                suspected.append(("prefix", stripped))
                continue

            # Inline credentials in URLs
            if inline_cred_pattern.search(stripped):
                suspected.append(("inline_creds", stripped))

        if suspected:
            details = "\n".join(f"{kind}: {val}" for kind, val in suspected)
            pytest.fail(f"Potential hardcoded credentials found in PR agent config:\n{details}")
        import math
        import re

        # Heuristic to detect inline creds in URLs (user:pass@)
        re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://[^/@:\\s]+:[^/@\\s]+@", re.IGNORECASE)

        # Common secret-like prefixes or markers
        secret_markers = (
            "secret",
            "token",
            "apikey",
            "api_key",
            "access_key",
            "private_key",
            "pwd",
            "password",
            "auth",
            "bearer ",
        )

    @staticmethod
    def test_no_hardcoded_credentials(pr_agent_config):
        """
        Recursively scan configuration values and keys for suspected secrets.
        - Flags high - entropy or secret - like string values.
        - Ensures sensitive keys only use safe placeholders.
        """
        import math
        import re

        import yaml

        # Heuristic to detect inline creds in URLs (user:pass@)
        inline_creds_re = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://[^/@:\s]+:[^/@\s]+@", re.IGNORECASE)

        # Common secret-like prefixes or markers
        secret_markers = (
            "secret",
            "token",
            "apikey",
            "api_key",
            "access_key",
            "private_key",
            "pwd",
            "password",
            "auth",
            "bearer ",
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
            placeholders = {
                "<token>",
                "<secret>",
                "changeme",
                "your-token-here",
                "dummy",
                "placeholder",
                "null",
                "none",
            }
            if v.lower() in placeholders:
                return False
            if inline_creds_re.search(v):
                return True
            if any(m in v.lower() for m in secret_markers) and len(v) >= 12:
                return True
            # Base64/URL-safe like long strings
            if re.fullmatch(r"[A-Za-z0-9_\-]{20,}", v) and shannon_entropy(v) >= 3.5:
                return True
            # Hex-encoded long strings (e.g., keys)
            if re.fullmatch(r"[A-Fa-f0-9]{32,}", v):
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
        sensitive_patterns = ["password", "secret", "token", "api_key", "apikey", "access_key", "private_key"]
        safe_placeholders = {None, "null", "webhook"}

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
                assert (" null" in config_str) or (
                    "webhook" in config_str
                ), f"Potential hardcoded credential found around pattern: {pat}"

    def test_no_hardcoded_secrets(self, pr_agent_config):
        """
        Traverse the parsed YAML and ensure that any key or value containing sensitive
        indicators has a safe placeholder value (None, 'null', 'none', 'placeholder',
        or a templated variable like '${VAR}').
        """
        sensitive_patterns = ["password", "secret", "token", "api_key", "apikey", "access_key", "private_key"]

        allowed_placeholders = {"null", "none", "placeholder", "***"}

        def value_contains_secret(val: str) -> bool:
            low = val.lower()
            # Ignore common placeholders and templated variables
            if low in allowed_placeholders or ("${" in val and "}" in val):
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
                # Fail if a string value looks like it may contain a secret
                assert not value_contains_secret(node), f"Potential hardcoded credential value at {path}"
            # Non-string scalars (int, float, bool, None) are safe to ignore

        scan_for_secrets(pr_agent_config)

        safe_placeholders = {None, "null", "webhook"}

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

    def test_safe_configuration_values(self, pr_agent_config):
        """
        Assert that key numeric limits in the PR agent configuration fall within safe bounds.

        Checks that:
        - `limits['max_execution_time']` is less than or equal to 3600 seconds.
        - `limits['max_concurrent_prs']` is less than or equal to 10.
        - `limits['rate_limit_requests']` is less than or equal to 1000.
        """
        limits = pr_agent_config["limits"]

        # Check for reasonable numeric limits
        assert limits["max_execution_time"] <= 3600, "Execution time too high"
        assert limits["max_concurrent_prs"] <= 10, "Too many concurrent PRs"
        assert limits["rate_limit_requests"] <= 1000, "Rate limit too high"


class TestPRAgentConfigRemovedComplexity:
    """Test that complex features were properly removed."""

    @pytest.fixture
    @staticmethod
    def pr_agent_config_content():
        """
        Return the contents of .github / pr - agent - config.yml as a string.

        Reads the PR agent configuration file from the repository root and returns its raw text.

        Returns:
            str: Raw YAML content of .github / pr - agent - config.yml.
        """
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, "r") as f:
            return f.read()

    def test_no_summarization_settings(self, pr_agent_config_content):
        """Verify summarization settings removed."""
        assert "summarization" not in pr_agent_config_content.lower()
        assert "max_summary_tokens" not in pr_agent_config_content

    def test_no_token_management(self, pr_agent_config_content):
        """Verify token management settings removed."""
        assert "max_tokens" not in pr_agent_config_content
        assert "context_length" not in pr_agent_config_content

    def test_no_llm_model_references(self, pr_agent_config_content):
        """
        Ensure no explicit LLM model identifiers appear in the raw PR agent configuration.

        Parameters:
            pr_agent_config_content(str): Raw contents of .github / pr - agent - config.yml used for pattern checks.
        """
        assert "gpt-3.5-turbo" not in pr_agent_config_content
        assert "gpt-4" not in pr_agent_config_content
