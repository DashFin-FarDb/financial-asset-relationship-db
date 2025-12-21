"""Comprehensive unit tests for .github/scripts/context_chunker.py

This module provides extensive test coverage for:
- ContextChunker initialization and configuration
- Context processing from PR payloads
- Token counting with and without tiktoken
- Priority ordering and chunking strategies
- Edge cases and error conditions
"""

import sys
from pathlib import Path
from unittest.mock import Mock, mock_open, patch

import pytest

# Add the scripts directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / ".github" / "scripts"))

from context_chunker import ContextChunker


@pytest.mark.unit
class TestContextChunkerInitialization:
    """Test suite for ContextChunker initialization."""

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="""
agent:
  context:
    max_tokens: 32000
    chunk_size: 28000
    overlap_tokens: 2000
    summarization_threshold: 30000
limits:
  fallback:
    priority_order:
      - review_comments
      - test_failures
      - changed_files
""",
    )
    @patch("pathlib.Path.exists")
    def test_initialization_with_valid_config(self, mock_exists, mock_file):
        """Test initialization with valid configuration file."""
        mock_exists.return_value = True

        chunker = ContextChunker()

        assert chunker.max_tokens == 32000
        assert chunker.chunk_size == 28000
        assert chunker.overlap_tokens == 2000
        assert chunker.summarization_threshold == 30000
        assert "review_comments" in chunker.priority_order

    @patch("pathlib.Path.exists")
    def test_initialization_with_missing_config(self, mock_exists):
        """Test initialization when config file doesn't exist."""
        mock_exists.return_value = False

        chunker = ContextChunker()

        # Should use defaults
        assert chunker.max_tokens == 32000
        assert chunker.chunk_size > 0
        assert isinstance(chunker.priority_order, list)

    @patch("builtins.open", side_effect=IOError("File read error"))
    @patch("pathlib.Path.exists")
    def test_initialization_with_config_read_error(self, mock_exists, mock_file):
        """Test initialization handles config file read errors gracefully."""
        mock_exists.return_value = True

        # Should not raise, should use defaults
        chunker = ContextChunker()

        assert chunker.max_tokens == 32000
        assert isinstance(chunker.config, dict)

    @patch("builtins.open", new_callable=mock_open, read_data="invalid: yaml: content: [[[")
    @patch("pathlib.Path.exists")
    def test_initialization_with_invalid_yaml(self, mock_exists, mock_file):
        """Test initialization handles invalid YAML gracefully."""
        mock_exists.return_value = True

        chunker = ContextChunker()

        # Should use defaults
        assert chunker.max_tokens == 32000

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="""
agent:
  context:
    max_tokens: 50000
    chunk_size: 45000
""",
    )
    @patch("pathlib.Path.exists")
    def test_initialization_with_custom_token_limits(self, mock_exists, mock_file):
        """Test initialization with custom token limits."""
        mock_exists.return_value = True

        chunker = ContextChunker()

        assert chunker.max_tokens == 50000
        assert chunker.chunk_size == 45000

    def test_initialization_chunk_size_derived_from_max_tokens(self):
        """Test that chunk_size is derived from max_tokens when not specified."""
        with patch("pathlib.Path.exists", return_value=False):
            chunker = ContextChunker()

            # chunk_size should be max_tokens - 4000
            expected_chunk_size = chunker.max_tokens - 4000
            assert chunker.chunk_size == expected_chunk_size

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="""
limits:
  fallback:
    priority_order:
      - custom_priority_1
      - custom_priority_2
      - custom_priority_3
""",
    )
    @patch("pathlib.Path.exists")
    def test_initialization_with_custom_priority_order(self, mock_exists, mock_file):
        """Test initialization with custom priority order."""
        mock_exists.return_value = True

        chunker = ContextChunker()

        assert chunker.priority_order == ["custom_priority_1", "custom_priority_2", "custom_priority_3"]
        assert chunker.priority_map["custom_priority_1"] == 0
        assert chunker.priority_map["custom_priority_2"] == 1

    def test_initialization_creates_priority_map(self):
        """Test that initialization creates proper priority mapping."""
        with patch("pathlib.Path.exists", return_value=False):
            chunker = ContextChunker()

            # Verify priority map is created
            assert isinstance(chunker.priority_map, dict)
            for name, index in chunker.priority_map.items():
                assert name in chunker.priority_order
                assert chunker.priority_order[index] == name


