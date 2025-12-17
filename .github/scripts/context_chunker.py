class ContextChunker:
    def __init__(self, config_path: str = ".github/pr-agent-config.yml"):
        self.config: Dict = {}

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
