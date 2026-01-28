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
        """Ensure the `limits` section does not contain a `fallback` key."""
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
        Ensure every non-empty, non-comment line in .github/pr-agent-config.yml uses indentation in 2-space increments.

        Scans the file line by line and verifies that any leading spaces on applicable lines are a multiple of two.

        Raises:
            AssertionError: If a line's leading spaces are not a multiple of two. The message includes the line number and the number of leading spaces.
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
        Scan all string values in the parsed PR agent config for potential hardcoded credentials.

        This test inspects every string value in the nested mapping/list structure and flags values that match simple heuristics:
        - strings of length 40 or greater,
        - values starting with common secret prefixes (e.g., `sk-`, `AKIA`, `SECRET_`, `TOKEN_`),
        - inline credentials in URLs (user:pass@ patterns).

        If any suspected secrets are found, the test fails and reports each match with its heuristic type.

        Parameters:
            pr_agent_config (dict): Parsed YAML mapping of .github/pr-agent-config.yml to scan for secrets.
        """

        def _iter_string_values(obj):
            """
            Recursively yield all string values from nested dict/list structures.

            Args:
                obj (str | dict | list): The object to iterate over for string values.

            Yields:
                str: Each string found within the nested object.
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

        Recursively inspects string values for secret-like patterns (inline credentials in URLs, common secret prefixes, long high-entropy tokens, or long hex strings) and asserts that sensitive keys (e.g., password, secret, token, api_key, access_key, private_key) only contain safe placeholders. Fails the test with a descriptive message when a suspected secret value or an unsafe sensitive key/value is detected.
        """
        import math

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

        # Sensitive keys to check for unsafe hardcoded values
        sensitive_keys = (
            "password",
            "secret",
            "token",
            "api_key",
            "access_key",
            "private_key",
        )

        def is_long_string(val):
            return len(val) >= 40

        def has_secret_prefix(val):
            return any(val.startswith(p) for p in secret_markers)

        def has_inline_creds(val):
            return bool(inline_creds_re.search(val))

        suspected = []

        def scan(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if (
                        isinstance(v, str)
                        and any(sk in k.lower() for sk in sensitive_keys)
                        and not (v.startswith("{{") and v.endswith("}}"))
                    ):
                        suspected.append((f"unsafe_key:{k}", v.strip()))
                        continue
                    scan(v)
            elif isinstance(obj, list):
                for item in obj:
                    scan(item)
            elif isinstance(obj, str):
                s = obj.strip()
                if is_long_string(s):
                    suspected.append(("long_string", s))
                elif has_secret_prefix(s):
                    suspected.append(("prefix", s))
                elif has_inline_creds(s):
                    suspected.append(("inline_creds", s))

        scan(pr_agent_config)

        if suspected:
            details = "\n".join(f"{kind}: {val}" for kind, val in suspected)
            pytest.fail(
                f"Potential hardcoded credentials found in PR agent config:\n{details}"
            )

        def shannon_entropy(s: str) -> float:
            """Compute the Shannon entropy of a string, measuring its randomness based on character frequencies."""
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
            """Determine if a given string value resembles a secret based on known patterns, markers, and entropy."""
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
            """Recursively traverse the object, inspecting string values for secrets and failing the test upon detection."""
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
            "password",
            "secret",
            "token",
            "api_key",
            "apikey",
            "access_key",
            "private_key",
        ]
        safe_placeholders = {None, "null", "webhook"}

        def check_sensitive_keys(node, path="root"):
            """
            Recursively validate that keys matching sensitive patterns map only to allowed placeholder values.

            Traverses mappings and lists in `node`. For any dictionary key whose lowercase form matches any of the configured sensitive patterns, asserts that the corresponding value is one of the allowed safe placeholders; the assertion includes the dotted/bracketed `path` to the offending key. Non-dictionary/list primitives are ignored.

            Parameters:
                node: The value to scan (may be a dict, list, or primitive).
                path (str): Current traversal path used in assertion messages (defaults to "root").

            Raises:
                AssertionError: If a sensitive key is found whose value is not in the allowed placeholders.
            """
            if isinstance(node, dict):
                for k, v in node.items():
                    key_l = str(k).lower()
                    new_path = f"{path}.{k}"
                    if any(p in key_l for p in sensitive_patterns):
                        assert v in safe_placeholders, (
                            f"Potential hardcoded credential at '{new_path}'"
                        )

    @staticmethod
    def test_no_hardcoded_secrets(pr_agent_config):
        """
        Ensure keys or values that indicate credentials or secrets are replaced with safe placeholders.

        Scans the provided parsed YAML mapping recursively. If a string value contains sensitive indicators (for example: "password", "secret", "token", "api_key", "apikey", "access_key", "private_key") it must be a safe placeholder such as "null", "none", "placeholder", "***", or a templated variable like "${VAR}". If a mapping key name contains one of those sensitive indicators, its associated value must be one of the safe key placeholders: None, "null", or "webhook". Violations raise an AssertionError that includes the YAML path to the offending node.

        Parameters:
            pr_agent_config (dict): Parsed .github/pr-agent-config.yml content as a nested mapping/list structure to validate.

        Raises:
            AssertionError: If a secret-like string value or a sensitive key mapped to a non-placeholder value is detected; the assertion message includes the path to the problematic node.
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

        def is_sensitive_key(key: str) -> bool:
            return any(pat in key.lower() for pat in sensitive_patterns)

        def is_placeholder(val: str) -> bool:
            low = val.lower()
            return low in allowed_placeholders or (
                low.startswith("${") and low.endswith("}")
            )

        def validate_node(node, path: str = ""):
            if isinstance(node, dict):
                for key, value in node.items():
                    current_path = f"{path}.{key}" if path else key
                    if is_sensitive_key(key):
                        assert (value is None) or (
                            isinstance(value, str)
                            and value.lower() in {"null", "webhook"}
                        ), (
                            f"Sensitive key '{key}' must have a safe placeholder at path: {current_path}"
                        )
                    validate_node(value, current_path)
            elif isinstance(node, list):
                for idx, item in enumerate(node):
                    validate_node(item, f"{path}[{idx}]")
            elif isinstance(node, str):
                low = node.lower()
                if any(pat in low for pat in sensitive_patterns) and not is_placeholder(
                    node
                ):
                    assert False, (
                        f"Potential hardcoded credential at path: {path}: '{node}'"
                    )
            # primitives other than str are ignored

        validate_node(pr_agent_config)

        # Final serialized scan to ensure sensitive markers aren't embedded in values
        config_str = yaml.dump(pr_agent_config)
        for pat in sensitive_patterns:
            if pat in config_str:
                assert (" null" in config_str) or ("webhook" in config_str), (
                    f"Potential hardcoded credential found around pattern: {pat}"
                )
            # Ignore common placeholders and templated variables
            if low in allowed_placeholders or ("${" in val and "}" in val):
                return False
            return any(pat in low for pat in sensitive_patterns)

        def scan_dict(node: dict, path: str):
            for k, v in node.items():
                key_l = str(k).lower()
                new_path = f"{path}.{k}"
                if any(pat in key_l for pat in sensitive_patterns):
                    assert v in allowed_placeholders, (
                        f"Potential hardcoded credential at '{new_path}'"
                    )
                scan_for_secrets(v, new_path)

        def scan_list(node: list, path: str):
            for idx, item in enumerate(node):
                scan_for_secrets(item, f"{path}[{idx}]")

        def scan_for_secrets(node, path="root"):
            """
            Recursively scan a nested data structure and assert there are no string values that appear to contain hardcoded secrets.

            Traverses mappings, sequences, and string leaves; if a string value appears to contain credentials or secret-like content, the function fails with an assertion that includes the path to the offending value.

            Parameters:
                node: The root node to scan; may be a dict, list, or scalar.
                path (str): Dot/bracket notation path used in assertion messages to locate the current node (defaults to "root").
            """
            if isinstance(node, dict):
                scan_dict(node, path)
            elif isinstance(node, list):
                scan_list(node, path)
            # primitives ignored

        safe_placeholders = {None, "null", "webhook"}

        def check_node(node, path=""):
            """
            Recursively scan a nested mapping/list structure and assert that sensitive keys map only to allowed placeholders.

            Traverses dictionaries and lists, building a dotted/bracketed path for error messages. For any dictionary key whose lowercase form contains a substring from the surrounding `sensitive_patterns`, asserts that the corresponding value is one of the surrounding `safe_placeholders`; on assertion failure the message includes the offending path.

            Parameters:
                node: The nested value to scan (dict, list, or primitive).
                path (str): Current dotted/bracketed path used in assertion messages (defaults to empty string).
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
