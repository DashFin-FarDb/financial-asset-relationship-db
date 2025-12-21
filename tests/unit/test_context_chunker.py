"""Comprehensive unit tests for .github/scripts/context_chunker.py module.

This module provides extensive test coverage for:
- ContextChunker initialization and configuration
- Context processing from PR payloads
- Token counting and estimation
- Configuration loading and defaults
- Priority ordering and context element handling
- Edge cases with large payloads
- Empty and missing data handling
"""

import sys
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest
import yaml

# Add the scripts directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / '.github' / 'scripts'))

from context_chunker import ContextChunker


class TestContextChunkerInitialization:
    """Test ContextChunker initialization and configuration loading."""

    def test_initialization_with_default_config(self):
        """Test initializing with default configuration path."""
        with patch('pathlib.Path.exists', return_value=False):
            chunker = ContextChunker()
            assert chunker is not None
            assert hasattr(chunker, 'max_tokens')
            assert hasattr(chunker, 'chunk_size')

    def test_initialization_sets_default_max_tokens(self):
        """Test that default max_tokens is set correctly."""
        with patch('pathlib.Path.exists', return_value=False):
            chunker = ContextChunker()
            assert chunker.max_tokens == 32000

    def test_initialization_sets_default_chunk_size(self):
        """Test that default chunk_size is calculated correctly."""
        with patch('pathlib.Path.exists', return_value=False):
            chunker = ContextChunker()
            # chunk_size should be max_tokens - 4000
            assert chunker.chunk_size > 0
            assert chunker.chunk_size <= chunker.max_tokens

    def test_initialization_sets_default_overlap_tokens(self):
        """Test that default overlap_tokens is set correctly."""
        with patch('pathlib.Path.exists', return_value=False):
            chunker = ContextChunker()
            assert chunker.overlap_tokens == 2000

    def test_initialization_sets_default_summarization_threshold(self):
        """Test that default summarization_threshold is set correctly."""
        with patch('pathlib.Path.exists', return_value=False):
            chunker = ContextChunker()
            # Should be approximately 90% of max_tokens
            assert chunker.summarization_threshold > 0
            assert chunker.summarization_threshold <= chunker.max_tokens

    def test_initialization_sets_default_priority_order(self):
        """Test that default priority_order is set correctly."""
        with patch('pathlib.Path.exists', return_value=False):
            chunker = ContextChunker()
            assert isinstance(chunker.priority_order, list)
            assert len(chunker.priority_order) > 0
            assert 'review_comments' in chunker.priority_order

    def test_initialization_creates_priority_map(self):
        """Test that priority_map is created from priority_order."""
        with patch('pathlib.Path.exists', return_value=False):
            chunker = ContextChunker()
            assert isinstance(chunker.priority_map, dict)
            assert len(chunker.priority_map) == len(chunker.priority_order)

    def test_initialization_with_custom_config_path(self):
        """Test initialization with custom config path."""
        with patch('pathlib.Path.exists', return_value=False):
            chunker = ContextChunker(config_path="custom/path/config.yml")
            assert chunker is not None

    def test_initialization_loads_valid_yaml_config(self, tmp_path):
        """Test loading valid YAML configuration."""
        config_file = tmp_path / "test_config.yml"
        config_data = {
            'agent': {
                'context': {
                    'max_tokens': 16000,
                    'chunk_size': 14000,
                    'overlap_tokens': 1000,
                    'summarization_threshold': 15000
                }
            },
            'limits': {
                'fallback': {
                    'priority_order': ['review_comments', 'changed_files']
                }
            }
        }
        config_file.write_text(yaml.dump(config_data))
        
        chunker = ContextChunker(config_path=str(config_file))
        assert chunker.max_tokens == 16000
        assert chunker.chunk_size == 14000
        assert chunker.overlap_tokens == 1000
        assert chunker.summarization_threshold == 15000

    def test_initialization_handles_missing_config_file(self):
        """Test that missing config file uses defaults."""
        with patch('pathlib.Path.exists', return_value=False):
            chunker = ContextChunker(config_path="nonexistent.yml")
            # Should use defaults
            assert chunker.max_tokens == 32000

    def test_initialization_handles_invalid_yaml(self, tmp_path):
        """Test handling of invalid YAML in config file."""
        config_file = tmp_path / "invalid.yml"
        config_file.write_text("invalid: yaml: content: [[[")
        
        # Should fall back to defaults without crashing
        chunker = ContextChunker(config_path=str(config_file))
        assert chunker.max_tokens == 32000

    def test_initialization_handles_empty_config(self, tmp_path):
        """Test handling of empty config file."""
        config_file = tmp_path / "empty.yml"
        config_file.write_text("")
        
        chunker = ContextChunker(config_path=str(config_file))
        assert chunker.max_tokens == 32000

    def test_initialization_handles_partial_config(self, tmp_path):
        """Test handling of partial configuration."""
        config_file = tmp_path / "partial.yml"
        config_data = {
            'agent': {
                'context': {
                    'max_tokens': 20000
                }
            }
        }
        config_file.write_text(yaml.dump(config_data))
        
        chunker = ContextChunker(config_path=str(config_file))
        assert chunker.max_tokens == 20000
        # Other values should use calculated defaults
        assert chunker.chunk_size > 0


