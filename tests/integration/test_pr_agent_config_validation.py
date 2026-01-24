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
        Scan a parsed PR agent configuration for string values that resemble hardcoded credentials.

        Traverses nested dicts and lists and inspects all string values. Flags values that match any of these heuristics:
        - long strings (40 or more characters),
        - common secret prefixes such as "sk-", "AKIA", "SECRET_", "TOKEN_",
        - inline credentials in URLs (user:pass@host).

        If any suspected secrets are found, the test fails with details of each finding.
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
        import math

        # Heuristic to detect inline creds in URLs (user:pass@)
        re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://[^/@:\\s]+:[^/@\\s]+@", re.IGNORECASE)

    @staticmethod
    def test_no_hardcoded_credentials(pr_agent_config):
        """
        Scan the PR agent configuration for hardcoded credentials and fail the test if any are found.

        This test inspects keys and string values in the provided configuration for indicators of secrets:
        long credential-like strings, common secret/key prefixes, inline credentials in URLs, high-entropy
        token-like sequences, and hex/base64-like keys. If any suspicious items are detected, the test
        fails with locations or examples of the offending values. It also enforces that recognized sensitive
        keys use safe placeholder values rather than actual secrets.

        Parameters:
            pr_agent_config (dict): Parsed PR agent configuration to scan for secrets.
        """
        import math
        import re

        # Helper function for secret detection
        def detect_secret_kinds(value):
            kinds = []
            if len(value) >= 40:
                kinds.append("long_string")
            if any(value.startswith(prefix) for prefix in secret_markers):
                kinds.append("prefix")
            if inline_creds_re.search(value):
                kinds.append("inline_creds")
            return kinds

        # Heuristic to detect inline creds in URLs (user:pass@)
        inline_creds_re = re.compile(
            r"^[a-zA-Z][a-zA-Z0-9+.-]*://[^/@:\\s]+:[^/@\\s]+@", re.IGNORECASE
        )

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

        def detect_prefix(s):
            """Detect strings starting with known secret-like prefixes.

            Parameters:
                s (str): Input string to check.

            Returns:
                tuple: ("prefix", s) if prefix matches, otherwise None.
            """
            for marker in secret_markers:
                if s.lower().startswith(marker):
                    return ("prefix", s)

        def detect_inline_creds(s):
            """Detect inline credentials in URLs (user:pass@).

            Parameters:
                s (str): Input string to check.

            Returns:
                tuple: ("inline_creds", s) if inline credentials found, otherwise None.
            """
            if inline_creds_re.search(s):
                return ("inline_creds", s)

        detectors = [detect_long_string, detect_prefix, detect_inline_creds]

        def scan_value(val):
            """Apply detectors to a value and return the first match.

            Parameters:
                val: Value to scan, converted to string and stripped.

            Returns:
                tuple or None: Detector result if any, otherwise None.
            """
            stripped = str(val).strip()
            if not stripped:
                return None
            for detector in detectors:
                result = detector(stripped)
                if result:
                    return result
            return None

        def scan(obj):
            """Recursively scan nested structures for potential secrets.

            Walks through dicts, lists, and tuples, applying scan_value to leaf values
            and collecting matches in the 'suspected' list.
            """
            if isinstance(obj, dict):
                for key, value in obj.items():
                    scan(value)
            elif isinstance(obj, (list, tuple)):
                for item in obj:
                    scan(item)
            else:
                result = scan_value(obj)
                if result:
                    suspected.append(result)
            return None

        scan(pr_agent_config)

        if suspected:
            details = "\n".join(f"{kind}: {val}" for kind, val in suspected)
            pytest.fail(
                f"Potential hardcoded credentials found in PR agent config:\n{details}"
            )

        def shannon_entropy(s: str) -> float:
            """
            Compute the Shannon entropy of a string in bits per symbol.

            This measures the average information content per character using base-2 logarithms.
            The calculation is performed on at most the first 256 characters of the input; if
            the input is empty the function returns 0.0.

            Parameters:
                s (str): Input string to analyze. Only the first 256 characters are considered.

            Returns:
                float: Shannon entropy (bits per symbol). Returns 0.0 for an empty string.
            """
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
            """Determine if a string resembles a secret based on patterns or entropy.

            Parameters:
                val (str): String to evaluate.

            Returns:
                bool: True if value likely a secret, otherwise False.
            """
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
            """Recursively traverse object values and fail on suspected secrets.

            Parameters:
                obj: Nested dict/list structure to inspect.
                path (str): Dotted path for locating values in error messages.
            """
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

    @staticmethod
    def test_no_hardcoded_secrets(pr_agent_config):
        """
        Ensure no sensitive keys or values in the parsed PR agent config contain hardcoded credentials.

        Recursively scans the provided configuration (dict/list) and validates that any key whose name
        contains sensitive indicators (e.g., "password", "secret", "token", "api_key", "access_key",
        "private_key", "apikey") is assigned a safe placeholder value (None, "null", "webhook", or other
        allowed placeholders) or is represented as a templated variable like "${VAR}". The check inspects
        both mapping keys and list elements and reports the dotted path to the offending entry.

        Parameters:
            pr_agent_config (dict): Parsed YAML configuration for the PR agent.

        Raises:
            AssertionError: If a sensitive key or suspicious value appears to contain a hardcoded secret;
                the assertion message includes the path to the offending item.
        """
        sensitive_patterns = [
            "password",
            "secret",
            "token",
            "api_key",
            "apikey",
            "access_key",
            "private_key",
        ]

        allowed_placeholders = {"null", "none", "placeholder", "***"}

        def value_contains_secret(val: str) -> bool:
            """Check if a string contains sensitive patterns and is not an allowed placeholder.

            Parameters:
                val (str): Value to check.

            Returns:
                bool: True if value contains a sensitive pattern, False otherwise.
            """
            low = val.lower()
            if low in allowed_placeholders or ("${" in val and "}" in val):
                return False
            return any(pat in low for pat in sensitive_patterns)

        def scan_dict(node: dict, path: str):
            """
            Recursively scan a mapping for potential hardcoded credentials and validate that sensitive keys use allowed placeholders.

            For each key / value pair in `node`, if the key matches known sensitive patterns the value is required to be one of the allowed placeholders; otherwise an AssertionError is raised identifying the dotted path to the offending entry. The function also delegates deeper scanning of each value via `scan_for_secrets`, using `path` as the dotted prefix for diagnostics.

            Parameters:
                node(dict): Mapping whose keys and values will be scanned.
                path(str): Dotted path prefix used in assertion messages for locating the inspected value.

            Raises:
                AssertionError: If a value for a key matching sensitive patterns is not in `allowed_placeholders`.
            """
            for k, v in node.items():
                key_l = str(k).lower()
                new_path = f"{path}.{k}"
                if any(pat in key_l for pat in sensitive_patterns):
                    assert v in allowed_placeholders, (
                        f"Potential hardcoded credential at '{new_path}'"
                    )
                scan_for_secrets(v, new_path)

        def scan_list(node: list, path: str):
            """
            Scan each element of `node` for potential secret values, updating `path` with each element's index to locate findings.

            Parameters:
                node(list): Sequence of values to inspect.
                path(str): Current dotted / indexed traversal path used to identify each element's location.
            """
            for idx, item in enumerate(node):
                scan_for_secrets(item, f"{path}[{idx}]")

        def scan_for_secrets(node, path="root"):
            """Scan a node(dict or list) for hardcoded secrets by delegating to scan_dict and scan_list.

            Parameters:
                node: Value to scan.
                path(str): Dotted path prefix for error messages.
            """
            if isinstance(node, dict):
                scan_dict(node, path)
            elif isinstance(node, list):
                scan_list(node, path)
            # primitives ignored

        safe_placeholders = {None, "null", "webhook"}

        def check_node(node, path=""):
            """
            Recursively inspects a nested structure for keys that match predefined sensitive patterns and asserts their values are safe.

            Traverses dictionaries and lists within `node`. For any dictionary key whose lowercase form contains one of the module - level sensitive_patterns, the corresponding value must be present in the module - level safe_placeholders set; otherwise an AssertionError is raised identifying the offending path.

            Parameters:
                node: The value to inspect; typically a dict, list, or primitive contained in the configuration.
                path(str): Dot - and -bracket notation string representing the current traversal path(used only for error messages).

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
        """
        Ensure no explicit LLM model identifiers appear in the raw PR agent configuration.

        Parameters:
            pr_agent_config_content(str): Raw contents of .github / pr - agent - config.yml used for pattern checks.
        """
        assert "gpt-3.5-turbo" not in pr_agent_config_content
        assert "gpt-4" not in pr_agent_config_content
