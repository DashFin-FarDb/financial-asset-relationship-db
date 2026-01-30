"""
Validation tests for PR agent configuration changes.

Tests the simplified PR agent configuration, ensuring:
- Version downgrade from 1.1.0 to 1.0.0
- Removal of context chunking features
- Removal of tiktoken dependencies
- Simplified configuration structure
"""

import math
import re
from pathlib import Path

import pytest
import yaml

# Inline credentials embedded in URLs, e.g. scheme://user:password@host
INLINE_CREDS_RE = re.compile(
    r"^[A-Za-z][A-Za-z0-9+.-]*://[^@:\s]+:[^@\s]+@",
    re.IGNORECASE,
)

# Common secret / credential indicators used across heuristics
SECRET_MARKERS = (
    "secret",
    "token",
    "apikey",
    "api_key",
    "access_key",
    "private_key",
    "pwd",
    "password",
    "auth",
    "bearer",
)


def _shannon_entropy(value: str) -> float:
    """
    Calculate Shannon entropy of a string.

    Used as a heuristic to detect high-entropy tokens such as API keys.
    """
    if not value:
        return 0.0

    sample = value[:256]
    freq = {}

    for ch in sample:
        freq[ch] = freq.get(ch, 0) + 1

    entropy = 0.0
    length = len(sample)

    for count in freq.values():
        p = count / length
        entropy -= p * math.log2(p)

    return entropy


def _looks_like_secret(value: str) -> bool:
    """
    Determine whether a string value appears to be a secret.

    This function intentionally uses conservative heuristics to avoid
    false positives while still catching common credential patterns.
    """
    v = value.strip()
    if not v:
        return False

    # Known safe placeholders
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

    # Inline credentials in URLs
    if INLINE_CREDS_RE.search(v):
        return True

    # Keyword-based secret indicators
    if any(marker in v.lower() for marker in SECRET_MARKERS) and len(v) >= 12:
        return True

    # High-entropy base64 / URL-safe strings
    if re.fullmatch(r"[A-Za-z0-9_\-]{20,}", v) and _shannon_entropy(v) >= 3.5:
        return True

    # Hex-encoded secrets (e.g. hashes, keys)
    if re.fullmatch(r"[A-Fa-f0-9]{32,}", v):
        return True

    return False


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
        Load and parse the PR agent YAML configuration from
        .github/pr-agent-config.yml.
        """
        config_path = Path(".github/pr-agent-config.yml")
        if not config_path.exists():
            pytest.fail(f"Config file not found: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            try:
                cfg = yaml.safe_load(f)
            except yaml.YAMLError as exc:
                pytest.fail(f"Invalid YAML in config: {exc}")

        if not isinstance(cfg, dict):
            pytest.fail("Config must be a non-empty YAML mapping")

        return cfg

    # ------------------------------------------------------------------

    @staticmethod
    def scan(obj, suspected):
        """
        Recursively scan configuration objects for suspected secrets.
        """
        if isinstance(obj, dict):
            for value in obj.values():
                TestPRAgentConfigSecurity.scan(value, suspected)

        elif isinstance(obj, (list, tuple)):
            for item in obj:
                TestPRAgentConfigSecurity.scan(item, suspected)

        elif isinstance(obj, str) and _looks_like_secret(obj):
            suspected.append(("secret", obj))

    # ------------------------------------------------------------------

    @staticmethod
    def test_config_values_have_no_hardcoded_credentials(pr_agent_config):
        """
        Recursively scan configuration values for suspected secrets.
        """
        suspected = []
        TestPRAgentConfigSecurity.scan(pr_agent_config, suspected)

        if suspected:
            details = "\n".join(suspected)
            pytest.fail(f"Potential hardcoded credentials found in PR agent config:\n{details}")

    # ------------------------------------------------------------------

    @staticmethod
    def test_no_hardcoded_secrets(pr_agent_config):
        """
        Ensure sensitive keys only use safe placeholders or templated values.
        """
        sensitive_patterns = (
            "password",
            "secret",
            "token",
            "api_key",
            "apikey",
            "access_key",
            "private_key",
        )

        allowed_placeholders = {None, "null", "none", "placeholder", "***"}
        templated_var_re = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*\}$")

        def is_allowed_placeholder(v) -> bool:
            if v in allowed_placeholders:
                return True
            if isinstance(v, str) and templated_var_re.match(v.strip()):
                return True
            return False

        def scan_for_secrets(node, path="root"):
            if isinstance(node, dict):
                for k, v in node.items():
                    key_lower = str(k).lower()
                    new_path = f"{path}.{k}"

                    if any(p in key_lower for p in sensitive_patterns):
                        assert is_allowed_placeholder(v), f"Potential hardcoded credential at '{new_path}'"

                    scan_for_secrets(v, new_path)

            elif isinstance(node, (list, tuple)):
                for i, item in enumerate(node):
                    scan_for_secrets(item, f"{path}[{i}]")

        scan_for_secrets(pr_agent_config)

    # ------------------------------------------------------------------

    @staticmethod
    def test_safe_configuration_values(pr_agent_config):
        """
        Assert numeric configuration limits fall within safe bounds.
        """
        limits = pr_agent_config["limits"]

        assert limits["max_execution_time"] <= 3600
        assert limits["max_concurrent_prs"] <= 10
        assert limits["rate_limit_requests"] <= 1000


class TestPRAgentConfigRemovedComplexity:
    """Test that complex features were properly removed."""

    @staticmethod
    @pytest.fixture
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
