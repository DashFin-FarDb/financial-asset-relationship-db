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
        Initialize the ContextChunker with configuration.

        Parameters:
            config_path: Path to the YAML configuration file.
        """
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
        Estimate the number of tokens in the given text.

        Uses tiktoken for accurate counting when available,
        otherwise falls back to heuristic estimation.

        Parameters:
            text: The text to estimate tokens for.

        Returns:
            int: Estimated number of tokens.
        """
        if not text:
            return 0

        if self._encoder is not None:
            try:
                return len(self._encoder.encode(text))
            except Exception:
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
        Process PR context data and return chunked/summarized content.

        Parameters:
            pr_data: Dictionary containing PR data (reviews, files, etc.).

        Returns:
            Tuple[str, bool]: Processed content and whether chunking was applied.
        """
        chunks = self._extract_chunks(pr_data)
        total_tokens = sum(self.estimate_tokens(chunk.get("content", "")) for chunk in chunks)

        if total_tokens <= self.max_tokens:
            # No chunking needed
            content = self._combine_chunks(chunks)
            return content, False

        # Apply chunking
        processed_content = self._build_limited_content(chunks)
        return processed_content, True

    def _extract_chunks(self, pr_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract chunks from PR data organized by type.

        Parameters:
            pr_data: Dictionary containing PR data.

        Returns:
            List of chunk dictionaries with type and content.
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
        Format review comments into readable content.

        Parameters:
            reviews: List of review dictionaries.

        Returns:
            str: Formatted review content.
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
        Format changed files into readable content.

        Parameters:
            files: List of file change dictionaries.

        Returns:
            str: Formatted files content.
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
        Format test failures into readable content.

        Parameters:
            failures: List of test failure dictionaries.

        Returns:
            str: Formatted test failures content.
        """
        lines = ["## Test Failures\n"]
        for failure in failures:
            test_name = failure.get("name", "unknown test")
            message = failure.get("message", "")
            lines.append(f"### {test_name}\n{message}\n")
        return "\n".join(lines)

    def _combine_chunks(self, chunks: List[Dict[str, Any]]) -> str:
        """
        Combine all chunks into a single content string.

        Parameters:
            chunks: List of chunk dictionaries.

        Returns:
            str: Combined content.
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

            if chunk_tokens <= remaining_tokens:
                # Chunk fits entirely
                result_parts.append(content)
                remaining_tokens -= chunk_tokens
            elif remaining_tokens > 500:
                # Truncate chunk to fit remaining space
                truncated = self._truncate_to_tokens(content, remaining_tokens - 100)
                if truncated:
                    truncated_with_note = truncated + f"\n\n[{chunk_type} truncated due to token limit]"
                    result_parts.append(truncated_with_note)
                    # Update remaining tokens after truncation
                    truncated_tokens = self.estimate_tokens(truncated_with_note)
                    remaining_tokens -= truncated_tokens
                # Continue to try fitting more chunks instead of breaking
            else:
                # Not enough space, add summary note
                result_parts.append(
                    f"\n[{chunk_type} omitted due to token limit - "
                    f"contained {chunk_tokens} tokens]"
                )
                break

        return "\n\n".join(result_parts)

    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """
        Truncate text to approximately max_tokens.

        Attempts to truncate at natural boundaries (newlines, sentences).
        Re-checks token count after truncation to ensure it doesn't exceed the limit.

        Parameters:
            text: The text to truncate.
            max_tokens: Maximum number of tokens to allow.

        Returns:
            str: Truncated text.
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
        truncated = text[:target_chars]

        # Find last newline for clean break
        last_newline = truncated.rfind('\n')
        if last_newline > target_chars // 2:
            truncated = truncated[:last_newline]

        # Re-check token count and further trim if necessary
        while self.estimate_tokens(truncated) > max_tokens and len(truncated) > 0:
            # Trim by 10% of current length or at least 100 characters
            trim_amount = max(100, len(truncated) // 10)
            truncated = truncated[:-trim_amount]
            # Try to find a natural boundary again
            last_newline = truncated.rfind('\n')
            if last_newline > len(truncated) // 2:
                truncated = truncated[:last_newline]

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
