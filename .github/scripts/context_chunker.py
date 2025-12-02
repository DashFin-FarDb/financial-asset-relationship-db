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
            chunks: Collection of content chunks to process.

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
                except Exception:
                    pass
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
        limit = max(1, int(self.max_tokens))  # safety

        for ch in sorted_chunks:
            content = (ch or {}).get("content") or ""
            if not content:
                continue
            # If content exceeds chunk_size, take a head segment with optional overlap
            max_len_tokens = max(1, int(self.chunk_size))
            content_tokens = estimate_tokens(content)
            if content_tokens > max_len_tokens:
                # approximate slicing by character proportion
                ratio = max_len_tokens / max(content_tokens, 1)
                take_chars = max(1, int(len(content) * ratio))
                # apply overlap at end to help continuity
                overlap_est = max(0, int(self.overlap_tokens))
                overlap_ratio = overlap_est / max(content_tokens, 1)
                overlap_chars = max(0, int(len(content) * overlap_ratio))
                slice_end = min(len(content), take_chars + overlap_chars)
                content = content[:slice_end]
                content_tokens = estimate_tokens(content)

            # Ensure we don't exceed the overall token limit
            if used_tokens + content_tokens > limit:
                # take a remaining slice proportionally
                remaining = max(0, limit - used_tokens)
                if remaining <= 0:
                    break
                ratio = remaining / max(content_tokens, 1)
                take_chars = max(1, int(len(content) * ratio))
                content = content[:take_chars]
                content_tokens = estimate_tokens(content)

                # Final check to ensure we don't exceed the limit due to approximation
                if content_tokens > remaining:
                    ratio = (remaining / max(content_tokens, 1)) * 0.95 # 5% safety margin
                    take_chars = max(1, int(len(content) * ratio))
                    content = content[:take_chars]
                    content_tokens = estimate_tokens(content)

            if content:
                pieces.append(content)
                used_tokens += content_tokens
                if used_tokens >= limit:
                    break

        return "\n\n".join(pieces)

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
