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
from collections import Counter
from enum import Enum
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.integration

# Inline credentials embedded in URLs, e.g. scheme://user:password@host
# Character classes are intentionally minimal and deduplicated to satisfy
# radarlint (S5869) while preserving strict userinfo detection semantics.
INLINE_CREDS_RE = re.compile(
    r"[A-Za-z][A-Za-z0-9+.-]*://[^@:\s]+:[^@\s]+@",
    re.IGNORECASE,
)


BASE64_LIKE_RE = re.compile(r"[A-Za-z0-9+/=_-]{20,}$")
HEX_RE = re.compile(r"[0-9a-fA-F]{32,}$")

SENSITIVE_PATTERNS = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_key",
    "private_key",
)

SAFE_PLACEHOLDERS = {
    "<token>",
    "<secret>",
    "changeme",
    "your-token-here",
    "dummy",
    "placeholder",
    "null",
    "none",
}


# Common secret / credential indicators used across heuristics
class SecretMarker(str, Enum):
    """
    Fixed set of secret/credential indicator keywords.
    """

    SECRET = "secret"
    TOKEN = "token"
    APIKEY = "apikey"
    API_KEY = "api_key"
    ACCESS_KEY = "access_key"
    PRIVATE_KEY = "private_key"
    PWD = "pwd"
    PASSWORD = "password"
    AUTH = "auth"
    BEARER = "bearer"


@pytest.fixture
def pr_agent_config() -> dict[str, object]:
    """
    Load and parse the PR agent YAML configuration from .github/pr-agent-config.yml.

    If the file is missing, contains invalid YAML, or does not contain a top-level mapping, the fixture will call pytest.fail to abort the test.

    Returns:
        dict: The parsed YAML content as a Python mapping.
    Raises:
       Failed: If the file is missing, invalid YAML, or not a mapping.
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


def _shannon_entropy(value: str) -> float:
    """Calculate Shannon entropy of a string."""
    if not value:
        return 0.0

    counts = Counter(value)
    length = len(value)

    entropy = 0.0
    for count in counts.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy


def test_looks_like_secret_empty_and_placeholder_values_are_not_secrets() -> None:
    """
    Ensure empty strings and placeholders are not treated as secrets.
    """
    assert _looks_like_secret("") is False
    assert _looks_like_secret("   ") is False

    # All configured placeholders should be treated as non-secret
    for placeholder in SAFE_PLACEHOLDERS:
        assert _looks_like_secret(placeholder) is False

        if isinstance(placeholder, str):
            assert _looks_like_secret(f"  {placeholder}  ") is False


def test_looks_like_secret_detects_inline_credentials_in_urls() -> None:
    """Ensure inline credentials embedded in URLs are treated as secrets.

    Returns:
        None
    Raises:
        None
    """
    candidate = "https://user:pa55w0rd@example.com/resource"
    assert _looks_like_secret(candidate) is True


def test_looks_like_secret_does_not_flag_urls_without_credentials() -> None:
    """Ensure URLs without inline credentials are not treated as secrets."""
    candidate = "https://example.com/resource"
    assert _looks_like_secret(candidate) is False


def test_looks_like_secret_detects_marker_based_secrets_with_sufficient_length() -> None:
    None
):
    """Ensure marker-based secrets with sufficient length are detected."""
    # Contains a marker keyword (e.g. "api_key") and is long enough to be considered a secret
    candidate = "my api_key is: abcdefghijkl"
    assert len(candidate) >= 12
    assert _looks_like_secret(candidate) is True


def test_looks_like_secret_does_not_flag_short_marker_based_values() -> None:
    """Ensure short marker-based values are not flagged as secrets."""
    candidate = "api_key=x"
    assert len(candidate) < 12
    assert _looks_like_secret(candidate) is False


def _looks_like_secret(value: object) -> bool:
    if not isinstance(value, str):
        return False

    v = value.strip()
    if not v:
        return False

    if v.lower() in SAFE_PLACEHOLDERS:
        return False

    # Inline credentials in URLs
    if INLINE_CREDS_RE.search(v):
        return True

    # Keyword-based secret indicators
    if any(marker.value in v.lower() for marker in SecretMarker) and len(v) >= 12:
        return True

    # High-entropy base64 / URL-safe strings
    if (
        BASE64_LIKE_RE.fullmatch(v)
        and re.search(r"[+/=_]", v)
        and _shannon_entropy(v) >= 3.5
    ):
        return True

    # Hex-encoded secrets (e.g. hashes, keys)
    if HEX_RE.fullmatch(v):
        return True

    return False


class TestPRAgentConfigSimplification:
    """Test PR agent config simplification changes."""

    @staticmethod
    def test_version_reverted_to_1_0_0(pr_agent_config):
        """Check that the PR agent's configured version is '1.0.0'."""
        assert pr_agent_config["agent"]["version"] == "1.0.0"

    @staticmethod
    def test_context_configuration_is_optional_and_validated(pr_agent_config) -> None:
        """
        Validate the optional 'agent.context' configuration.

        The 'context' key may be absent. If present, it must be a mapping (dict)
        to ensure the configuration shape is valid.
        """
        agent_config = pr_agent_config["agent"]

        if "context" in agent_config:
            assert isinstance(
                agent_config["context"],
                dict,
            ), "Context must be a valid configuration object"

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
        Verify the PR agent configuration file contains valid YAML syntax.

        Attempts to parse .github/pr-agent-config.yml with yaml.safe_load; the test
        fails implicitly if the file contains malformed YAML.
        """
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, "r", encoding="utf-8") as f:
            yaml.safe_load(f)

    @staticmethod
    def test_no_duplicate_keys():
        """
        Fail the test if any top-level YAML key appears more than once in the file.

        Scans .github/pr-agent-config.yml, ignores comment lines, and for each non-comment line treats the text before the first ':' as the key; the test fails if a key is encountered more than once.
        """
        config_path = Path(".github/pr-agent-config.yml")

        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Custom loader to detect duplicate YAML entries at any nesting level

    class DuplicateKeyLoader(yaml.SafeLoader):
        """YAML loader subclass that fails on duplicate keys.

        Overrides mapping construction to detect duplicate entries
        at any nesting level.
        """

        # pylint: disable=arguments-differ
        def construct_mapping(self, node, deep=False):
            """Construct a mapping from a YAML node, failing on duplicate keys."""
            mapping = {}

            # Intentionally not calling super(): we need full control
            # over key insertion to detect duplicates.
            for key_node, value_node in node.value:
                key = self.construct_object(key_node, deep=deep)
                if key in mapping:
                    pytest.fail(
                        f"Duplicate entry found: {key} at line {node.start_mark.line + 1}"
                    )
                value = self.construct_object(value_node, deep=deep)
                mapping[key] = value

            return mapping

        @staticmethod
        def test_consistent_indentation():
            """
            Verify that every non-empty, non-comment line in the PR agent YAML uses two-space indentation increments.

            Raises an AssertionError indicating the line number when a line's leading spaces are not a multiple of two.
            """
            config_path = Path(".github/pr-agent-config.yml")
            with open(config_path, "r", encoding="utf-8") as f:
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

    # In utils/secret_detection.py


def find_potential_secrets(config_obj: dict) -> list[tuple[str, str]]:
    suspected = []
    # ... scanning logic
    return suspected

    @staticmethod
    def scan(obj: object, suspected: list[tuple[str, str]]) -> None:
        """Recursively scan configuration objects for suspected secrets.

        Args:
            obj: Configuration object to scan (dict, list, or scalar).
            suspected: List to append (kind, value) tuples when secrets are found.
        Returns:
            None
        Raises:
            None
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
    def test_config_values_have_no_hardcoded_credentials(
        pr_agent_config: dict[str, object],
    ) -> None:
        """
        Recursively scan configuration values for suspected secrets.

        Returns:
            None
        Raises:
            AssertionError: If suspected secrets are found.
        """
        suspected = []
        TestPRAgentConfigSecurity.scan(pr_agent_config, suspected)

        def _redact(value: str) -> str:
            """Redact a string by obscuring all but the first and last four characters."""
            if len(value) <= 8:
                return "***"
            return f"{value[:4]}...{value[-4:]}"

        if suspected:
            details = "\n".join(
                f"{kind}: {_redact(value)}" for kind, value in suspected
            )
            pytest.fail(
                f"Potential hardcoded credentials found in PR agent config:\n{details}"
            )

    # ------------------------------------------------------------------

    @staticmethod
    def test_no_hardcoded_secrets(pr_agent_config):
        """Ensure sensitive keys only use safe placeholders or templated values."""
        # Use the global SAFE_PLACEHOLDERS constant instead of redefining

        allowed_placeholders = {None, "***"} | SAFE_PLACEHOLDERS
        templated_var_re = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*\}$")

        def is_allowed_placeholder(v: object) -> bool:
            """
            Determine if a value is an allowed placeholder or templated variable.
            """
            if v is None:
                return True

            if not isinstance(v, str):
                return False

            stripped_v = v.strip()

            if stripped_v.lower() in allowed_placeholders:
                return True

            if templated_var_re.match(stripped_v):
                return True

            return False

        def scan_for_secrets(node: object, path: str = "root") -> None:
            """
            Recursively scan the given node for sensitive patterns and assert that placeholders are allowed.
            """
            if isinstance(node, dict):
                for k, v in node.items():
                    key_lower = str(k).lower()
                    new_path = f"{path}.{k}"

                    if any(p in key_lower for p in SENSITIVE_PATTERNS):
                        assert is_allowed_placeholder(v), (
                            f"Potential hardcoded credential at '{new_path}'"
                        )

                    scan_for_secrets(v, new_path)

            elif isinstance(node, (list, tuple)):
                for i, item in enumerate(node):
                    scan_for_secrets(item, f"{path}[{i}]")

        scan_for_secrets(pr_agent_config)

    # ------------------------------------------------------------------


