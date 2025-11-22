"""
Comprehensive validation tests for pr-agent-config.yml.

This module validates the structure, completeness, and correctness of the
PR agent configuration file after simplification changes.
"""

import pytest
import yaml
from pathlib import Path
from typing import Any, Dict, List


CONFIG_FILE = Path(__file__).parent.parent.parent / ".github" / "pr-agent-config.yml"


@pytest.fixture
def config() -> Dict[str, Any]:
    """Load the pr-agent-config.yml file."""
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


class TestConfigStructure:
    """Test the overall structure of the configuration file."""
    
    def test_config_is_valid_yaml(self):
        """Verify configuration file is valid YAML."""
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            try:
                yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in pr-agent-config.yml: {e}")
    
    def test_config_has_required_sections(self, config: Dict[str, Any]):
        """Verify all required configuration sections are present."""
        required_sections = ['agent', 'monitoring', 'comment_parsing', 'actions']
        
        for section in required_sections:
            assert section in config, f"Required section '{section}' is missing"
    
    def test_config_has_no_duplicate_keys(self):
        """Verify no duplicate keys in configuration."""
        duplicates = []
        
        class DuplicateKeySafeLoader(yaml.SafeLoader):
            pass
        
        def constructor_with_dup_check(loader, node):
            mapping = {}
            for key_node, value_node in node.value:
                key = loader.construct_object(key_node, deep=False)
                if key in mapping:
                    duplicates.append(key)
                mapping[key] = loader.construct_object(value_node, deep=False)
            return mapping
        
        DuplicateKeySafeLoader.add_constructor(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            constructor_with_dup_check
        )
        
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            yaml.load(f, Loader=DuplicateKeySafeLoader)
        
        assert len(duplicates) == 0, f"Duplicate keys found: {duplicates}"


class TestAgentSection:
    """Test the agent configuration section."""
    
    def test_agent_has_name(self, config: Dict[str, Any]):
        """Verify agent has a name configured."""
        assert 'name' in config['agent']
        assert isinstance(config['agent']['name'], str)
        assert len(config['agent']['name']) > 0
    
    def test_agent_has_version(self, config: Dict[str, Any]):
        """Verify agent has a version configured."""
        assert 'version' in config['agent']
        version = config['agent']['version']
        assert isinstance(version, str)
        
        # Should follow semantic versioning (x.y.z)
        parts = version.split('.')
        assert len(parts) == 3, "Version should follow semantic versioning (x.y.z)"
        for part in parts:
            assert part.isdigit(), f"Version part '{part}' should be numeric"
    
    def test_agent_version_is_1_0_0(self, config: Dict[str, Any]):
        """Verify version is 1.0.0 after removing context chunking."""
        assert config['agent']['version'] == '1.0.0'
    
    def test_agent_has_enabled_flag(self, config: Dict[str, Any]):
        """Verify agent has enabled flag."""
        assert 'enabled' in config['agent']
        assert isinstance(config['agent']['enabled'], bool)
    
    def test_agent_is_enabled(self, config: Dict[str, Any]):
        """Verify agent is enabled."""
        assert config['agent']['enabled'] is True
    
    def test_no_context_section(self, config: Dict[str, Any]):
        """Verify context chunking configuration has been removed."""
        assert 'context' not in config['agent'], \
            "Context configuration should be removed after simplification"


class TestMonitoringSection:
    """Test the monitoring configuration section."""
    
    def test_monitoring_has_check_interval(self, config: Dict[str, Any]):
        """Verify monitoring has check_interval configured."""
        assert 'check_interval' in config['monitoring']
        assert isinstance(config['monitoring']['check_interval'], int)
        assert config['monitoring']['check_interval'] > 0
    
    def test_monitoring_has_max_retries(self, config: Dict[str, Any]):
        """Verify monitoring has max_retries configured."""
        assert 'max_retries' in config['monitoring']
        assert isinstance(config['monitoring']['max_retries'], int)
        assert config['monitoring']['max_retries'] > 0
    
    def test_monitoring_has_timeout(self, config: Dict[str, Any]):
        """Verify monitoring has timeout configured."""
        assert 'timeout' in config['monitoring']
        assert isinstance(config['monitoring']['timeout'], int)
        assert config['monitoring']['timeout'] > 0
    
    def test_monitoring_values_reasonable(self, config: Dict[str, Any]):
        """Verify monitoring values are within reasonable ranges."""
        monitoring = config['monitoring']
        
        # Check interval should be reasonable (not too frequent)
        assert monitoring['check_interval'] >= 60, \
            "Check interval should be at least 60 seconds"
        assert monitoring['check_interval'] <= 7200, \
            "Check interval should not exceed 2 hours"
        
        # Max retries should be reasonable
        assert monitoring['max_retries'] >= 1
        assert monitoring['max_retries'] <= 10
        
        # Timeout should be reasonable
        assert monitoring['timeout'] >= 60
        assert monitoring['timeout'] <= 1800


