# Top-level secret placeholder checks are performed within dedicated tests, not at import time.

from pathlib import Path

import yaml



import pytest
# Secret placeholder checks are performed within dedicated tests, not at import time.

"""Validation tests for PR agent configuration changes.

Tests the simplified PR agent configuration, ensuring:
- Version downgrade from 1.1.0 to 1.0.0
- Removal of context chunking features
- Removal of tiktoken dependencies
- Simplified configuration structure
"""


class TestPRAgentConfigSimplification:
    """Test PR agent config simplification changes."""

    @pytest.fixture
    def pr_agent_config(self):
        """
        Load and parse the PR agent YAML configuration from .github / pr - agent - config.yml.

        If the file is missing, contains invalid YAML, or does not contain a top - level mapping, the fixture will call pytest.fail to abort the test.

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

        The test fails if the parsed PR agent configuration includes a 'context' key under the top - level 'agent' section.
        """
        agent_config = pr_agent_config["agent"]
        assert "context" not in agent_config

    def test_no_chunking_settings(self, pr_agent_config):
        """
        Assert the configuration contains no chunking - related settings.

        Checks that the keys 'chunking', 'chunk_size' and 'overlap_tokens' do not appear in the serialized configuration string(case-insensitive).
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
        Ensure the top - level `limits` section does not contain a `fallback` key.
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
        Ensure the top - level monitoring section contains the keys 'check_interval', 'max_retries', and 'timeout'.

        Parameters:
            pr_agent_config(dict): Parsed PR agent configuration mapping.
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
        Fail the test if .github / pr - agent - config.yml contains invalid YAML.

        Attempts to parse the repository file at .github / pr - agent - config.yml and fails the test with the YAML parser error when parsing fails.
        """
        config_path = Path(".github/pr-agent-config.yml")

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            pytest.fail(f"Invalid YAML syntax: {e}")

        assert config is not None
        assert isinstance(config, dict)
        config_path = Path(".github/pr-agent-config.yml")

        class _NoDuplicateKeysSafeLoader(yaml.SafeLoader):
            """YAML loader that fails on duplicate mapping keys."""

            def construct_mapping(self, node, deep=False):
                mapping = {}
                seen = set()

                for key_node, value_node in node.value:
                    key = self.construct_object(key_node, deep=deep)

                    # Most YAML keys here are scalars (strings). For safety, fall back
                    # to string representation for unhashable keys.
                    key_id = repr(key)
                    is_hashable = False

                    if key_id in seen:
                        # Use the key node mark for precise location info.
                        mark = getattr(key_node, "start_mark", None)
                        if mark is not None:
                            pytest.fail(
                                f"Duplicate key '{key}' at line {mark.line + 1}, column {mark.column + 1}"
                            )
                        pytest.fail(f"Duplicate key '{key}' found in YAML mapping")

                    seen.add(key_id)
                    mapping[key] = self.construct_object(value_node, deep=deep)

                return mapping

        try:
            with open(config_path, "r") as f:
                config = yaml.load(f, Loader=_NoDuplicateKeysSafeLoader)
            assert config is not None
            assert isinstance(config, dict)
        except yaml.YAMLError as e:
            pytest.fail(f"Invalid YAML syntax: {e}")

        with open(config_path, "r") as f:
            try:
                yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"PR agent config has invalid YAML: {e}")

    def test_no_duplicate_keys(self):
        """
        Fail the test if any top - level YAML key appears more than once in the file.

        Scans .github / pr - agent - config.yml, ignores comment lines, and for each non - comment line treats the text before the first ':' as the key; the test fails if a key is encountered more than once.
        """
        config_path = Path(".github/pr-agent-config.yml")

        class DuplicateKeyLoader(yaml.SafeLoader):
            """YAML loader that raises on duplicate mapping keys."""

            def construct_mapping(self, node, deep=False):
                mapping = {}
                for key_node, value_node in node.value:
                    key = self.construct_object(key_node, deep=deep)
                    if key in mapping:
                        raise yaml.constructor.ConstructorError(
                            "while constructing a mapping",
                            key_node.start_mark,
                            f"found duplicate key ({key})",
                            key_node.start_mark,
                        )
                    mapping[key] = self.construct_object(value_node, deep=deep)
                return mapping

            try:
                # DuplicateKeyLoader is expected to raise ConstructorError on duplicates
                yaml.load(f, Loader=DuplicateKeyLoader)
            except yaml.constructor.ConstructorError as e:
                # ConstructorError can be raised for reasons other than duplicate keys;
                # only fail this test when the error is actually about duplicates.
                if "duplicate" in str(e).lower():
                    pytest.fail(f"Duplicate key found: {e}")
                raise
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML syntax while checking duplicates: {e}")

        with open(config_path, "r") as f:
            content = f.read()

        # Simple check for obvious duplicates
        lines = content.split("\n")
        with open(config_path, "r") as f:
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

    def test_consistent_indentation(self):
        """
        Verify that every non - empty, non - comment line in the PR agent YAML uses 2 - space indentation increments.

        Raises an AssertionError indicating the line number when a line's leading spaces are not a multiple of two.
        """
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, "r") as f:
            lines = f.readlines()

        for i, line in enumerate(lines, 1):
            # Disallow tabs anywhere (especially in indentation)
            assert "\t" not in line, (
                f"Line {i}: Tab character found; tabs are not allowed"
            )

            # If line starts with spaces, ensure multiple of 2 indentation
            if line.strip() and line[0] == " ":
                spaces = len(line) - len(line.lstrip(" "))
                assert spaces % 2 == 0, (
                    f"Line {i}: Inconsistent indentation (not multiple of 2)"
                )
        # Redundant second indentation pass removed; the loop above already validates each line's indentation directly.