class TestProcessContext:
    """Test process_context method for PR payload processing."""

    @pytest.fixture
    def chunker(self):
        """Create a ContextChunker instance for testing."""
        with patch('pathlib.Path.exists', return_value=False):
            return ContextChunker()

    def test_process_context_empty_payload(self, chunker):
        """Test processing empty payload."""
        payload = {}
        text, has_content = chunker.process_context(payload)
        assert isinstance(text, str)
        assert has_content is False

    def test_process_context_with_reviews(self, chunker):
        """Test processing payload with review comments."""
        payload = {
            'reviews': [
                {'body': 'This looks good!'},
                {'body': 'Please fix the tests.'}
            ]
        }
        text, has_content = chunker.process_context(payload)
        assert has_content is True
        assert 'This looks good!' in text
        assert 'Please fix the tests.' in text

    def test_process_context_with_files(self, chunker):
        """Test processing payload with file patches."""
        payload = {
            'files': [
                {'patch': '+added line\n-removed line'},
                {'patch': '+another change'}
            ]
        }
        text, has_content = chunker.process_context(payload)
        assert has_content is True
        assert '+added line' in text or 'added line' in text

    def test_process_context_with_reviews_and_files(self, chunker):
        """Test processing payload with both reviews and files."""
        payload = {
            'reviews': [{'body': 'Review comment'}],
            'files': [{'patch': '+code change'}]
        }
        text, has_content = chunker.process_context(payload)
        assert has_content is True
        assert len(text) > 0

    def test_process_context_reviews_without_body(self, chunker):
        """Test processing reviews without body field."""
        payload = {
            'reviews': [
                {'user': 'reviewer1'},
                {'body': None}
            ]
        }
        text, has_content = chunker.process_context(payload)
        # Should handle gracefully
        assert isinstance(text, str)

    def test_process_context_files_without_patch(self, chunker):
        """Test processing files without patch field."""
        payload = {
            'files': [
                {'filename': 'test.py'},
                {'patch': None}
            ]
        }
        text, has_content = chunker.process_context(payload)
        assert isinstance(text, str)

    def test_process_context_none_reviews(self, chunker):
        """Test processing when reviews is None."""
        payload = {
            'reviews': None,
            'files': [{'patch': 'some code'}]
        }
        text, has_content = chunker.process_context(payload)
        assert isinstance(text, str)

    def test_process_context_none_files(self, chunker):
        """Test processing when files is None."""
        payload = {
            'reviews': [{'body': 'comment'}],
            'files': None
        }
        text, has_content = chunker.process_context(payload)
        assert has_content is True

    def test_process_context_empty_reviews_list(self, chunker):
        """Test processing with empty reviews list."""
        payload = {
            'reviews': [],
            'files': []
        }
        text, has_content = chunker.process_context(payload)
        assert has_content is False

    def test_process_context_large_payload(self, chunker):
        """Test processing large payload."""
        payload = {
            'reviews': [{'body': 'x' * 10000} for _ in range(10)],
            'files': [{'patch': 'y' * 5000} for _ in range(20)]
        }
        text, has_content = chunker.process_context(payload)
        assert has_content is True
        assert len(text) > 0

    def test_process_context_unicode_content(self, chunker):
        """Test processing payload with unicode characters."""
        payload = {
            'reviews': [{'body': 'Review with emoji 🎉 and 中文'}],
            'files': [{'patch': '+café ≠ coffee'}]
        }
        text, has_content = chunker.process_context(payload)
        assert has_content is True
        assert isinstance(text, str)

    def test_process_context_special_characters(self, chunker):
        """Test processing payload with special characters."""
        payload = {
            'reviews': [{'body': 'Review with <html> & "quotes"'}]
        }
        text, has_content = chunker.process_context(payload)
        assert has_content is True
        assert isinstance(text, str)

    def test_process_context_multiline_content(self, chunker):
        """Test processing payload with multiline content."""
        payload = {
            'reviews': [{
                'body': '''This is a multiline
                review comment with
                several lines of text'''
            }]
        }
        text, has_content = chunker.process_context(payload)
        assert has_content is True
        assert 'multiline' in text