class TestCommentParsingSection:
    """Test the comment parsing configuration section."""
    
    def test_comment_parsing_has_triggers(self, config: Dict[str, Any]):
        """Verify comment parsing has triggers list."""
        assert 'triggers' in config['comment_parsing']
        assert isinstance(config['comment_parsing']['triggers'], list)
        assert len(config['comment_parsing']['triggers']) > 0
    
    def test_triggers_are_strings(self, config: Dict[str, Any]):
        """Verify all triggers are strings."""
        triggers = config['comment_parsing']['triggers']
        
        for trigger in triggers:
            assert isinstance(trigger, str), f"Trigger '{trigger}' should be a string"
            assert len(trigger) > 0, "Trigger should not be empty"
    
    def test_common_triggers_present(self, config: Dict[str, Any]):
        """Verify common trigger patterns are present."""
        triggers = config['comment_parsing']['triggers']
        
        # Should have bot mention triggers
        bot_triggers = [t for t in triggers if '@' in t]
        assert len(bot_triggers) > 0, "Should have at least one @ mention trigger"
    
    def test_comment_parsing_has_ignore_patterns(self, config: Dict[str, Any]):
        """Verify comment parsing has ignore patterns."""
        assert 'ignore_patterns' in config['comment_parsing']
        assert isinstance(config['comment_parsing']['ignore_patterns'], list)
    
    def test_ignore_patterns_are_strings(self, config: Dict[str, Any]):
        """Verify all ignore patterns are strings."""
        patterns = config['comment_parsing']['ignore_patterns']
        
        for pattern in patterns:
            assert isinstance(pattern, str)
    
    def test_comment_parsing_has_priority_keywords(self, config: Dict[str, Any]):
        """Verify comment parsing has priority keywords."""
        assert 'priority_keywords' in config['comment_parsing']
        priorities = config['comment_parsing']['priority_keywords']
        
        assert isinstance(priorities, dict)
        assert 'high' in priorities
        assert 'medium' in priorities
        assert 'low' in priorities
    
    def test_priority_keywords_are_lists(self, config: Dict[str, Any]):
        """Verify priority keywords are lists of strings."""
        priorities = config['comment_parsing']['priority_keywords']
        
        for level, keywords in priorities.items():
            assert isinstance(keywords, list), f"{level} priority should be a list"
            for keyword in keywords:
                assert isinstance(keyword, str), f"Keyword '{keyword}' should be a string"
    
    def test_high_priority_has_critical_keywords(self, config: Dict[str, Any]):
        """Verify high priority includes critical keywords."""
        high_priority = config['comment_parsing']['priority_keywords']['high']
        
        critical_keywords = ['breaking', 'security', 'critical', 'urgent']
        for keyword in critical_keywords:
            assert keyword in high_priority, \
                f"High priority should include '{keyword}'"


class TestActionsSection:
    """Test the actions configuration section."""
    
    def test_actions_has_auto_acknowledge(self, config: Dict[str, Any]):
        """Verify actions has auto_acknowledge setting."""
        assert 'auto_acknowledge' in config['actions']
        assert isinstance(config['actions']['auto_acknowledge'], bool)
    
    def test_actions_values_are_boolean(self, config: Dict[str, Any]):
        """Verify all action values are boolean."""
        actions = config['actions']
        
        for key, value in actions.items():
            if isinstance(value, bool):
                # Boolean values are fine
                continue
            elif isinstance(value, dict):
                # Nested config is fine
                continue
            else:
                pytest.fail(f"Action '{key}' should be boolean or dict, got {type(value)}")


class TestLimitsSection:
    """Test the limits configuration section (if present)."""
    
    def test_no_chunking_limits(self, config: Dict[str, Any]):
        """Verify chunking-related limits have been removed."""
        if 'limits' in config:
            limits = config['limits']
            
            # These should not be present after simplification
            assert 'max_files_per_chunk' not in limits
            assert 'max_diff_lines' not in limits
            assert 'max_comment_length' not in limits
            assert 'fallback' not in limits
    
    def test_limits_if_present_are_reasonable(self, config: Dict[str, Any]):
        """Verify any remaining limits have reasonable values."""
        if 'limits' in config:
            limits = config['limits']
            
            for key, value in limits.items():
                if isinstance(value, int):
                    assert value > 0, f"Limit '{key}' should be positive"
                    assert value < 1000000, f"Limit '{key}' seems unreasonably high"


