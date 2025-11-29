import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

import yaml

try:
    import tiktoken  # type: ignore

    TIKTOKEN_AVAILABLE = True
except Exception:
    TIKTOKEN_AVAILABLE = False


class ContextChunker:
    """
    Manages context chunking for PR (Pull Request) processing.

    Responsibilities:
        - Loads configuration from a YAML file to set chunking and token limits.
        - Handles token management using tiktoken if available.
        - Processes PR content (reviews, files) into text chunks for further analysis.
        - Maintains priority ordering for different context sources.

    Typical workflow:
        1. Instantiate ContextChunker (optionally providing a config path).
        2. Call `process_context(payload)` with a PR payload to extract and chunk relevant text.

    Example:
        chunker = ContextChunker()
        context_text, has_content = chunker.process_context(pr_payload)
    """

    def __init__(self, config_path: str = ".github/pr-agent-config.yml") -> None:
        """
        Initialize a ContextChunker for PR agent context chunking.

        Args:
            config_path (str): Path to the YAML configuration file. Defaults to ".github/pr-agent-config.yml".
                The file should contain configuration sections for 'agent.context' (chunking parameters)
                and 'limits.fallback' (priority order for context elements).

        Loads configuration sections:
            - agent.context: Controls chunking parameters (max_tokens, chunk_size, overlap_tokens, summarization_threshold).
            - limits.fallback: Specifies priority_order for context elements.

        Exceptions:
            - Prints a warning and uses defaults if the config file cannot be loaded or parsed.
            - Prints a warning if tiktoken encoder initialization fails.
        """
        self.config: Dict[str, Any] = {}
        cfg_file = Path(config_path)
        if cfg_file.exists():
            try:
                with cfg_file.open("r", encoding="utf-8") as f:
                    self.config = yaml.safe_load(f) or {}
            except Exception as e:
                print(f"Warning: failed to load config from {config_path}: {e}", file=sys.stderr)
                self.config = {}
        agent_cfg = (self.config.get("agent") or {}).get("context") or {}
        self.max_tokens: int = int(agent_cfg.get("max_tokens", 32000))
        self.chunk_size: int = int(agent_cfg.get("chunk_size", max(1, self.max_tokens - 4000)))
        self.overlap_tokens: int = int(agent_cfg.get("overlap_tokens", 2000))
        self.summarization_threshold: int = int(agent_cfg.get("summarization_threshold", int(self.max_tokens * 0.9)))
        limits_cfg = (self.config.get("limits") or {}).get("fallback") or {}
        self.priority_order: List[str] = limits_cfg.get(
            "priority_order",
            [
                "review_comments",
                "test_failures",
                "changed_files",
                "ci_logs",
                "full_diff",
            ],
        )
        self.priority_map: Dict[str, int] = {name: i for i, name in enumerate(self.priority_order)}
        self._encoder: Optional[Any] = None
        if TIKTOKEN_AVAILABLE:
            try:
                self._encoder = tiktoken.get_encoding("cl100k_base")
            except Exception as e:
                print(f"Warning: failed to initialize tiktoken encoder: {e}", file=sys.stderr)
                self._encoder = None

    def process_context(self, payload: Dict[str, Any]) -> tuple[str, bool]:
        """
        Processes a PR payload dictionary into a single text string.

        Args:
            payload (Dict[str, Any]): Dictionary containing PR context. Expected keys:
                - 'reviews': Optional[List[Dict[str, Any]]] — each dict may have a 'body' key (str).
                - 'files': Optional[List[Dict[str, Any]]] — each dict may have a 'patch' key (str).

        Returns:
            tuple[str, bool]: A tuple containing:
                - The processed text content (str), concatenated from review bodies and file patches.
                - A boolean indicating if any content exists (True if non-empty, False otherwise).

        Example:
            >>> payload = {
            ...     "reviews": [{"body": "Looks good."}, {"body": "Needs changes."}],
            ...     "files": [{"patch": "diff --git ..."}]
            ... }
            >>> chunker = ContextChunker()
            >>> text, has_content = chunker.process_context(payload)
            >>> print(has_content)  # True
        """
        text_parts: List[str] = []
        reviews = payload.get("reviews")
        if not isinstance(reviews, list):
            reviews = []
        files = payload.get("files")
        if not isinstance(files, list):
            files = []
        for r in reviews:
            body = (r or {}).get("body") or ""
            if body:
                text_parts.append(str(body))
        for f in files:
            patch = (f or {}).get("patch") or ""
            if patch:
                text_parts.append(str(patch))
        result = "\n\n".join(text_parts).strip()
        return result, bool(result)

    def count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in the given text.

        Uses the tiktoken encoder if available, otherwise falls back to a simple
        word-based approximation (splitting on whitespace).

        Args:
            text (str): The text to count tokens for.

        Returns:
            int: The estimated number of tokens in the text.

        Example:
            >>> chunker = ContextChunker()
            >>> token_count = chunker.count_tokens("Hello, world!")
            >>> print(token_count)  # Number of tokens
        """
        if not text:
            return 0
        if self._encoder is not None:
            return len(self._encoder.encode(text))
        # Fallback: approximate tokens by splitting on whitespace
        return len(text.split())
