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
    def __init__(self, config_path: str = ".github/pr-agent-config.yml") -> None:
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
        self.priority_order: List[str] = limits_cfg.get("priority_order", [
            "review_comments",
            "test_failures",
            "changed_files",
            "ci_logs",
            "full_diff",
        ])
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
            Tuple[str, bool]: A tuple containing:
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
        reviews = payload.get("reviews") or []
        files = payload.get("files") or []
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
