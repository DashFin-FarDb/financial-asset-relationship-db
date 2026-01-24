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

    @staticmethod
    def test_version_reverted_to_1_0_0(pr_agent_config):
        """Check that the PR agent's configured version is '1.0.0'."""
        assert pr_agent_config["agent"]["version"] == "1.0.0"

    @staticmethod
    def test_no_context_configuration(pr_agent_config):
        """
        Assert that the 'agent' section does not contain a 'context' key.

        The test fails if the parsed PR agent configuration includes a 'context' key under the top-level 'agent' section.
        """
        agent_config = pr_agent_config["agent"]
        assert "context" not in agent_config

    @staticmethod
    def test_no_chunking_settings(pr_agent_config):
        """
        Assert the configuration contains no chunking-related settings.

        Checks that the keys 'chunking', 'chunk_size' and 'overlap_tokens' do not appear in the serialized configuration string (case-insensitive).
        """
        config_str = yaml.dump(pr_agent_config)
        assert "chunking" not in config_str.lower()
        assert "chunk_size" not in config_str.lower()
        assert "overlap_tokens" not in config_str.lower()

    @staticmethod
    def test_no_tiktoken_references(pr_agent_config):
        """Verify tiktoken references removed."""
        config_str = yaml.dump(pr_agent_config)
        assert "tiktoken" not in config_str.lower()

    @staticmethod
    def test_no_fallback_strategies(pr_agent_config):
        """
        Ensure the top-level `limits` section does not contain a `fallback` key.
        """
        limits = pr_agent_config.get("limits", {})
        assert "fallback" not in limits

    @staticmethod
    def test_basic_config_structure_intact(pr_agent_config):
        """Verify basic configuration sections still present."""
        # Essential sections should remain
        assert "agent" in pr_agent_config
        assert "monitoring" in pr_agent_config
        assert "actions" in pr_agent_config
        assert "quality" in pr_agent_config
        assert "security" in pr_agent_config

    @staticmethod
    def test_monitoring_config_present(pr_agent_config):
        """
        Ensure the top-level monitoring section contains the keys 'check_interval', 'max_retries', and 'timeout'.

        Parameters:
            pr_agent_config (dict): Parsed PR agent configuration mapping.
        """
        monitoring = pr_agent_config["monitoring"]
        assert "check_interval" in monitoring
        assert "max_retries" in monitoring
        assert "timeout" in monitoring

    @staticmethod
    def test_limits_simplified(pr_agent_config):
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

    @staticmethod
    def test_config_is_valid_yaml():
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

    @staticmethod
    def test_no_duplicate_keys():
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

    @staticmethod
    def test_consistent_indentation():
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
                    assert indent % 2 == 0, (
                        f"Line {i} has inconsistent indentation: {indent} spaces"
                    )


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

    @staticmethod
    def test_config_values_have_no_hardcoded_credentials(pr_agent_config):
        """
        Scan the PR agent configuration for string values that resemble hardcoded credentials.

        This test inspects all string values in the provided configuration and fails if any value matches credential heuristics: strings of 40 or more characters, strings starting with common secret prefixes (e.g., "sk-", "AKIA", "SECRET_", "TOKEN_"), or inline credentials embedded in URLs (user:pass@host). On failure, the test reports each finding with its heuristic type and value.
        """

        def _iter_string_values(obj):
            """
            Recursively iterate through a nested structure of dicts and lists,
            yielding all string values found for subsequent secret scanning.
            """
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
            pytest.fail(
                f"Potential hardcoded credentials found in PR agent config:\n{details}"
            )

        # Heuristic to detect inline creds in URLs (user:pass@)
        re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://[^/@:\\s]+:[^/@\\s]+@", re.IGNORECASE)

    @staticmethod
    def test_no_hardcoded_credentials(pr_agent_config):
        """
        Scan the PR agent configuration for potential hardcoded credentials and fail the test if any are found.

        Uses heuristic checks (long strings, known secret-like prefixes, inline credentials in URLs, entropy/encoding patterns,
        and sensitive key names) to identify suspicious values and reports their locations via pytest.fail.

        Parameters:
            pr_agent_config (dict): Parsed PR agent configuration mapping to inspect for hardcoded secrets.
        """
        import re

        inline_creds_re = re.compile(
            r"^[a-zA-Z][a-zA-Z0-9+.-]*://[^/@:\\s]+:[^/@\\s]+@", re.IGNORECASE
        )
        secret_markers = (
            "secret",
            "token",
            "apikey",
            "api_key",
            "access_key",
        )
        suspected = []

        def is_suspected(key, val):
            s = str(val).strip()
            if not s:
                return None
            if any(marker in key.lower() for marker in secret_markers):
                return "key_name"
            if len(s) >= 40:
                return "long_string"
            if any(s.startswith(p) for p in secret_prefixes):
                return "prefix"
            if inline_creds_re.search(s):
                return "inline_creds"
            return None

        for section, section_config in pr_agent_config.items():
            for key, val in section_config.items():
                kind = is_suspected(key, val)
                if kind:
                    suspected.append((kind, str(val).strip()))

        if suspected:
            details = "\n".join(f"{kind}: {val}" for kind, val in suspected)
            pytest.fail(
                f"Potential hardcoded credentials found in PR agent config:\n{details}"
            )
            return len(val) >= 40

        def check_prefix(val):
            """Check if the string starts with any common secret or key prefix marker."""
            lowered = val.lower()
            return any(lowered.startswith(marker) for marker in secret_markers)

        def check_inline_creds(val):
            """Detect inline credentials in URLs using a scheme://user:pass@ pattern."""
            return bool(inline_creds_re.search(val))

        checkers = [
            ("long_string", check_long_string),
            ("prefix", check_prefix),
            ("inline_creds", check_inline_creds),
        ]

        for _, value in pr_agent_config.items():
            if not isinstance(value, str):
                continue
            stripped = value.strip()
            for kind, checker in checkers:
                if checker(stripped):
                    suspected.append((kind, stripped))
                    break

        if suspected:
            details = "\n".join(f"{kind}: {val}" for kind, val in suspected)
            pytest.fail(
                f"Potential hardcoded credentials found in PR agent config:\n{details}"
            )

        suspected = []

        # Define detectors for credential heuristics
        def detect_long_string(s):
            """Detect long strings (>=40 characters) that may indicate embedded secrets.

            Parameters:
                s (str): Input string to check.

            Returns:
                tuple: ("long_string", s) if length >= 40, otherwise None.
            """
            if len(s) >= 40:
                return ("long_string", s)
            return None

        def detect_prefix(s):
            """
            Identify whether a string begins with a known secret-like prefix.

            Parameters:
                s (str): String to inspect; matching is case-insensitive against the global `secret_markers`.
            "api_key",
            "apikey",
            "access_key",
            "private_key",
        ]
        # Values considered safe placeholders
        allowed_placeholders = {None, "null", "webhook"}

        def matches_sensitive(key):
            key_lower = key.lower()
            return any(pattern in key_lower for pattern in sensitive_patterns)

        def is_placeholder(value):
            if value in allowed_placeholders:
                return True
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                return True
            return False

        def check_key(path, key, value):
            if matches_sensitive(key) and not is_placeholder(value):
                raise AssertionError(
                    f"Hardcoded secret found at {path}: key '{key}' has disallowed value '{value}'"
                )

        def recurse(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_path = f"{path}.{key}" if path else key
                    if isinstance(value, (dict, list, tuple)):
                        recurse(value, current_path)
                    else:
                        check_key(current_path, key, value)
            elif isinstance(obj, (list, tuple)):
                for idx, item in enumerate(obj):
                    current_path = f"{path}[{idx}]"
                    if isinstance(item, (dict, list, tuple)):
                        recurse(pr_agent_config)

        def shannon_entropy(s):
            from collections import Counter
            import math
            counts = Counter(s).values()
            probabilities = [count / len(s) for count in counts]
            return -sum(p * math.log2(p) for p in probabilities)

        def is_allowed_value(val):
            """Return True if val is an allowed placeholder or a variable substitution(${...}); False otherwise."""
            if val in allowed_placeholders:
                return True
            if isinstance(val, str) and val.startswith("${") and val.endswith("}"):
                return True
            return False

        def is_hardcoded_secret(val):
            """Determine if a string value is likely a hardcoded secret by checking for sensitive markers, high entropy, or encoding patterns."""
            if not isinstance(val, str):
                return False
            low = val.lower()
            # Marker-based secrets
            if any(marker in low for marker in sensitive_patterns) and len(val) >= 12:
                return True
            # Base64/URL-safe like long strings
            if (
                re.fullmatch(r"[A-Za-z0-9_\-]{20,}", val)
                and shannon_entropy(val) >= 3.5
            ):
                return True
            # Hex-encoded long strings (e.g., keys)
            if re.fullmatch(r"[A-Fa-f0-9]{32,}", val):
                return True
            return False

        suspected = []

        def scan(obj, path=""):
            """Recursively scan the object for potential hardcoded secrets, populating 'suspected' list with (path, value) tuples when found."""
            if isinstance(obj, dict):
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    if any(pat in key.lower() for pat in sensitive_patterns):
                        if not is_allowed_value(value):
                            suspected.append((new_path, value))
                    else:
                        scan(value, new_path)
            elif isinstance(obj, (list, tuple)):
                for idx, item in enumerate(obj):
                    scan(item, f"{path}[{idx}]")
            else:
                if is_hardcoded_secret(obj):
                    suspected.append((path, obj))

        scan(pr_agent_config)

        if suspected:
            details = "\n".join(f"{p}: {v}" for p, v in suspected)
            pytest.fail(
                f"Potential hardcoded credentials found in PR agent config:\n{details}"
            )
        allowed_placeholders = {None, "null", "webhook"}

        def is_sensitive_key(key):
            """Return True if the key name contains any of the predefined sensitive patterns."""
            key_lower = key.lower()
            return any(pattern in key_lower for pattern in sensitive_patterns)

        def is_templated_value(val):
            """Return True if the value is a templated string of the form "${VAR}"."""
            return isinstance(val, str) and val.startswith("${") and val.endswith("}")

        def is_safe_value(val):
            """Return True if the value is one of the allowed placeholders or a valid templated variable."""
            return val in allowed_placeholders or is_templated_value(val)

        def check_entry(path, key, value):
            """Assert that a sensitive key at the given path does not contain a hardcoded value or suspicious secret."""
            from tests.utils import looks_like_secret

            if is_sensitive_key(key) and not is_safe_value(value):
                pytest.fail(
                    f"Sensitive key '{path}.{key}' contains hardcoded value: {value}"
                )

            if isinstance(value, str) and looks_like_secret(value):
                pytest.fail(
                    f"Suspected secret value at '{path}.{key}': {value[:20]}..."
                )

        def traverse(obj, path="root"):
            """Recursively traverse the configuration object, applying checks at each mapping key and list item."""
            if isinstance(obj, dict):
                for k, v in obj.items():
                    check_entry(path, k, v)
                    traverse(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    traverse(item, f"{path}[{i}]")
            # Non-string scalars ignored

        traverse(pr_agent_config)

        allowed_placeholders = {"null", "none", "placeholder", "***"}

        safe_placeholders = {None, "null", "webhook"}

        def check_node(node, path=""):
            """
            Recursively validate that values stored under sensitive keys are not hardcoded secrets.

            Inspects dictionaries and lists within `node`. If a dictionary key(lowercased) contains any substring from the module - level `sensitive_patterns`, its value must be one of the module - level `safe_placeholders`; otherwise an AssertionError is raised identifying the dotted / bracketed path to the offending value.

            Parameters:
                node: The value to inspect; typically a dict, list, or primitive from the configuration.
                path(str): Current traversal path in dotted / bracket notation used in error messages(defaults to the empty string).

            Raises:
                AssertionError: If a value is found under a sensitive key that is not listed in `safe_placeholders`.
            """
            if isinstance(node, dict):
                for k, v in node.items():
                    key_l = str(k).lower()
                    new_path = f"{path}.{k}" if path else str(k)
                    if any(p in key_l for p in sensitive_patterns):
                        assert v in safe_placeholders, (
                            f"Potential hardcoded credential at '{new_path}'"
                        )
                    check_node(v, new_path)
            elif isinstance(node, list):
                for idx, item in enumerate(node):
                    check_node(item, f"{path}[{idx}]")
            # primitives are ignored unless hit via a sensitive key above

        check_node(pr_agent_config)

    @staticmethod
    def test_safe_configuration_values(pr_agent_config):
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
    def pr_agent_config_content(self) -> str:
        """Raw YAML content of .github / pr - agent - config.yml."""
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, "r") as f:
            return f.read()

    @staticmethod
    def test_no_summarization_settings(pr_agent_config_content):
        """Verify summarization settings removed."""
        assert "summarization" not in pr_agent_config_content.lower()
        assert "max_summary_tokens" not in pr_agent_config_content

    @staticmethod
    def test_no_token_management(pr_agent_config_content):
        """Verify token management settings removed."""
        assert "max_tokens" not in pr_agent_config_content
        assert "context_length" not in pr_agent_config_content

    @staticmethod
    def test_no_llm_model_references(pr_agent_config_content):
        """Ensure no explicit LLM model identifiers appear in the raw PR agent configuration."""
        assert "gpt-3.5-turbo" not in pr_agent_config_content
        assert "gpt-4" not in pr_agent_config_content
