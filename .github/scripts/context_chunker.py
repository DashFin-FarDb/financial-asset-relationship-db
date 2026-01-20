#!/usr/bin/env python3
"""
Context chunker for PR Agent.

This module provides intelligent context chunking to handle large PRs
without hitting token limits. It implements priority-based processing,
smart chunking, and automatic summarization.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


class ContextChunker:
    """
    Handles intelligent context chunking for large PRs.

    Provides priority-based processing, smart chunking with overlap,
    and automatic summarization when content exceeds token limits.
    """

    def __init__(self, config_path: str = ".github/pr-agent-config.yml"):
        """
        Load configuration and initialize context-chunking parameters and the tokenizer.
        
        Reads settings from the provided YAML config (if available) and initializes instance attributes used for chunking: `config`, `max_tokens`, `chunk_size`, `overlap_tokens`, `summarization_threshold`, `priority_order`, `priority_map`, and `_encoder`.
        
        Parameters:
            config_path (str): Path to the YAML configuration file (default: ".github/pr-agent-config.yml").
        """
        self.config: Dict = self._load_config(config_path)

        # Read agent context settings with safe defaults
        agent_cfg = (self.config.get("agent") or {}).get("context") or {}
        self.max_tokens = int(agent_cfg.get("max_tokens", 32000))
        self.chunk_size = int(agent_cfg.get("chunk_size", max(1, self.max_tokens - 4000)))
        self.overlap_tokens = int(agent_cfg.get("overlap_tokens", 2000))
        self.summarization_threshold = int(
            agent_cfg.get("summarization_threshold", int(self.max_tokens * 0.9))
        )

        # Prepare priority order
        limits_cfg = (self.config.get("limits") or {}).get("fallback") or {}
        self.priority_order = limits_cfg.get(
            "priority_order",
            ["review_comments", "test_failures", "changed_files", "ci_logs", "full_diff"],
        )
        # Map chunk type to priority index (lower is higher priority)
        self.priority_map = {name: i for i, name in enumerate(self.priority_order)}

        # Setup tokenizer/encoder if tiktoken available
        self._encoder = self._init_encoder()

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """
        Load YAML configuration from disk and return it as a dictionary.
        
        If the file does not exist, the YAML library is unavailable, or an error occurs while reading/parsing,
        an empty dict is returned and a warning is emitted to stderr.
        
        Returns:
            Dict[str, Any]: Parsed configuration mapping, or an empty dict on missing/invalid config.
        """
        cfg_file = Path(config_path)
        if not (cfg_file.exists() and yaml is not None):
            return {}

        try:
            with cfg_file.open("r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Warning: failed to load config from {config_path}: {e}", file=sys.stderr)
            return {}

def _init_encoder(self):
    """
    Initialize the optional tiktoken encoder.
    
    Returns:
        The tiktoken encoder instance if available and successfully initialized, `None` otherwise.
    """
    if not TIKTOKEN_AVAILABLE:
        return None
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception as e:
        print(f"Warning: failed to initialize tiktoken encoder: {e}", file=sys.stderr)
        return None
        """
        Initialize the optional tiktoken encoder and load agent context settings.
        
        Loads configuration from the repository (if available), populates self.config and context-related attributes
        (self.max_tokens, self.chunk_size, self.overlap_tokens, self.summarization_threshold), and builds chunk
        priority structures (self.priority_order, self.priority_map). Attempts to initialize and store the tiktoken
        encoder on self._encoder.
        
        Returns:
            The tiktoken encoder instance if available and successfully initialized, `None` otherwise.
        """
        if not TIKTOKEN_AVAILABLE:
            return None
        try:
            return tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            print(f"Warning: failed to initialize tiktoken encoder: {e}", file=sys.stderr)
            return None
        self.config: Dict = {}

        # Load configuration if available
        cfg_file = Path(config_path)
        if cfg_file.exists() and yaml is not None:
            try:
                with cfg_file.open("r", encoding="utf-8") as f:
                    self.config = yaml.safe_load(f) or {}
            except Exception as e:
                print(f"Warning: failed to load config from {config_path}: {e}", file=sys.stderr)
                self.config = {}

        # Read agent context settings with safe defaults
        agent_cfg = (self.config.get("agent") or {}).get("context") or {}
        self.max_tokens: int = int(agent_cfg.get("max_tokens", 32000))
        self.chunk_size: int = int(agent_cfg.get("chunk_size", max(1, self.max_tokens - 4000)))
        self.overlap_tokens: int = int(agent_cfg.get("overlap_tokens", 2000))
        self.summarization_threshold: int = int(
            agent_cfg.get("summarization_threshold", int(self.max_tokens * 0.9))
        )

        # Prepare priority order
        limits_cfg = (self.config.get("limits") or {}).get("fallback") or {}
        self.priority_order: List[str] = limits_cfg.get("priority_order", [
            "review_comments",
            "test_failures",
            "changed_files",
            "ci_logs",
            "full_diff",
        ])
        # Map chunk type to priority index (lower is higher priority)
        self.priority_map: Dict[str, int] = {name: i for i, name in enumerate(self.priority_order)}

        # Setup tokenizer/encoder if tiktoken available
        self._encoder = None
        if TIKTOKEN_AVAILABLE:
            try:
                self._encoder = tiktoken.get_encoding("cl100k_base")
            except Exception as e:
                print(f"Warning: failed to initialize tiktoken encoder: {e}", file=sys.stderr)
                self._encoder = None

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate the number of tokens contained in the provided text.
        
        Uses an available encoder for exact counts; otherwise returns a heuristic estimate. Returns `0` for empty input.
        
        Returns:
            int: Estimated token count (`0` for empty input).
        """
        if not text:
            return 0

        if self._encoder is not None:
            try:
                return len(self._encoder.encode(text))
            except Exception as e:
                # Log encoding failure and fall back to heuristic
                print(f"Warning: tiktoken encoding failed: {e}", file=sys.stderr)
                pass

        # Heuristic fallback: ~4 chars per token with adjustments
        base_tokens = len(text) / 4.0

        # Adjust for code structural characters
        structural_chars = sum(1 for c in text if c in "{}()[];")
        base_tokens += structural_chars * 0.5

        # Adjust for whitespace sequences
        whitespace_count = sum(
            1 for i, c in enumerate(text)
            if c.isspace() and (i == 0 or not text[i - 1].isspace())
        )
        base_tokens += whitespace_count * 0.25

        # Adjust for markdown formatting
        format_chars = sum(1 for c in text if c in "*_`#-")
        base_tokens += format_chars * 0.3

        # Add 10% safety margin
        return int(base_tokens * 1.1)

    def process_context(self, pr_data: Dict[str, Any]) -> Tuple[str, bool]:
        """
        Produce a combined or chunked PR content string based on token limits.
        
        Parameters:
            pr_data (Dict[str, Any]): PR data dictionary containing keys such as `reviews`, `files`, `test_failures`, `ci_logs`, and `full_diff`.
        
        Returns:
            Tuple[str, bool]: A tuple where the first element is the assembled content (combined or chunked) and the second element is `True` if chunking was applied, `False` otherwise.
        """
        chunks = self._extract_chunks(pr_data)
        total_tokens = sum(self.estimate_tokens(chunk.get("content", "")) for chunk in chunks)

        if total_tokens <= self.max_tokens:
            # No chunking needed
            content = self._combine_chunks(chunks)
            return content, False

        # Apply chunking

    def _extract_chunks(self, pr_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Builds an ordered list of content chunks extracted from PR data for prioritized processing.
        
        Parameters:
            pr_data (Dict[str, Any]): PR data source. Recognized keys include:
                - "reviews": list of review dicts
                - "files": list of changed-file dicts
                - "test_failures": list of test-failure dicts
                - "ci_logs": CI log string
                - "diff": full diff string
        
        Returns:
            List[Dict[str, Any]]: A list of chunk dictionaries sorted by priority (lower value = higher priority).
                Each chunk dict contains:
                    - "type" (str): chunk category (e.g., "review_comments", "changed_files").
                    - "content" (str): formatted text for the chunk.
                    - "priority" (int): numeric priority used for ordering.
        """
        chunks: List[Dict[str, Any]] = []

        # Extract review comments
        reviews = pr_data.get("reviews", [])
        if reviews:
            review_content = self._format_reviews(reviews)
            chunks.append({
                "type": "review_comments",
                "content": review_content,
                "priority": self.priority_map.get("review_comments", 0),
            })

        # Extract changed files
        files = pr_data.get("files", [])
        if files:
            files_content = self._format_files(files)
            chunks.append({
                "type": "changed_files",
                "content": files_content,
                "priority": self.priority_map.get("changed_files", 2),
            })

        # Extract test failures
        test_failures = pr_data.get("test_failures", [])
        if test_failures:
            failures_content = self._format_test_failures(test_failures)
            chunks.append({
                "type": "test_failures",
                "content": failures_content,
                "priority": self.priority_map.get("test_failures", 1),
            })

        # Extract CI logs
        ci_logs = pr_data.get("ci_logs", "")
        if ci_logs:
            chunks.append({
                "type": "ci_logs",
                "content": ci_logs,
                "priority": self.priority_map.get("ci_logs", 3),
            })

        # Extract full diff
        full_diff = pr_data.get("diff", "")
        if full_diff:
            chunks.append({
                "type": "full_diff",
                "content": full_diff,
                "priority": self.priority_map.get("full_diff", 4),
            })

        # Sort by priority (lower number = higher priority)
        chunks.sort(key=lambda x: x.get("priority", 999))
        return chunks

    def _format_reviews(self, reviews: List[Dict[str, Any]]) -> str:
        """
        Format a list of review dictionaries into a markdown string with headings for each reviewer and their state.
        
        Each review dict is expected to include the keys 'user' (a dict with 'login'), 'state', and 'body'; missing values are replaced with sensible defaults.
        
        Parameters:
            reviews (List[Dict[str, Any]]): Review objects to format.
        
        Returns:
            str: A markdown-formatted string starting with "## Review Comments" and containing one subsection per review in the form "### @<login> (<state>)" followed by the review body.
        """
        lines = ["## Review Comments\n"]
        for review in reviews:
            user = review.get("user", {}).get("login", "unknown")
            state = review.get("state", "unknown")
            body = review.get("body", "")
            lines.append(f"### @{user} ({state})\n{body}\n")
        return "\n".join(lines)

    def _format_files(self, files: List[Dict[str, Any]]) -> str:
        """
        Format a list of file-change records into a markdown-style summary with diffs.
        
        Each record in `files` may include the keys:
        - `filename` (str): path or name of the changed file.
        - `additions` (int): number of added lines.
        - `deletions` (int): number of removed lines.
        - `patch` (str): unified diff or patch fragment for the file.
        
        Parameters:
            files: List of file-change dictionaries as described above.
        
        Returns:
            A single string containing a markdown-style "Changed Files" section where each file is listed with its addition/deletion counts and an optional fenced diff block for the `patch`.
        """
        lines = ["## Changed Files\n"]
        for f in files:
            filename = f.get("filename", "unknown")
            additions = f.get("additions", 0)
            deletions = f.get("deletions", 0)
            patch = f.get("patch", "")
            lines.append(f"### {filename} (+{additions}/-{deletions})\n")
            if patch:
                lines.append(f"```diff\n{patch}\n```\n")
        return "\n".join(lines)

    def _format_test_failures(self, failures: List[Dict[str, Any]]) -> str:
        """
        Format a list of test failure records into a markdown-style string.
        
        Each failure record may include the keys "name" (test name) and "message" (failure details). Missing names default to "unknown test".
        
        Parameters:
            failures (List[Dict[str, Any]]): Test failure records to format.
        
        Returns:
            str: Markdown-formatted content starting with "## Test Failures" and a "### {test name}" section for each failure containing its message.
        """
        lines = ["## Test Failures\n"]
        for failure in failures:
            test_name = failure.get("name", "unknown test")
            message = failure.get("message", "")
            lines.append(f"### {test_name}\n{message}\n")
        return "\n".join(lines)

    def _combine_chunks(self, chunks: List[Dict[str, Any]]) -> str:
        """
        Concatenate the `content` fields of multiple chunks into a single string separated by two newlines.
        
        Parameters:
            chunks (List[Dict[str, Any]]): List of chunk dictionaries; each chunk's `"content"` value will be used (missing or falsy `"content"` is treated as an empty string).
        
        Returns:
            str: The combined content string.
        """
        return "\n\n".join(chunk.get("content", "") for chunk in chunks)

    def _build_limited_content(self, chunks: List[Dict[str, Any]]) -> str:
        """
        Build content limited to max_tokens by prioritizing chunks.

        This method processes chunks in priority order, including as much
        content as possible while staying within token limits. Higher priority
        chunks are included first, and lower priority chunks are truncated
        or omitted if necessary.

        Parameters:
            chunks: Collection of content chunks to process, each containing
                   'type', 'content', and 'priority' keys.

        Returns:
            str: The processed content, limited to max_tokens.
        """
        if not chunks:
            return ""

        # Sort chunks by priority (already sorted, but ensure)
        sorted_chunks = sorted(chunks, key=lambda x: x.get("priority", 999))

        result_parts: List[str] = []
        remaining_tokens = self.max_tokens

        for chunk in sorted_chunks:
            content = chunk.get("content", "")
            chunk_type = chunk.get("type", "unknown")

            if not content:
                continue

            chunk_tokens = self.estimate_tokens(content)
            processed_chunk, tokens_used, should_break = self._process_chunk(
                content, chunk_type, chunk_tokens, remaining_tokens
            )

            if processed_chunk:
                result_parts.append(processed_chunk)
                remaining_tokens -= tokens_used

            if should_break:
                break

        return "\n\n".join(result_parts)

    def _process_chunk(
        self, content: str, chunk_type: str, chunk_tokens: int, remaining_tokens: int
    ) -> Tuple[str, int, bool]:
        """
        Decide how to include a single content chunk given the remaining token budget.
        
        Parameters:
            content (str): The chunk content.
            chunk_type (str): Identifier for the chunk type (used in truncation/omission notes).
            chunk_tokens (int): Estimated token count for the full chunk.
            remaining_tokens (int): Available token budget.
        
        Returns:
            processed_content (str): The content to include (possibly truncated or an omission note).
            tokens_used (int): Number of tokens that will be consumed by the returned content.
            stop_processing (bool): `True` if no further chunks should be processed after this one, `False` otherwise.
        """
        if chunk_tokens <= remaining_tokens:
            return content, chunk_tokens, False

        if remaining_tokens > 500:
            return self._handle_truncation(content, chunk_type, remaining_tokens)

        return self._handle_omission(chunk_type, chunk_tokens)

    def _handle_truncation(
        self, content: str, chunk_type: str, remaining_tokens: int
    ) -> Tuple[str, int, bool]:
        """
        Truncate a chunk to fit the remaining token budget and append a truncation notice.
        
        Parameters:
            content: The chunk content to truncate.
            chunk_type: Identifier used in the appended truncation notice.
            remaining_tokens: Available token budget.
        
        Returns:
            (str, int, bool): Truncated content with a trailing note, the estimated token count of that content, and `False` to indicate processing should continue.
        """
        truncated = self._truncate_to_tokens(content, remaining_tokens - 100)
        if truncated:
            truncated_with_note = truncated + f"\n\n[{chunk_type} truncated due to token limit]"
            truncated_tokens = self.estimate_tokens(truncated_with_note)
            return truncated_with_note, truncated_tokens, False
        return "", 0, False

    def _handle_omission(self, chunk_type: str, chunk_tokens: int) -> Tuple[str, int, bool]:
        """
        Produce an omission notice for a chunk when there is no remaining token budget.
        
        Parameters:
            chunk_type (str): Identifier for the chunk type being omitted (e.g., "ci_logs").
            chunk_tokens (int): Estimated number of tokens that the omitted chunk would have consumed.
        
        Returns:
            omission_note (str): Human-readable notice explaining the omission and token count.
            tokens_used (int): Always 0 for omitted chunks.
            stop_processing (bool): Always True to indicate no further chunks should be included.
        """
        omission_note = (
            f"\n[{chunk_type} omitted due to token limit - "
            f"contained {chunk_tokens} tokens]"
        )
        return omission_note, 0, True

    def _find_natural_boundary(self, text: str) -> str:
        """
        Truncate text at a natural boundary (the last newline) when that boundary occurs after the midpoint.
        
        Parameters:
            text (str): The input text to potentially truncate.
        
        Returns:
            str: The input truncated at the last newline if that newline is located after half the text length, otherwise the original input.
        """
        last_newline = text.rfind('\n')
        if last_newline > len(text) // 2:
            return text[:last_newline]
        return text

    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """
        Truncates text so its estimated token count does not exceed max_tokens.
        
        Attempts to prefer natural boundaries (newlines/sentences) and iteratively trims until the estimated token count fits within the limit.
        
        Parameters:
            text (str): The text to truncate.
            max_tokens (int): Maximum number of tokens allowed; non-positive values produce an empty string.
        
        Returns:
            str: Truncated text whose estimated token count is <= max_tokens, or an empty string if nothing fits.
        """
        if not text or max_tokens <= 0:
            return ""

        current_tokens = self.estimate_tokens(text)
        if current_tokens <= max_tokens:
            return text

        # Estimate character count for target tokens
        # Using conservative estimate of 3 chars per token (lower than the 4.0
        # used in heuristic estimation to ensure we don't exceed the limit)
        chars_per_token_conservative = 3
        target_chars = max_tokens * chars_per_token_conservative

        if target_chars >= len(text):
            return text

        # Try to truncate at a natural boundary
        truncated = self._find_natural_boundary(text[:target_chars])

        # Re-check token count and further trim if necessary
        while self.estimate_tokens(truncated) > max_tokens and len(truncated) > 0:
            # Trim by 10% of current length or at least 100 characters
            trim_amount = max(100, len(truncated) // 10)
            truncated = self._find_natural_boundary(truncated[:-trim_amount])

        return truncated


def main():
    """Example usage of the ContextChunker."""
    chunker = ContextChunker()

    # Example PR data
    example_pr = {
        'reviews': [
            {
                'user': {'login': 'reviewer1'},
                'state': 'changes_requested',
                'body': 'Please fix the bug in the database connection and add tests.'
            }
        ],
        'files': [
            {
                'filename': 'src/data/database.py',
                'additions': 50,
                'deletions': 20,
                'patch': '@@ -1,5 +1,10 @@\n-old code\n+new code'
            }
        ]
    }

    processed, chunked = chunker.process_context(example_pr)
    print(f"Chunked: {chunked}")
    print(f"\nProcessed content:\n{processed}")


if __name__ == "__main__":
    main()