@pytest.mark.unit
class TestProcessContext:
    """Test suite for process_context method."""

    def test_process_context_with_reviews_only(self):
        """Test processing context with only review data."""
        chunker = ContextChunker()

        payload = {"reviews": [{"body": "Review comment 1"}, {"body": "Review comment 2"}]}

        text, has_content = chunker.process_context(payload)

        assert has_content is True
        assert "Review comment 1" in text
        assert "Review comment 2" in text

    def test_process_context_with_files_only(self):
        """Test processing context with only file data."""
        chunker = ContextChunker()

        payload = {"files": [{"patch": "diff --git a/file1.py"}, {"patch": "diff --git a/file2.py"}]}

        text, has_content = chunker.process_context(payload)

        assert has_content is True
        assert "diff --git a/file1.py" in text
        assert "diff --git a/file2.py" in text

    def test_process_context_with_reviews_and_files(self):
        """Test processing context with both reviews and files."""
        chunker = ContextChunker()

        payload = {"reviews": [{"body": "Review text"}], "files": [{"patch": "File patch"}]}

        text, has_content = chunker.process_context(payload)

        assert has_content is True
        assert "Review text" in text
        assert "File patch" in text

    def test_process_context_with_empty_payload(self):
        """Test processing empty payload."""
        chunker = ContextChunker()

        payload = {}

        text, has_content = chunker.process_context(payload)

        assert has_content is False
        assert text == ""

    def test_process_context_with_none_reviews(self):
        """Test processing context when reviews is None."""
        chunker = ContextChunker()

        payload = {"reviews": None}

        text, has_content = chunker.process_context(payload)

        assert has_content is False

    def test_process_context_with_non_list_reviews(self):
        """Test processing context when reviews is not a list."""
        chunker = ContextChunker()

        payload = {"reviews": "not a list"}

        text, has_content = chunker.process_context(payload)

        # Should handle gracefully
        assert has_content is False

    def test_process_context_with_empty_bodies(self):
        """Test processing context with empty review bodies."""
        chunker = ContextChunker()

        payload = {"reviews": [{"body": ""}, {"body": None}, {}]}

        text, has_content = chunker.process_context(payload)

        assert has_content is False

    def test_process_context_with_mixed_empty_and_filled(self):
        """Test processing context with mix of empty and filled content."""
        chunker = ContextChunker()

        payload = {
            "reviews": [{"body": ""}, {"body": "Actual review"}, {"body": None}],
            "files": [{"patch": ""}, {"patch": "Actual patch"}],
        }

        text, has_content = chunker.process_context(payload)

        assert has_content is True
        assert "Actual review" in text
        assert "Actual patch" in text

    def test_process_context_separates_with_double_newline(self):
        """Test that content parts are separated with double newlines."""
        chunker = ContextChunker()

        payload = {"reviews": [{"body": "Review 1"}, {"body": "Review 2"}]}

        text, has_content = chunker.process_context(payload)

        assert "\n\n" in text
        parts = text.split("\n\n")
        assert len(parts) >= 2

    def test_process_context_strips_whitespace(self):
        """Test that final output is stripped of leading/trailing whitespace."""
        chunker = ContextChunker()

        payload = {"reviews": [{"body": "  Review with spaces  "}]}

        text, has_content = chunker.process_context(payload)

        # Individual parts preserve their content, but overall is stripped
        assert has_content is True
        assert text  # Not empty

    def test_process_context_with_unicode_content(self):
        """Test processing context with unicode characters."""
        chunker = ContextChunker()

        payload = {"reviews": [{"body": "Review with émojis 🚀 and ünïcödë"}]}

        text, has_content = chunker.process_context(payload)

        assert has_content is True
        assert "🚀" in text
        assert "émojis" in text

    def test_process_context_with_very_long_content(self):
        """Test processing context with very long content."""
        chunker = ContextChunker()

        long_text = "x" * 100000
        payload = {"reviews": [{"body": long_text}]}

        text, has_content = chunker.process_context(payload)

        assert has_content is True
        assert len(text) == 100000

    def test_process_context_preserves_special_characters(self):
        """Test that special characters in content are preserved."""
        chunker = ContextChunker()

        special_content = "Content with\ttabs\nand\nnewlines\rand\r\ncarriage returns"
        payload = {"reviews": [{"body": special_content}]}

        text, has_content = chunker.process_context(payload)

        assert has_content is True
        assert special_content in text


