"""Context chunking utilities for processing PR payloads.

Provides the ContextChunker class for extracting and managing context from
pull request payloads while respecting token limits.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml as _yaml

    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

try:
    import tiktoken as _tiktoken

    _TIKTOKEN_AVAILABLE = True
except ImportError:
    _TIKTOKEN_AVAILABLE = False

_DEFAULT_MAX_TOKENS = 32000
_DEFAULT_OVERLAP_TOKENS = 2000
_DEFAULT_SUMMARIZATION_THRESHOLD = 30000
_DEFAULT_PRIORITY_ORDER: list[str] = [
    "review_comments",
    "test_failures",
    "changed_files",
    "pr_description",
    "commit_messages",
]

# Config file is expected alongside other GitHub config files.
_CONFIG_PATH = Path(__file__).parent.parent / "pr-agent-config.yml"


class ContextChunker:
    """Chunks context from PR payloads while respecting token limits.

    Reads optional YAML configuration to set token limits and priority order.
    Falls back to sensible defaults when the config file is absent or unreadable.
    """

    def __init__(self) -> None:
        self.config: dict[str, Any] = {}
        self._encoder: Any = None

        # Attempt to load config from the YAML file.
        if _CONFIG_PATH.exists():
            try:
                with open(_CONFIG_PATH, encoding="utf-8") as fh:
                    if _YAML_AVAILABLE:
                        try:
                            loaded = _yaml.safe_load(fh)
                            self.config = loaded if isinstance(loaded, dict) else {}
                        except _yaml.YAMLError:
                            self.config = {}
            except (IOError, OSError):
                self.config = {}

        agent_context: dict[str, Any] = self.config.get("agent", {}).get("context", {}) or {}
        limits_fallback: dict[str, Any] = self.config.get("limits", {}).get("fallback", {}) or {}

        self.max_tokens: int = agent_context.get("max_tokens", _DEFAULT_MAX_TOKENS)
        self.chunk_size: int = agent_context.get("chunk_size", max(1, self.max_tokens - 4000))
        self.overlap_tokens: int = agent_context.get("overlap_tokens", _DEFAULT_OVERLAP_TOKENS)
        self.summarization_threshold: int = agent_context.get(
            "summarization_threshold", _DEFAULT_SUMMARIZATION_THRESHOLD
        )
        self.priority_order: list[str] = limits_fallback.get("priority_order", list(_DEFAULT_PRIORITY_ORDER))
        self.priority_map: dict[str, int] = {name: i for i, name in enumerate(self.priority_order)}

        # Try to set up a tiktoken encoder for accurate token counting.
        if _TIKTOKEN_AVAILABLE:
            try:
                self._encoder = _tiktoken.get_encoding("cl100k_base")
            except Exception:
                self._encoder = None

    def process_context(self, payload: dict[str, Any]) -> tuple[str, bool]:
        """Extract and combine text content from a PR payload.

        Args:
            payload: Dictionary that may contain ``reviews`` and/or ``files`` lists.

        Returns:
            A ``(text, has_content)`` tuple.  ``has_content`` is ``True`` when
            at least one non-empty content item was found.
        """
        parts: list[str] = []

        reviews = payload.get("reviews")
        if isinstance(reviews, list):
            for item in reviews:
                if isinstance(item, dict):
                    body = item.get("body")
                    if body and isinstance(body, str) and body.strip():
                        parts.append(body)

        files = payload.get("files")
        if isinstance(files, list):
            for item in files:
                if isinstance(item, dict):
                    patch = item.get("patch")
                    if patch and isinstance(patch, str) and patch.strip():
                        parts.append(patch)

        if not parts:
            return "", False

        text = "\n\n".join(parts).strip()
        return text, bool(text)

    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in *text*.

        Uses a tiktoken encoder when available; falls back to word count.

        Args:
            text: The text to tokenize.

        Returns:
            Estimated token count (>= 0).
        """
        if not text:
            return 0

        if self._encoder is not None:
            try:
                return len(self._encoder.encode(text))
            except Exception:
                pass

        # Fallback: approximate by splitting on whitespace.
        return len(text.split())
