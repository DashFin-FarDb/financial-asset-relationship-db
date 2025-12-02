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
            chunks: Collection of content chunks to process.

        Returns:
            def _build_limited_content(self, chunks):
                """
                Build limited content from chunks by concatenating their content in priority order
                while respecting the configured chunk/token size limits.

                Parameters:
                    chunks: Iterable of dict-like chunk items with at least:
                            - 'type': str (e.g., 'review_comments', 'test_failures', etc.)
                            - 'content': str
                            Optional: 'metadata': dict

                Returns:
                    str: Concatenated content limited by configured size.
                """
                if not chunks:
                    return ""

                # Helper to compute token length if encoder is available, else fallback to len()
                def _length(text: str) -> int:
                    """
                    Estimate token length. Uses tiktoken if available; otherwise falls back to a heuristic
                    that approximates tokenization by splitting on word characters, punctuation, and whitespace.
                    Note: This is an approximation and may slightly over/under count.
                    """
                    if getattr(self, "_encoder", None) is not None:
                        try:
                            return len(self._encoder.encode(text))
                        except Exception:
                            pass
                    # Heuristic fallback: approximate tokens by regex-based segmentation
                    # This more closely matches token boundaries than len(text), especially for non-ASCII.
                    import re
                    # Split into words, punctuation, and whitespace; collapse contiguous whitespace to a single token.
                    tokens = re.findall(r"\w+|[^\w\s]|(?:\s+)", text, flags=re.UNICODE)
                    # Count collapsed whitespace as single tokens
                    approx_count = 0
                    for tok in tokens:
                        if tok.isspace():
                            approx_count += 1
                        else:
                            approx_count += 1
                    return approx_count

                # Normalize chunks into a list of tuples with priority
                norm_chunks = []
                for ch in chunks:
                    ch_type = (ch or {}).get("type", "unknown")
                    content = (ch or {}).get("content", "")
                    metadata = (ch or {}).get("metadata", {})
                    if not isinstance(content, str):
                        try:
                            content = str(content)
                        except Exception:
                            content = ""
                    priority = self.priority_map.get(ch_type, len(self.priority_map) + 100)
                    norm_chunks.append((priority, ch_type, content, metadata))

                # Sort by priority (lower is higher priority)
                norm_chunks.sort(key=lambda x: x[0])

                # Build output up to the allowed size
                header = "== Context Chunks ==\n"
                output_parts = [header]
                current_len = _length(header)

                limit = max(1, int(self.chunk_size))
                truncated = False

                for _, ch_type, content, metadata in norm_chunks:
                    if not content:
                        continue

                    meta_str = ""
                    if metadata and isinstance(metadata, dict):
                        # Include a small subset of metadata keys if available
                        keys = ["filename", "path", "user", "state", "summary"]
                        kv = []
                        for k in keys:
                            if k in metadata:
                                v = metadata[k]
                                # Make sure value is stringifiable and short
                                v_str = str(v)
                                if len(v_str) > 200:
                                    v_str = v_str[:197] + "..."
                                kv.append(f"{k}={v_str}")
                        if kv:
                            meta_str = f" ({', '.join(kv)})"

                    block_header = f"\n## {ch_type}{meta_str}\n"
                    block_body = content.strip() + "\n"
                    block_text = block_header + block_body

                    blk_len = _length(block_text)
                    if current_len + blk_len <= limit:
                        output_parts.append(block_text)
                        current_len += blk_len
                    else:
                        # Try to add as much of the body as possible after the header
                        remaining = max(0, limit - current_len - _length(block_header))
                        if remaining > 0:
                            # Token-aware truncation if possible
                            if getattr(self, "_encoder", None) is not None:
                                try:
                                    tokens = self._encoder.encode(block_body)
                                    if remaining < len(tokens):
                                        tokens = tokens[:remaining]
                                        decoded = self._encoder.decode(tokens)
                                        truncated_body = decoded if decoded.strip() else block_body[:remaining]
                                    else:
                                        truncated_body = block_body
                                    else:
                                        truncated_body = block_body
                                except Exception:
                                    truncated_body = block_body[:remaining]
                            else:
                                truncated_body = block_body[:remaining]

                            output_parts.append(block_header)
                            output_parts.append(truncated_body.rstrip() + "\n")
                            current_len = limit
                        truncated = True
                        break

                if truncated:
                    output_parts.append("\n...[truncated due to size limits]...\n")

                return "".join(output_parts).rstrip() + "\n"


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

    try:
        processed, chunked = chunker.process_context(example_pr)
    except Exception as e:
        print(f"Error: failed to process context: {e}", file=sys.stderr)
        return
    print(f"Chunked: {chunked}")
    print(f"\nProcessed content:\n{processed}")


if __name__ == "__main__":
    main()