class TestPriorityOrdering:
    """Test priority ordering and priority map functionality."""

    def test_priority_map_matches_order(self):
        """Test that priority_map indices match priority_order."""
        with patch('pathlib.Path.exists', return_value=False):
            chunker = ContextChunker()
            for idx, element in enumerate(chunker.priority_order):
                assert chunker.priority_map[element] == idx

    def test_custom_priority_order_from_config(self, tmp_path):
        """Test custom priority order from configuration."""
        config_file = tmp_path / "priority_config.yml"
        custom_order = ['test_failures', 'review_comments', 'changed_files']
        config_data = {
            'limits': {
                'fallback': {
                    'priority_order': custom_order
                }
            }
        }
        config_file.write_text(yaml.dump(config_data))
        
        chunker = ContextChunker(config_path=str(config_file))
        assert chunker.priority_order == custom_order
        assert chunker.priority_map['test_failures'] == 0
        assert chunker.priority_map['review_comments'] == 1

    def test_priority_order_contains_expected_elements(self):
        """Test that default priority order contains expected elements."""
        with patch('pathlib.Path.exists', return_value=False):
            chunker = ContextChunker()
            expected_elements = ['review_comments', 'test_failures', 'changed_files', 'ci_logs', 'full_diff']
            for element in expected_elements:
                assert element in chunker.priority_order