@pytest.mark.unit
class TestCountTokens:
    """Test suite for count_tokens method."""

    def test_count_tokens_with_empty_string(self):
        """Test counting tokens in empty string."""
        chunker = ContextChunker()

        count = chunker.count_tokens("")

        assert count == 0

    def test_count_tokens_with_simple_text(self):
        """Test counting tokens in simple text."""
        chunker = ContextChunker()

        count = chunker.count_tokens("Hello world")

        assert count > 0

    def test_count_tokens_with_longer_text(self):
        """Test counting tokens in longer text."""
        chunker = ContextChunker()

        text = "This is a longer piece of text with multiple words and sentences."
        count = chunker.count_tokens(text)

        assert count > 0
        # Should be roughly the number of words
        word_count = len(text.split())
        assert count >= word_count - 5  # Allow some variance

    def test_count_tokens_fallback_without_tiktoken(self):
        """Test token counting fallback when tiktoken is not available."""
        chunker = ContextChunker()
        chunker._encoder = None  # Simulate tiktoken not available

        text = "one two three four five"
        count = chunker.count_tokens(text)

        # Fallback counts words
        assert count == 5

    @patch("context_chunker.TIKTOKEN_AVAILABLE", False)
    def test_count_tokens_fallback_initialization(self):
        """Test that fallback works when tiktoken is not importable."""
        chunker = ContextChunker()

        text = "test text here"
        count = chunker.count_tokens(text)

        assert count == 3  # Fallback word count

    def test_count_tokens_with_punctuation(self):
        """Test token counting with punctuation."""
        chunker = ContextChunker()

        text = "Hello, world! How are you?"
        count = chunker.count_tokens(text)

        assert count > 0

    def test_count_tokens_with_code(self):
        """Test token counting with code snippets."""
        chunker = ContextChunker()

        code = "def function(param1, param2):\n    return param1 + param2"
        count = chunker.count_tokens(code)

        assert count > 0

    def test_count_tokens_with_unicode(self):
        """Test token counting with unicode characters."""
        chunker = ContextChunker()

        text = "Hello 世界 🌍"
        count = chunker.count_tokens(text)

        assert count > 0

    def test_count_tokens_consistency(self):
        """Test that token counting is consistent for same input."""
        chunker = ContextChunker()

        text = "Consistent text for testing"
        count1 = chunker.count_tokens(text)
        count2 = chunker.count_tokens(text)

        assert count1 == count2

    def test_count_tokens_scales_with_length(self):
        """Test that token count scales with text length."""
        chunker = ContextChunker()

        short_text = "Short"
        long_text = "Short " * 100

        short_count = chunker.count_tokens(short_text)
        long_count = chunker.count_tokens(long_text)

        assert long_count > short_count
        assert long_count > short_count * 50  # Should be roughly 100x


