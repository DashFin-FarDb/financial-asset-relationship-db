#!/usr/bin/env python3
"""
Context Chunker for PR Agent

This module provides intelligent context chunking to handle large PRs
without hitting token limits. It reads PR context from stdin and outputs
processed/chunked content to stdout.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


class ContextChunker:
    """Handles chunking of PR context to fit within token limits."""


    def __init__(self, config_path: str = ".github/pr-agent-config.yml") -> None:
        """Initialize the context chunker with configuration."""
        self.config: Dict[str, Any] = {}

        # Load configuration if available
        cfg_file = Path(config_path)
        if cfg_file.exists() and YAML_AVAILABLE:
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

    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken or estimate."""
        if self._encoder:
            return len(self._encoder.encode(text))
        # Fallback: rough estimate of 4 chars per token
        return len(text) // 4

    def process_context(self, pr_data: Dict[str, Any]) -> Tuple[str, bool]:
        """
        Process PR context data and return chunked content.

        Args:
            pr_data: Dictionary containing PR information (reviews, files, etc.)

        Returns:
            Tuple of (processed_content, was_truncated)
        """
        processed_content, was_truncated = self._build_limited_content(pr_data)
        return processed_content, was_truncated

    def _build_limited_content(self, pr_data: Dict[str, Any]) -> Tuple[str, bool]:
        """Build size-limited content from PR data based on priority.

        Returns:
            Tuple of (content_string, was_truncated)
        """
        sections: List[Tuple[int, str, str]] = []  # (priority, name, content)
        was_truncated = False

        # Extract reviews
        reviews = pr_data.get("reviews", [])
        if reviews:
            review_text = self._format_reviews(reviews)
            sections.append((self.priority_map.get("review_comments", 0), "reviews", review_text))

        # Extract check runs (test failures)
        check_runs = pr_data.get("check_runs", [])
        if check_runs:
            checks_text = self._format_check_runs(check_runs)
            sections.append((self.priority_map.get("test_failures", 1), "check_runs", checks_text))

        # Extract files
        files = pr_data.get("files", [])
        if files:
            files_text = self._format_files(files)
            sections.append((self.priority_map.get("changed_files", 2), "files", files_text))

        # Sort by priority and build content
        sections.sort(key=lambda x: x[0])

        result_parts: List[str] = []
        total_tokens = 0

        for _, name, content in sections:
            content_tokens = self.count_tokens(content)
            if total_tokens + content_tokens <= self.max_tokens:
                result_parts.append(f"## {name.replace('_', ' ').title()}\n{content}")
                total_tokens += content_tokens
            else:
                # Truncate content to fit
                remaining_tokens = self.max_tokens - total_tokens
                if remaining_tokens > 100:
                    truncated = self._truncate_to_tokens(content, remaining_tokens - 50)
                    # Ensure we end at a logical boundary (end of line) to avoid malformed markdown
                    if "\n" in truncated:
                        truncated = truncated.rsplit("\n", 1)[0]
                    truncated += "\n\n[... truncated due to context size limits ...]"
                    truncated_section = f"## {name.replace('_', ' ').title()} (truncated)\n{truncated}"
                    result_parts.append(truncated_section)
                    total_tokens += self.count_tokens(truncated_section)
                    was_truncated = True
                was_truncated = True
                break

        content = "\n\n".join(result_parts) if result_parts else json.dumps(pr_data, indent=2)
        return content, was_truncated

    def _format_reviews(self, reviews: List[Dict[str, Any]]) -> str:
        """Format review comments."""
        lines: List[str] = []
        for review in reviews:
            user_data = review.get("user", {})
            if isinstance(user_data, dict):
                user = user_data.get("login", "unknown")
            else:
                user = str(user_data) if user_data else "unknown"
            state = review.get("state", "unknown")
            body = review.get("body", "")
            lines.append(f"- **{user}** ({state}): {(body or '(no comment)')[:500]}")
        return "\n".join(lines)

    def _format_check_runs(self, check_runs: List[Dict[str, Any]]) -> str:
        """Format check run results."""
        lines: List[str] = []
        for check in check_runs:
            name = check.get("name", "unknown")
            conclusion = check.get("conclusion", "unknown")
            output = check.get("output", {})
            summary = output.get("summary", "") if isinstance(output, dict) else ""
            lines.append(f"- **{name}**: {conclusion}")
            if summary:
                lines.append(f"  {summary[:200]}")
        return "\n".join(lines)

    def _format_files(self, files: List[Dict[str, Any]]) -> str:
        """Format changed files."""
        lines: List[str] = []
        for f in files:
            filename = f.get("filename", "unknown")
            additions = f.get("additions", 0)
            deletions = f.get("deletions", 0)
            lines.append(f"- `{filename}` (+{additions}/-{deletions})")
        return "\n".join(lines)

    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to approximately max_tokens."""
        if self._encoder:
            tokens = self._encoder.encode(text)
            if len(tokens) <= max_tokens:
                return text
            truncated_tokens = tokens[:max_tokens]
            return self._encoder.decode(truncated_tokens) + "..."
        # Fallback: estimate 4 chars per token
        max_chars = max_tokens * 4
        if len(text) <= max_chars:
            return text
        snippet = text[:max_chars]
        if len(text) > max_chars:
            # Prefer truncation at a word boundary if possible
            cut = snippet.rsplit(" ", 1)[0]
            # If no space found (single long token), fall back to hard cut
            safe = cut if cut else snippet
            return safe.rstrip() + "..."
        return text


def main() -> None:
    """Main entry point - reads from stdin, writes to stdout."""
    chunker = ContextChunker()

    try:
        # Read JSON from stdin
        input_data = sys.stdin.read()
        if not input_data.strip():
            print(json.dumps({}), file=sys.stdout)
            return

        pr_data = json.loads(input_data)
        processed, was_truncated = chunker.process_context(pr_data)

        # Output processed content as JSON
        output = {
            "content": processed,
            "was_truncated": was_truncated,
            "original_keys": list(pr_data.keys()) if isinstance(pr_data, dict) else [],
        }
        print(json.dumps(output, indent=2), file=sys.stdout)

    except json.JSONDecodeError as e:
        print(f"Error parsing JSON input: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error processing context: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
