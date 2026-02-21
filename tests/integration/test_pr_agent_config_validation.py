"""
Validation tests for PR agent configuration changes.

Tests the simplified PR agent configuration, ensuring:
- Version downgrade from 1.1.0 to 1.0.0
- Removal of context chunking features
- Removal of tiktoken dependencies
- Simplified configuration structure
"""

import re
from enum import Enum
from pathlib import Path

import numpy as np
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
HEX_RE = re.compile(r"[0-9a-fA-F]{16,}$")

sensitive_patterns = (
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

    Returns:
        SecretMarker: Enum member representing a secret marker.
    Raises:
        None
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
    Load and return the PR agent configuration from .github/pr-agent-config.yml.

    Aborts the test with pytest.fail if the file is missing, cannot be parsed as YAML, or does not contain a top-level mapping.

    Returns:
        dict[str, object]: Parsed YAML content as a Python mapping.
    """
    config_path = Path(".github/pr-agent-config.yml")
    if not config_path.exists():
        pytest.fail(f"Config file not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if cfg is None or not isinstance(cfg, dict):
        pytest.fail("Config must be a YAML mapping (dict) and not empty")
    return cfg


def _shannon_entropy(value: str) -> float:
    """
    Compute the Shannon entropy of a string to quantify its character-level randomness.

    Parameters:
        value (str): The string to analyze.

    Returns:
        float: Shannon entropy in bits per character; 0.0 for empty input.
    """
    if not value:
        return 0.0

    sample = np.frombuffer(value.encode("utf-8"), dtype=np.uint8)
    if sample.size == 0:
        return 0.0
    counts = np.bincount(sample)
    probs = counts[counts > 0] / sample.size
    return float(-np.sum(probs * np.log2(probs)))


def _looks_like_secret(value: str) -> bool:
    """
    Detects whether a string value appears to contain a secret or credential.

    Parameters:
        value (str): The string to inspect.

    Returns:
        bool: `true` if the string appears to be a secret, `false` otherwise.
    """
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
    if BASE64_LIKE_RE.fullmatch(v) and _shannon_entropy(v) >= 3.5:
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
    def test_no_context_configuration(pr_agent_config):
        """
        Verify the top-level "agent" section does not include a "context" key.

        The test fails if the parsed PR agent configuration contains a "context" mapping under the top-level "agent" section.
        """
        agent_config = pr_agent_config["agent"]
        assert "context" not in agent_config

    @staticmethod
    def test_no_chunking_settings(pr_agent_config):
        """
        Validate that the serialized PR agent configuration does not include chunking-related settings.

        Checks the serialized YAML for absence (case-insensitive) of the keys: `chunking`, `chunk_size`, and `overlap_tokens`.
        """
        config_str = yaml.dump(pr_agent_config)
        assert "chunking" not in config_str.lower()
        assert "chunk_size" not in config_str.lower()
        assert "overlap_tokens" not in config_str.lower()

    @staticmethod
    def test_no_tiktoken_references(pr_agent_config):
        """
        Fail the test if the serialized PR agent configuration contains any reference to "tiktoken".

        Parameters:
            pr_agent_config (dict): Parsed PR agent configuration loaded from .github/pr-agent-config.yml.
        """
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
        Verify the top-level "monitoring" section contains the required keys: "check_interval", "max_retries", and "timeout".

        Parameters:
            pr_agent_config (dict): Parsed PR agent configuration mapping loaded from .github/pr-agent-config.yml.
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
        Assert that .github/pr-agent-config.yml contains valid YAML.

        Parses the repository file and fails the test if a YAML parsing error occurs.
        """
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, "r", encoding="utf-8") as f:
            yaml.safe_load(f)

    @staticmethod
    def test_no_duplicate_keys():
        """
        Check .github/pr-agent-config.yml for duplicate mapping keys and fail the test if any are found.

        Parses the file and fails with pytest.fail when a mapping key appears more than once at any nesting level; the failure message includes the duplicated key and its line number.
        """
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Custom loader to detect duplicate YAML entries at any nesting level
        class DuplicateKeyLoader(yaml.SafeLoader):
            """YAML loader subclass that fails on duplicate keys.

            Overrides construct_mapping to detect duplicate entries at any nesting level and fails the test if found.
            """

            def construct_mapping(self, node, deep=False):
                """
                Constructs a Python dict from a YAML mapping node and fails the test if duplicate keys are encountered.

                Parameters:
                    node: YAML mapping node expected to provide `.value` (sequence of key/value node pairs) and `start_mark.line` for keys.
                    deep (bool): If True, construct nested objects recursively.

                Returns:
                    dict: Mapping of constructed keys to their constructed values.

                Raises:
                    pytest.fail: Fails the current test with a message that includes the 1-based line number when a duplicate key is found.
                """
                mapping = {}
                for entry_node, val_node in node.value:
                    entry = self.construct_object(entry_node, deep=deep)
                    if entry in mapping:
                        pytest.fail(
                            f"Duplicate entry found: {entry} at line {entry_node.start_mark.line + 1}"
                        )
                    value = self.construct_object(val_node, deep=deep)
                    mapping[entry] = value
                return mapping

        # Using yaml.load() with custom Loader is required for duplicate key detection.
        # DuplicateKeyLoader extends SafeLoader, so this is secure.
        yaml.load(content, Loader=DuplicateKeyLoader)

    @staticmethod
    def test_consistent_indentation():
        """
        Verify that each non-empty, non-comment line in the PR agent YAML uses indentation in two-space increments.

        Checks the file .github/pr-agent-config.yml and asserts on the first line whose leading spaces are not a multiple of two.

        Raises:
            AssertionError: If a line's leading spaces are not a multiple of two; the message includes the line number and the number of spaces.
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

    @staticmethod
    def scan(obj: object, suspected: list[tuple[str, str]]) -> None:
        """
        Recursively collect suspected secret values from a configuration object.

        Scans dicts, lists/tuples, and scalar values; when a string value appears secret, appends a ("secret", value) tuple to `suspected`.

        Parameters:
            obj (object): Configuration object to scan (may be a dict, list/tuple, or scalar).
            suspected (list[tuple[str, str]]): Mutable list that will be appended with (kind, value) tuples for each suspected secret.
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
        Scan the PR agent configuration for values that resemble hardcoded credentials and fail the test if any are detected.

        Parameters:
            pr_agent_config (dict[str, object]): Parsed PR agent YAML configuration to inspect.
        """
        suspected = []
        TestPRAgentConfigSecurity.scan(pr_agent_config, suspected)

        def _redact(value: str) -> str:
            """
            Redact a string, preserving the first and last four characters when possible.

            Returns:
                `***` if the input length is 8 characters or fewer, otherwise a string in the form `<first4>...<last4>` where the middle is replaced by an ellipsis.
            """
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

        allowed_placeholders = {None, "***"} | SAFE_PLACEHOLDERS
        templated_var_re = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*\}$")

        def is_allowed_placeholder(v: object) -> bool:
            """
            Check whether a value is an allowed placeholder or a templated variable.

            Parameters:
                v (object): The value to evaluate. None and strings that match known placeholder values
                    or the templated-variable pattern are considered allowed.

            Returns:
                bool: `True` if `v` is None, a recognized placeholder string, or matches the templated-variable
                regular expression; `False` otherwise.
            """
            if v is None:
                return True
            if isinstance(v, str):
                candidate = v.strip().lower()
                if candidate in allowed_placeholders:
                    return True
                if templated_var_re.match(candidate):
                    return True
            return False

        def scan_for_secrets(node: object, path: str = "root") -> None:
            """
            Recursively validate configuration values for sensitive keys and assert they use allowed placeholders.

            Traverse mappings, lists, and tuples; when a mapping key contains any pattern from `sensitive_patterns`, validate its value with `is_allowed_placeholder(value)` and raise an assertion if the value is not allowed. Assertion messages include the dotted/bracketed `path` to the offending value.

            Parameters:
                node (object): The current node to inspect; may be a mapping, sequence, or scalar.
                path (str): Dot/bracket-notation path to `node` used in assertion messages (default "root").

            Raises:
                AssertionError: If a sensitive key contains a disallowed hardcoded value (message includes the node path).
            """
            if isinstance(node, dict):
                for k, v in node.items():
                    key_lower = str(k).lower()
                    new_path = f"{path}.{k}"

                    if any(p in key_lower for p in sensitive_patterns):
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
        """
        Validate that numeric limits in the PR agent configuration are within safe bounds.

        Asserts that:
        - `max_execution_time` is less than or equal to 3600 seconds.
        - `max_concurrent_prs` is less than or equal to 10.
        - `rate_limit_requests` is less than or equal to 1000.
        """
        limits = pr_agent_config["limits"]

        assert limits["max_execution_time"] <= 3600
        assert limits["max_concurrent_prs"] <= 10
        assert limits["rate_limit_requests"] <= 1000


class TestPRAgentConfigRemovedComplexity:
    """Test that complex features were properly removed."""

    @pytest.fixture
    def pr_agent_config_content(self) -> str:
        """
        Load and return the raw text of .github/pr-agent-config.yml.

        Reads the PR agent YAML configuration file from the repository root and returns its contents.

        Returns:
                str: Raw YAML text of the PR agent configuration file.

        Raises:
                FileNotFoundError: If the configuration file cannot be found.
        """
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def test_no_summarization_settings(pr_agent_config_content):
        """
        Assert that summarization-related settings are not present in the raw PR agent configuration text.

        Parameters:
            pr_agent_config_content (str): Raw YAML content of the .github/pr-agent-config.yml file.
        """
        assert "summarization" not in pr_agent_config_content.lower()
        assert "max_summary_tokens" not in pr_agent_config_content

    @staticmethod
    def test_no_token_management(pr_agent_config_content):
        """
        Ensure token management-related keys are absent from the raw PR agent configuration text.

        Checks that the YAML content does not contain the `max_tokens` or `context_length` keys.

        Parameters:
            pr_agent_config_content (str): Raw text content of the `.github/pr-agent-config.yml` file.
        """
        assert "max_tokens" not in pr_agent_config_content
        assert "context_length" not in pr_agent_config_content

    @staticmethod
    def test_no_llm_model_references(pr_agent_config_content):
        """
        Verify that no explicit LLM model identifiers appear in the raw PR agent configuration.

        Parameters:
            pr_agent_config_content (str): Raw text content of .github/pr-agent-config.yml to scan for model identifiers.
        """
        assert "gpt-3.5-turbo" not in pr_agent_config_content
        assert "gpt-4" not in pr_agent_config_content