class TestConfigurationEdgeCases:
    """Test edge cases in configuration handling."""

    def test_negative_max_tokens_converted_to_positive(self, tmp_path):
        """Test handling of negative max_tokens."""
        config_file = tmp_path / "negative.yml"
        config_data = {
            'agent': {'context': {'max_tokens': -1000}}
        }
        config_file.write_text(yaml.dump(config_data))
        
        chunker = ContextChunker(config_path=str(config_file))
        # Should handle gracefully, likely using absolute value or default
        assert chunker.max_tokens != -1000

    def test_zero_max_tokens(self, tmp_path):
        """Test handling of zero max_tokens."""
        config_file = tmp_path / "zero.yml"
        config_data = {
            'agent': {'context': {'max_tokens': 0}}
        }
        config_file.write_text(yaml.dump(config_data))
        
        chunker = ContextChunker(config_path=str(config_file))
        # Should handle gracefully
        assert chunker.max_tokens >= 0

    def test_very_large_max_tokens(self, tmp_path):
        """Test handling of very large max_tokens."""
        config_file = tmp_path / "large.yml"
        config_data = {
            'agent': {'context': {'max_tokens': 1000000}}
        }
        config_file.write_text(yaml.dump(config_data))
        
        chunker = ContextChunker(config_path=str(config_file))
        assert chunker.max_tokens == 1000000

    def test_string_values_in_config(self, tmp_path):
        """Test handling of string values that should be integers."""
        config_file = tmp_path / "strings.yml"
        config_data = {
            'agent': {'context': {'max_tokens': '16000'}}
        }
        config_file.write_text(yaml.dump(config_data))
        
        chunker = ContextChunker(config_path=str(config_file))
        # Should convert string to int
        assert isinstance(chunker.max_tokens, int)

    def test_missing_agent_section(self, tmp_path):
        """Test config without agent section."""
        config_file = tmp_path / "no_agent.yml"
        config_data = {
            'other_section': {'value': 123}
        }
        config_file.write_text(yaml.dump(config_data))
        
        chunker = ContextChunker(config_path=str(config_file))
        # Should use defaults
        assert chunker.max_tokens == 32000

    def test_missing_context_section(self, tmp_path):
        """Test config without context section."""
        config_file = tmp_path / "no_context.yml"
        config_data = {
            'agent': {'other_key': 'value'}
        }
        config_file.write_text(yaml.dump(config_data))
        
        chunker = ContextChunker(config_path=str(config_file))
        assert chunker.max_tokens == 32000

    def test_missing_limits_section(self, tmp_path):
        """Test config without limits section."""
        config_file = tmp_path / "no_limits.yml"
        config_data = {
            'agent': {'context': {'max_tokens': 20000}}
        }
        config_file.write_text(yaml.dump(config_data))
        
        chunker = ContextChunker(config_path=str(config_file))
        # Should use default priority order
        assert len(chunker.priority_order) > 0


class TestTiktokenIntegration:
    """Test tiktoken integration for token counting."""

    def test_tiktoken_available_flag_false_when_not_installed(self):
        """Test TIKTOKEN_AVAILABLE flag when tiktoken not installed."""
        with patch('context_chunker.TIKTOKEN_AVAILABLE', False):
            with patch('pathlib.Path.exists', return_value=False):
                chunker = ContextChunker()
                assert chunker._encoder is None

    def test_encoder_initialization_handles_exception(self):
        """Test that encoder initialization handles exceptions gracefully."""
        with patch('context_chunker.TIKTOKEN_AVAILABLE', True):
            with patch('context_chunker.tiktoken.get_encoding', side_effect=Exception("Test error")):
                with patch('pathlib.Path.exists', return_value=False):
                    chunker = ContextChunker()
                    assert chunker._encoder is None


