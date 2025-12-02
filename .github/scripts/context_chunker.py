        self.config: Dict = {}

        # Load configuration if available
        cfg_file = Path(config_path)
        if cfg_file.exists():
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
        self.summarization_threshold: int = int(agent_cfg.get("summarization_threshold", int(self.max_tokens * 0.9)))

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
                # Use a common 32k context model encoding if available; fallback to cl100k_base
                self._encoder = tiktoken.get_encoding("cl100k_base")
            except Exception as e:
                print(f"Warning: failed to initialize tiktoken encoder: {e}", file=sys.stderr)
                self._encoder = None

        # Precompiled regexes or any other helpers
        processed_content = self._build_limited_content(chunks)
        return processed_content, True


    def _build_limited_content(self, chunks):
        """
        Build limited content from chunks (placeholder implementation).

        Parameters:
    def _build_limited_content(self, chunks):
        """
        Build limited content from chunks (placeholder implementation).

        Parameters:
def _build_limited_content(self, chunks):
        """
        Build a token-limited string from prioritized content chunks.

        Args:
            chunks: A collection of dictionaries. Each dict should have:
                - "type": (str) Used for prioritization via `self.priority_map`.
                - "content": (str) The text content to include.

        Returns:
            str: A concatenated string of chunk contents, separated by double newlines,
                 respecting `self.max_tokens` total limit and `self.chunk_size` per-chunk limit.
                 Chunks are processed in priority order (unknown types last).
                 Token estimation uses `self._encoder` if available, else a 4-char heuristic.
        """

        Returns:
            A prioritized, size-limited string assembled from provided chunks.
        """
        # Build limited content by prioritizing chunks and enforcing token limits

        Returns:
        # Build limited content by prioritizing chunks and enforcing token limits
        # Expect each chunk to be a dict with keys: "type" and "content"
        def estimate_tokens(text: str) -> int:
            if self._encoder:
                try:
                    return len(self._encoder.encode(text))
                except Exception as e:
                    import warnings
                    warnings.warn(f"Token encoder failed: {e}. Using fallback estimation.", stacklevel=2)
            # Fallback heuristic: ~4 chars per token
            return max(1, len(text) // 4)

        # Sort chunks by configured priority (unknown types come last)
        def priority_key(ch):
            if not isinstance(ch, dict):
                return len(self.priority_map)  # Treat as lowest priority
            ch_type = ch.get("type", "")
            return self.priority_map.get(ch_type, len(self.priority_map))

        filtered_chunks = [ch for ch in (chunks or []) if ch is not None]
        sorted_chunks = sorted(filtered_chunks, key=priority_key)

        pieces = []
        used_tokens = 0
        limit = self.max_tokens

        for ch in sorted_chunks:
            content = (ch or {}).get("content") or ""
        # Normalize and validate input: ensure iterable of dicts
        try:
            iterable_chunks = list(chunks or [])
        except TypeError:
            iterable_chunks = []
        filtered_chunks = [ch for ch in iterable_chunks if isinstance(ch, dict)]
        sorted_chunks = sorted(filtered_chunks, key=priority_key)

        def main():
            """Example usage"""
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
