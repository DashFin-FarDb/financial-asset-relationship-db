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
        assert 'chunk_size' not in config_str.lower()
        assert 'overlap_tokens' not in config_str.lower()
    
    def test_no_tiktoken_references(self, pr_agent_config):
        """Verify tiktoken references removed."""
        config_str = yaml.dump(pr_agent_config)
        assert 'tiktoken' not in config_str.lower()
    
    def test_no_fallback_strategies(self, pr_agent_config):
        """Verify fallback strategies removed from limits."""
        limits = pr_agent_config.get('limits', {})
        assert 'fallback' not in limits
    
    def test_basic_config_structure_intact(self, pr_agent_config):
        """Verify basic configuration sections still present."""
        # Essential sections should remain
        assert 'agent' in pr_agent_config
        assert 'monitoring' in pr_agent_config
        assert 'actions' in pr_agent_config
        assert 'quality' in pr_agent_config
        assert 'security' in pr_agent_config
    
    def test_monitoring_config_present(self, pr_agent_config):
        """
        Verify the monitoring section contains the required keys: 'check_interval', 'max_retries' and 'timeout'.
        
        Parameters:
            pr_agent_config (dict): Parsed PR agent configuration loaded from .github/pr-agent-config.yml.
        """
        monitoring = pr_agent_config['monitoring']
        assert 'check_interval' in monitoring
        assert 'max_retries' in monitoring
        assert 'timeout' in monitoring
    
    def test_limits_simplified(self, pr_agent_config):
        """Verify limits section simplified."""
        limits = pr_agent_config['limits']
        
        # Should not have complex chunking limits
        assert 'max_files_per_chunk' not in limits
        assert 'max_diff_lines' not in limits
        
        # Should have basic limits
        assert 'max_execution_time' in limits
        assert 'max_concurrent_prs' in limits


class TestPRAgentConfigYAMLValidity:
    """Test YAML validity and structure."""
    
    def test_config_is_valid_yaml(self):
        """Verify config file is valid YAML."""
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, 'r') as f:
            try:
                yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"PR agent config has invalid YAML: {e}")
    
    def test_no_duplicate_keys(self):
        """
        Fail the test if any top-level YAML key appears more than once in the file.
        
        Reads .github/pr-agent-config.yml, ignores commented lines, and treats the text before the first ':' on each non-comment line as a key; the test fails when a previously seen key is encountered again.
        """
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, 'r') as f:
            content = f.read()
        
        # Simple check for obvious duplicates
        lines = content.split('\n')
        seen_keys = set()
        for line in lines:
            if ':' in line and not line.strip().startswith('#'):
                key = line.split(':')[0].strip()
                if key in seen_keys:
                    pytest.fail(f"Duplicate key found: {key}")
                seen_keys.add(key)
    
    def test_consistent_indentation(self):
        """
        Assert that every non-empty, non-comment line in the PR agent YAML file uses indentation in 2-space increments.
        
        Raises an assertion error pointing to the line number if a line has a number of leading spaces that is not a multiple of two.
        """
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
        Traverse the parsed YAML and ensure that any key containing sensitive indicators
        has a safe placeholder value (None, 'null', or 'webhook').
        """
        sensitive_patterns = [
            'password', 'secret', 'token', 'api_key', 'apikey',
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