class TestConfigCompleteness:
    """Test configuration completeness and best practices."""
    
    def test_config_has_comments(self):
        """Verify configuration file has helpful comments."""
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should have comments explaining sections
        assert '#' in content, "Configuration should have comments"
        
        # Count comment lines
        comment_lines = [line for line in content.split('\n') if line.strip().startswith('#')]
        assert len(comment_lines) >= 3, "Should have multiple explanatory comments"
    
    def test_no_hardcoded_secrets(self):
        """Verify no secrets are hardcoded in config."""
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            content = f.read().lower()
        
        secret_indicators = ['password', 'api_key', 'token', 'secret', 'credential']
        
        for indicator in secret_indicators:
            if indicator in content:
                # Check it's not an actual secret value
                for line in content.split('\n'):
                    if indicator in line.lower() and ':' in line:
                        value = line.split(':', 1)[1].strip()
                        # Should reference ${{}} or be a placeholder
                        if value and not value.startswith('#'):
                            assert '${{' in value or 'secret' not in value.lower(), \
                                f"Possible hardcoded secret in line: {line}"
    
    def test_all_values_have_types(self, config: Dict[str, Any]):
        """Verify all configuration values have appropriate types."""
        def check_types(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    check_types(value, f"{path}.{key}" if path else key)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_types(item, f"{path}[{i}]")
            elif obj is None:
                pytest.fail(f"Configuration value at '{path}' is None")
        
        check_types(config)


class TestConfigConsistency:
    """Test configuration consistency and relationships."""
    
    def test_timeout_less_than_check_interval(self, config: Dict[str, Any]):
        """Verify timeout is less than check interval (if both present)."""
        monitoring = config.get('monitoring', {})
        
        if 'timeout' in monitoring and 'check_interval' in monitoring:
            assert monitoring['timeout'] <= monitoring['check_interval'], \
                "Timeout should not exceed check interval"
    
    def test_trigger_patterns_unique(self, config: Dict[str, Any]):
        """Verify trigger patterns are unique."""
        triggers = config['comment_parsing']['triggers']
        
        assert len(triggers) == len(set(triggers)), \
            "Trigger patterns should be unique"
    
    def test_priority_keywords_unique_per_level(self, config: Dict[str, Any]):
        """Verify priority keywords are unique within each level."""
        priorities = config['comment_parsing']['priority_keywords']
        
        for level, keywords in priorities.items():
            assert len(keywords) == len(set(keywords)), \
                f"Keywords in '{level}' priority should be unique"
    
    def test_no_keyword_overlap_between_priorities(self, config: Dict[str, Any]):
        """Verify keywords don't overlap between priority levels."""
        priorities = config['comment_parsing']['priority_keywords']
        
        high = set(priorities.get('high', []))
        medium = set(priorities.get('medium', []))
        low = set(priorities.get('low', []))
        
        # Check for overlaps
        high_medium_overlap = high & medium
        high_low_overlap = high & low
        medium_low_overlap = medium & low
        
        assert len(high_medium_overlap) == 0, \
            f"Keywords overlap between high and medium: {high_medium_overlap}"
        assert len(high_low_overlap) == 0, \
            f"Keywords overlap between high and low: {high_low_overlap}"
        assert len(medium_low_overlap) == 0, \
            f"Keywords overlap between medium and low: {medium_low_overlap}"


class TestConfigBackwardCompatibility:
    """Test backward compatibility of configuration."""
    
    def test_essential_triggers_preserved(self, config: Dict[str, Any]):
        """Verify essential trigger patterns are preserved."""
        triggers = config['comment_parsing']['triggers']
        
        # Should still have common patterns
        trigger_str = ' '.join(triggers)
        assert 'fix' in trigger_str.lower() or any('fix' in t for t in triggers)
    
    def test_monitoring_preserved(self, config: Dict[str, Any]):
        """Verify monitoring configuration is still present."""
        assert 'monitoring' in config
        assert len(config['monitoring']) > 0


class TestConfigEdgeCases:
    """Test edge cases in configuration."""
    
    def test_empty_strings_not_in_triggers(self, config: Dict[str, Any]):
        """Verify no empty strings in triggers list."""
        triggers = config['comment_parsing']['triggers']
        
        for trigger in triggers:
            assert len(trigger.strip()) > 0, "Triggers should not be empty"
    
    def test_empty_strings_not_in_ignore_patterns(self, config: Dict[str, Any]):
        """Verify no empty strings in ignore patterns."""
        patterns = config['comment_parsing']['ignore_patterns']
        
        for pattern in patterns:
            assert len(pattern.strip()) > 0, "Ignore patterns should not be empty"
    
    def test_whitespace_only_values_not_present(self, config: Dict[str, Any]):
        """Verify no whitespace-only string values."""
        def check_whitespace(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    check_whitespace(value, f"{path}.{key}" if path else key)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_whitespace(item, f"{path}[{i}]")
            elif isinstance(obj, str):
                assert len(obj.strip()) > 0, \
                    f"String value at '{path}' is whitespace-only"
        
        check_whitespace(config)


class TestConfigDocumentation:
    """Test configuration documentation and readability."""
    
    def test_file_has_header_comment(self):
        """Verify file starts with descriptive header."""
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            first_lines = [f.readline() for _ in range(3)]
        
        # First non-empty line should be a comment
        for line in first_lines:
            if line.strip():
                assert line.strip().startswith('#'), \
                    "File should start with a descriptive comment"
                break
    
    def test_sections_have_comments(self):
        """Verify major sections have explanatory comments."""
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        
        sections = ['agent', 'monitoring', 'comment_parsing', 'actions']
        
        for section in sections:
            # Find section in content
            section_index = content.find(f'{section}:')
            if section_index > 0:
                # Check if there's a comment within 3 lines before
                before_section = content[:section_index].split('\n')[-4:]
                has_comment = any(line.strip().startswith('#') for line in before_section)
                
                assert has_comment or '#' in content[max(0, section_index-200):section_index], \
                    f"Section '{section}' should have explanatory comment"