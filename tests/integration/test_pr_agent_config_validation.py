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
    Load and parse the PR agent YAML configuration from .github/pr-agent-config.yml.
    
    Calls pytest.fail to abort the test if the file is missing, the YAML is invalid, or the top-level document is not a mapping.
    
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
    Calculate Shannon entropy of a string.

    Used as a heuristic to detect high-entropy tokens such as API keys.

    Args:
        value: The string to analyse.

    Returns:
        float: Shannon entropy value (bits per character).
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
    Determine whether a string likely contains a secret or credential.
    
    Strips surrounding whitespace and treats known safe placeholders as non-secrets; flags inline URL credentials, values containing secret-indicating keywords of sufficient length, long base64-like strings with high entropy, or long hexadecimal strings.
    
    Parameters:
        value (str): String to evaluate.
    
    Returns:
        bool: `true` if the value is likely a secret, `false` otherwise.
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
        Assert that the 'agent' section does not contain a 'context' key.

        The test fails if the parsed PR agent configuration includes a 'context' key under the top - level 'agent' section.
        """
        agent_config = pr_agent_config["agent"]
        assert "context" not in agent_config

    @staticmethod
    def test_no_chunking_settings(pr_agent_config):
        """
        Verify the agent configuration contains no chunking-related settings.
        
        Checks that the keys "chunking", "chunk_size", and "overlap_tokens" do not appear in the serialized YAML of the configuration (case-insensitive); the test fails if any are present.
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
        Verify the top-level "monitoring" section contains the required keys.
        
        Parameters:
            pr_agent_config (dict): The parsed PR agent configuration mapping.
        
        The monitoring section must include the keys "check_interval", "max_retries", and "timeout".
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
        Validate that .github/pr-agent-config.yml contains valid YAML.
        
        Attempts to parse the file with yaml.safe_load and fails the test if parsing raises a YAML parser error.
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
                Build a dict from a YAML mapping node, failing the test on duplicate keys.
                
                Parameters:
                    node: YAML mapping node with `.value` pairs and `.start_mark.line`; entries will be constructed via `construct_object`.
                    deep (bool): If True, construct nested objects recursively.
                
                Returns:
                    dict: Mapping of constructed keys to their constructed values.
                
                Raises:
                    pytest.fail: If a duplicate key is found; message includes the 1-based line number where the duplicate occurs.
                """
                mapping = {}
                for entry_node, val_node in node.value:
                    entry = self.construct_object(entry_node, deep=deep)
                    if entry in mapping:
                        pytest.fail(f"Duplicate entry found: {entry} at line {entry_node.start_mark.line + 1}")
                    value = self.construct_object(val_node, deep=deep)
                    mapping[entry] = value
                return mapping

        # Using yaml.load() with custom Loader is required for duplicate key detection.
        # DuplicateKeyLoader extends SafeLoader, so this is secure.
        yaml.load(content, Loader=DuplicateKeyLoader)

    @staticmethod
    def test_consistent_indentation():
        """
        Ensure non-empty, non-comment lines in the PR agent YAML use two-space indentation increments.
        
        Raises:
            AssertionError: if a line's leading spaces are not a multiple of two; message includes the line number.
        """
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for i, line in enumerate(lines, 1):
            if line.strip() and not line.strip().startswith("#"):
                indent = len(line) - len(line.lstrip())
                if indent > 0:
                    assert indent % 2 == 0, f"Line {i} has inconsistent indentation: {indent} spaces"


class TestPRAgentConfigSecurity:
    """Test security aspects of configuration."""

    @staticmethod
    def scan(obj: object, suspected: list[tuple[str, str]]) -> None:
        """
        Recursively search a configuration object for strings that resemble secrets and record them.
        
        Parameters:
            obj (object): The value to scan; may be a dict, list/tuple, or scalar.
            suspected (list[tuple[str, str]]): Mutable list that will be appended with (kind, value) tuples for each detected secret.
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
            Produce a redacted representation of a string, preserving up to the first and last four characters when possible.
            
            Returns:
                `'***'` if the input length is eight characters or less, otherwise a string in the form `'<first4>...<last4>'` where the first four and last four characters are kept and the middle is replaced by an ellipsis.
            """
            if len(value) <= 8:
                return "***"
            return f"{value[:4]}...{value[-4:]}"

        if suspected:
            details = "\n".join(f"{kind}: {_redact(value)}" for kind, value in suspected)
            pytest.fail(f"Potential hardcoded credentials found in PR agent config:\n{details}")

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
                v (object): Value to evaluate; may be None or a string.
            
            Returns:
                bool: True if v is None, one of the allowed placeholder strings (case-insensitive after trimming), or matches the templated variable pattern; False otherwise.
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
            Validate that values whose keys match sensitive indicator patterns are allowed placeholders by recursively traversing mappings and sequences.
            
            Parameters:
                node (object): Current node to inspect; may be a dict, list/tuple, or scalar.
                path (str): Dot/bracket-notation path to `node` used in assertion messages (default "root").
            
            Raises:
                AssertionError: If a sensitive key contains a disallowed hardcoded value; the error message includes the offending node path.
            """
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
        """Assert numeric configuration limits fall within safe bounds."""
        limits = pr_agent_config["limits"]

        assert limits["max_execution_time"] <= 3600
        assert limits["max_concurrent_prs"] <= 10
        assert limits["rate_limit_requests"] <= 1000


class TestPRAgentConfigRemovedComplexity:
    """Test that complex features were properly removed."""

    @pytest.fixture
    def pr_agent_config_content(self) -> str:
        """
        Get the raw text of the .github/pr-agent-config.yml file.
        
        Returns:
            Raw YAML content of the PR agent configuration file as a string.
        """
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def test_no_summarization_settings(pr_agent_config_content):
        """Verify summarization settings removed."""
        assert "summarization" not in pr_agent_config_content.lower()
        assert "max_summary_tokens" not in pr_agent_config_content

    @staticmethod
    def test_no_token_management(pr_agent_config_content):
        """
        Ensure token management settings are not present in the PR agent configuration content.
        
        Asserts that the raw configuration text does not contain the keys "max_tokens" or "context_length".
        """
        assert "max_tokens" not in pr_agent_config_content
        assert "context_length" not in pr_agent_config_content

    @staticmethod
    def test_no_llm_model_references(pr_agent_config_content):
        """
        Verify that the raw PR agent configuration contains no explicit LLM model identifiers.
        
        Parameters:
            pr_agent_config_content (str): Raw contents of .github/pr-agent-config.yml to scan for model names.
        """
        assert "gpt-3.5-turbo" not in pr_agent_config_content
        assert "gpt-4" not in pr_agent_config_content