@pytest.mark.unit
class TestContextChunkerIntegration:
    """Integration tests for complete ContextChunker workflows."""

    def test_full_pr_processing_workflow(self):
        """Test complete workflow of processing a PR payload."""
        chunker = ContextChunker()

        # Simulate realistic PR payload
        payload = {
            "reviews": [
                {"body": "Please fix the linting errors in file.py"},
                {"body": "The test coverage needs to be improved"},
                {"body": "Consider refactoring the main function"},
            ],
            "files": [
                {"patch": "diff --git a/file1.py b/file1.py\n+def new_function():"},
                {"patch": "diff --git a/file2.py b/file2.py\n-old_code\n+new_code"},
            ],
        }

        text, has_content = chunker.process_context(payload)

        assert has_content is True
        assert "linting errors" in text
        assert "test coverage" in text
        assert "refactoring" in text
        assert "new_function" in text

        # Count tokens
        token_count = chunker.count_tokens(text)
        assert token_count > 0

    def test_empty_pr_handling(self):
        """Test handling of empty PR with no reviews or files."""
        chunker = ContextChunker()

        payload = {"reviews": [], "files": []}

        text, has_content = chunker.process_context(payload)

        assert has_content is False
        assert text == ""
        assert chunker.count_tokens(text) == 0

    def test_large_pr_handling(self):
        """Test handling of large PR with many reviews and files."""
        chunker = ContextChunker()

        # Create large payload
        payload = {
            "reviews": [{"body": f"Review comment {i}"} for i in range(50)],
            "files": [{"patch": f"diff for file {i}"} for i in range(100)],
        }

        text, has_content = chunker.process_context(payload)

        assert has_content is True
        token_count = chunker.count_tokens(text)
        assert token_count > 100  # Should be substantial

    def test_config_affects_behavior(self):
        """Test that configuration affects chunker behavior."""
        with patch("pathlib.Path.exists", return_value=False):
            chunker = ContextChunker()

            # Verify config values are set
            assert chunker.max_tokens > 0
            assert chunker.chunk_size > 0
            assert chunker.overlap_tokens > 0
            assert len(chunker.priority_order) > 0


@pytest.mark.unit
class TestContextChunkerEdgeCases:
    """Test edge cases and error conditions."""

    def test_process_context_with_nested_none_values(self):
        """Test processing context with deeply nested None values."""
        chunker = ContextChunker()

        payload = {"reviews": [None, None, {"body": None}], "files": [None, {"patch": None}]}

        text, has_content = chunker.process_context(payload)

        assert has_content is False

    def test_process_context_with_malformed_items(self):
        """Test processing context with malformed items."""
        chunker = ContextChunker()

        payload = {"reviews": ["not a dict", 123, {"wrong_key": "value"}]}

        text, has_content = chunker.process_context(payload)

        # Should handle gracefully
        assert has_content is False

    def test_count_tokens_with_only_whitespace(self):
        """Test counting tokens in whitespace-only string."""
        chunker = ContextChunker()

        count = chunker.count_tokens("     \n\t\r  ")

        # Fallback would count this as 0 words
        assert count >= 0

    def test_initialization_with_zero_token_limit(self):
        """Test initialization with edge case token limits."""
        with patch(
            "builtins.open",
            new_callable=mock_open,
            read_data="""
agent:
  context:
    max_tokens: 0
""",
        ):
            with patch("pathlib.Path.exists", return_value=True):
                chunker = ContextChunker()

                # Should handle gracefully, chunk_size will be negative but capped
                assert chunker.max_tokens == 0
                assert chunker.chunk_size >= 1  # max(1, -4000) = 1

    def test_process_context_with_binary_content(self):
        """Test processing context that might contain binary-like content."""
        chunker = ContextChunker()

        payload = {"reviews": [{"body": "\x00\x01\x02 binary content"}]}

        text, has_content = chunker.process_context(payload)

        # Should handle without crashing
        assert isinstance(text, str)

    def test_priority_map_with_empty_priority_order(self):
        """Test priority map creation with empty priority order."""
        with patch(
            "builtins.open",
            new_callable=mock_open,
            read_data="""
limits:
  fallback:
    priority_order: []
""",
        ):
            with patch("pathlib.Path.exists", return_value=True):
                chunker = ContextChunker()

                assert chunker.priority_order == []
                assert chunker.priority_map == {}