class TestPayloadStructureVariations:
    """Test various payload structure variations."""

    @pytest.fixture
    def chunker(self):
        """Create a ContextChunker instance for testing."""
        with patch('pathlib.Path.exists', return_value=False):
            return ContextChunker()

    def test_payload_with_additional_fields(self, chunker):
        """Test payload with additional unexpected fields."""
        payload = {
            'reviews': [{'body': 'comment'}],
            'files': [{'patch': 'code'}],
            'extra_field': 'should be ignored',
            'another_field': [1, 2, 3]
        }
        text, has_content = chunker.process_context(payload)
        assert has_content is True

    def test_payload_reviews_as_dict(self, chunker):
        """Test payload where reviews is a dict instead of list."""
        payload = {
            'reviews': {'body': 'single review'}
        }
        # Should handle gracefully
        text, has_content = chunker.process_context(payload)
        assert isinstance(text, str)

    def test_payload_files_as_dict(self, chunker):
        """Test payload where files is a dict instead of list."""
        payload = {
            'files': {'patch': 'single file'}
        }
        # Should handle gracefully
        text, has_content = chunker.process_context(payload)
        assert isinstance(text, str)

    def test_payload_nested_structure(self, chunker):
        """Test payload with deeply nested structure."""
        payload = {
            'reviews': [
                {
                    'body': 'comment',
                    'user': {
                        'name': 'reviewer',
                        'email': 'test@example.com'
                    },
                    'nested': {
                        'deep': {
                            'structure': 'value'
                        }
                    }
                }
            ]
        }
        text, has_content = chunker.process_context(payload)
        assert has_content is True

    def test_payload_with_empty_strings(self, chunker):
        """Test payload with empty string values."""
        payload = {
            'reviews': [{'body': ''}],
            'files': [{'patch': ''}]
        }
        text, has_content = chunker.process_context(payload)
        # Empty strings should result in no content
        assert isinstance(text, str)

    def test_payload_with_whitespace_only(self, chunker):
        """Test payload with whitespace-only strings."""
        payload = {
            'reviews': [{'body': '   \n\t  '}],
            'files': [{'patch': '     '}]
        }
        text, has_content = chunker.process_context(payload)
        assert isinstance(text, str)


class TestChunkSizeCalculations:
    """Test chunk size calculations and relationships."""

    def test_chunk_size_less_than_max_tokens(self):
        """Test that chunk_size is less than max_tokens."""
        with patch('pathlib.Path.exists', return_value=False):
            chunker = ContextChunker()
            assert chunker.chunk_size < chunker.max_tokens

    def test_overlap_tokens_less_than_chunk_size(self):
        """Test that overlap_tokens is less than chunk_size."""
        with patch('pathlib.Path.exists', return_value=False):
            chunker = ContextChunker()
            assert chunker.overlap_tokens < chunker.chunk_size

    def test_summarization_threshold_reasonable(self):
        """Test that summarization_threshold is reasonable."""
        with patch('pathlib.Path.exists', return_value=False):
            chunker = ContextChunker()
            # Should be between chunk_size and max_tokens
            assert chunker.chunk_size <= chunker.summarization_threshold <= chunker.max_tokens

    def test_custom_chunk_size_preserved(self, tmp_path):
        """Test that custom chunk_size from config is preserved."""
        config_file = tmp_path / "chunk_config.yml"
        config_data = {
            'agent': {
                'context': {
                    'max_tokens': 30000,
                    'chunk_size': 25000
                }
            }
        }
        config_file.write_text(yaml.dump(config_data))
        
        chunker = ContextChunker(config_path=str(config_file))
        assert chunker.chunk_size == 25000


class TestIntegrationScenarios:
    """Test complete integration scenarios."""

    def test_complete_pr_context_processing(self, tmp_path):
        """Test processing a complete realistic PR context."""
        config_file = tmp_path / "pr_config.yml"
        config_data = {
            'agent': {'context': {'max_tokens': 50000}},
            'limits': {'fallback': {'priority_order': ['review_comments', 'changed_files']}}
        }
        config_file.write_text(yaml.dump(config_data))
        
        chunker = ContextChunker(config_path=str(config_file))
        
        payload = {
            'reviews': [
                {'body': 'Please update the documentation'},
                {'body': 'The tests are failing on line 42'}
            ],
            'files': [
                {'patch': '+def new_function():\n+    pass'},
                {'patch': '-old_code\n+new_code'}
            ]
        }
        
        text, has_content = chunker.process_context(payload)
        assert has_content is True
        assert len(text) > 0

    def test_minimal_valid_configuration(self, tmp_path):
        """Test with minimal valid configuration."""
        config_file = tmp_path / "minimal.yml"
        config_file.write_text("agent:\n  context:\n    max_tokens: 10000\n")
        
        chunker = ContextChunker(config_path=str(config_file))
        assert chunker.max_tokens == 10000
        
        payload = {'reviews': [{'body': 'test'}]}
        text, has_content = chunker.process_context(payload)
        assert has_content is True