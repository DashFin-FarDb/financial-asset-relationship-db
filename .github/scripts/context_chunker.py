class ContextChunker:
    def __init__(self, config_path: str = ".github/pr-agent-config.yml"):
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

        def main():
            """
            Demonstrates creating a ContextChunker and processing a sample pull request structure.
            
            This example constructs a ContextChunker, builds a simple pull request payload containing one review and one changed file, invokes process_context on that payload, and prints the chunking metadata and resulting processed content.
            """
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