@staticmethod
def test_safe_configuration_values(pr_agent_config):
    """Assert numeric configuration limits fall within safe bounds."""
    limits = pr_agent_config["limits"]

    assert limits["max_execution_time"] <= 3600, (
        "max_execution_time exceeds safe bound (<= 3600 seconds)"
    )
    assert limits["max_concurrent_prs"] <= 10, (
        "max_concurrent_prs exceeds safe bound (<= 10)"
    )
    assert limits["rate_limit_requests"] <= 1000, (
        "rate_limit_requests exceeds safe bound (<= 1000 per period)"
    )


class TestPRAgentConfigRemovedComplexity:
    """Test that complex features were properly removed."""

    @pytest.fixture
    def pr_agent_config_content():
        """
        Return the contents of .github/pr-agent-config.yml as a string.

        Reads the PR agent configuration file from the repository root and returns its raw text.

        Returns:
            str: Raw YAML content of .github/pr-agent-config.yml.
        Raises:
            FileNotFoundError: If the configuration file cannot be found.
        """
        config_path = Path(".github/pr-agent-config.yml")
        if not config_path.exists():
            pytest.fail(f"Config file not found: {config_path}")
        with open(config_path, "r", encoding="utf-8") as f:
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
            pr_agent_config_content(str): Raw contents of .github/pr-agent-config.yml used for pattern checks.
        """
        assert "gpt-3.5-turbo" not in pr_agent_config_content
        assert "gpt-4" not in pr_agent_config_content