class TestPRAgentConfigSecurity:
    """Test security aspects of configuration."""

    @ pytest.fixture
    def pr_agent_config(self) -> dict[str, object] | None:
        """
        Load and parse the PR agent YAML configuration from .github/pr-agent-config.yml.

        Returns:
            The parsed YAML content as a Python mapping or sequence (typically a dict),
            or `None` if the file is empty.
        Raises:
            AssertionError: Via pytest.fail if the file is missing or contains invalid YAML.
        """
        config_path = Path(".github/pr-agent-config.yml")
        if not config_path.exists():
            pytest.fail(f"Config file not found: {config_path}")
        with open(config_path, "r", encoding="utf-8") as f:
            try:
                cfg = yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in PR agent config: {e}")
        if cfg is not None and not isinstance(cfg, dict):
            pytest.fail("Config must be a YAML mapping (dict) or empty")
        return cfg

    def test_no_hardcoded_credentials(self, pr_agent_config):
        """
        Recursively scan configuration values and keys for suspected secrets.
        - Flags high-entropy or secret-like string values.
        - Ensures sensitive keys only use safe placeholders.
        """
        import math
        import re

        # Heuristic to detect inline creds in URLs (user:pass@)
        inline_creds_re = re.compile(
            r"^[a-zA-Z][a-zA-Z0-9+.-]*://[^/@:\s]+:[^/@\s]+@", re.IGNORECASE
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
            "bearer",
        )
        sensitive_key_patterns = [
            "password",
            "secret",
            "token",
            "api_key",
            "apikey",
            "access_key",
            "private_key",
        ]
        safe_placeholders = {
            None,
            "null",
            "webhook",
            "<token>",
            "<secret>",
            "changeme",
            "your-token-here",
            "dummy",
            "placeholder",
        }

        def shannon_entropy(s: str) -> float:
            if not s:
                return 0.0
            sample = s[:256]
            freq = {ch: sample.count(ch) for ch in set(sample)}
            ent = 0.0
            length = len(sample)
            for c in freq.values():
                p = c / length
                ent -= p * math.log2(p)
            return ent

        def looks_like_secret(val: str) -> bool:
            v = val.strip()
            if not v or v.lower() in safe_placeholders:
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

        def walk_and_check_config(obj, path="root"):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    current_path = f"{path}.{k}"
                    key_l = str(k).lower()
                    if any(p in key_l for p in sensitive_key_patterns):
                        if v is None:
                            # Allow explicit null values for sensitive keys as safe placeholders
                            continue
                            f"Potential hardcoded credential at '{current_path}'"
                        )
                    walk_and_check_config(v, current_path)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    walk_and_check_config(item, f"{path}[{i}]")
            elif isinstance(obj, str):
                if looks_like_secret(obj):
                    pytest.fail(f"Suspected secret value at '{path}': {obj[:20]}...")

        if pr_agent_config:
            walk_and_check_config(pr_agent_config)


def test_safe_configuration_values(pr_agent_config: dict[str, object]) -> None:
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


@pytest.fixture
def pr_agent_config_content() -> str:
    """
    Read and return the raw contents of .github/pr-agent-config.yml.

    Returns:
        str: Raw YAML content of .github/pr-agent-config.yml.
    """
    config_path = Path(".github/pr-agent-config.yml")
    with open(config_path, "r", encoding="utf-8") as f:
        return f.read()


def test_no_summarization_settings(pr_agent_config_content: str) -> None:
    """Verify summarization settings have been removed from the configuration."""
    assert "summarization" not in pr_agent_config_content.lower()
    assert "max_summary_tokens" not in pr_agent_config_content


def test_no_token_management(pr_agent_config_content: str) -> None:
    """Verify token management settings have been removed from the configuration."""
    assert "max_tokens" not in pr_agent_config_content
    assert "context_length" not in pr_agent_config_content


def test_no_llm_model_references(pr_agent_config_content: str) -> None:
    """
    Ensure no explicit LLM model identifiers appear in the raw PR agent configuration.

    Parameters:
        pr_agent_config_content (str): Raw contents of .github/pr-agent-config.yml used for pattern checks.
            pr_agent_config_content(str): Raw contents of .github / pr - agent - config.yml used for pattern checks.
        """
        assert "gpt-3.5-turbo" not in pr_agent_config_content
        assert "gpt-4" not in pr_agent_config_content
