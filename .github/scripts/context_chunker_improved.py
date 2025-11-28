#!/usr/bin/env python3
"""
Context Chunker for PR Agent

This module provides intelligent context chunking to handle large PRs
without hitting token limits. It reads PR context from stdin and outputs
processed/chunked content to stdout.

Improved version with better error handling, performance optimizations,
and maintainability enhancements.
"""

import json
import logging
import sys
from dataclasses import dataclass
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
    logging.getLogger(__name__).warning(
        "tiktoken is not available. Token counting will fall back to estimation. "
        "Install tiktoken for more accurate token counting."
    )


logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    """Configure module logging when the script is run directly.

    This avoids overriding an application's logging configuration when the
    module is imported. If logging handlers are already present, do nothing.
    """
    # Avoid overriding application-level logging configuration
    if logger.hasHandlers():
        return

    handler = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)


@dataclass
class ChunkingConfig:
    """Configuration for context chunking."""
    max_tokens: int = 32000
    chunk_size: int = 28000  # Default chunk size with buffer
    min_chunk_size: int = 100
    truncation_threshold: int = 100
    encoding_name: str = "cl100k_base"
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'ChunkingConfig':
        """Create config from dictionary with validation."""
        agent_cfg = config_dict.get("agent", {}).get("context", {})
        limits_cfg = config_dict.get("limits", {}).get("fallback", {})
        
        max_tokens = int(agent_cfg.get("max_tokens", 32000))
        chunk_size = int(agent_cfg.get("chunk_size", max(1000, max_tokens - 4000)))
        
        return cls(
            max_tokens=max_tokens,
            chunk_size=chunk_size,
            min_chunk_size=int(limits_cfg.get("min_chunk_size", 100)),
            truncation_threshold=int(limits_cfg.get("truncation_threshold", 100)),
            encoding_name=limits_cfg.get("encoding", "cl100k_base")
        )


@dataclass 
class PriorityMapping:
    """Maps chunk types to priority indices."""
    order: List[str]
    map_dict: Dict[str, int]
    
    @classmethod
    def from_config(cls, config_dict: Dict[str, Any]) -> 'PriorityMapping':
        """Create priority mapping from config."""
        limits_cfg = config_dict.get("limits", {}).get("fallback", {})
        default_order = [
            "review_comments",
            "test_failures",
            "changed_files",
            "ci_logs",
            "full_diff",
        ]
        order = limits_cfg.get("priority_order", default_order)
        map_dict = {name: i for i, name in enumerate(order)}
        return cls(order=order, map_dict=map_dict)


@dataclass
class ProcessingResult:
    """Result of context processing."""
    content: str
    was_truncated: bool
    original_keys: List[str]
    token_count: int
    chunk_count: int


class TokenCounter:
    """Handles token counting with fallback mechanisms."""
    
    def __init__(self, encoding_name: str = "cl100k_base"):
        self._encoder = None
        self._encoding_name = encoding_name
        self._initialize_encoder()
    
    def _initialize_encoder(self) -> None:
        """Initialize tokenizer with error handling."""
        if not TIKTOKEN_AVAILABLE:
            logger.warning("tiktoken not available, using character-based estimation")
            return
            
        try:
            self._encoder = tiktoken.get_encoding(self._encoding_name)
            logger.info(f"Successfully initialized tokenizer: {self._encoding_name}")
        except Exception as e:
            logger.warning(f"Failed to initialize tiktoken encoder: {e}")
            self._encoder = None
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        if not isinstance(text, str):
            logger.warning(f"Expected string, got {type(text).__name__}")
            return 0
            
        if self._encoder:
            try:
                return len(self._encoder.encode(text))
            except Exception as e:
                logger.warning(f"Token counting failed, using estimation: {e}")
        
        # Fallback: estimate 4 chars per token (approximate)
        return max(0, len(text) // 4)
    
    def truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to approximately max_tokens."""
        if not isinstance(text, str) or not text:
            return ""
        
        if self._encoder:
            try:
                tokens = self._encoder.encode(text)
                if len(tokens) <= max_tokens:
                    return text
                truncated_tokens = tokens[:max_tokens]
                return f"{self._encoder.decode(truncated_tokens)}..."
            except Exception as e:
                logger.warning(f"Token truncation failed, using character-based: {e}")
        
        # Fallback: character-based truncation
        max_chars = max_tokens * 4
        if len(text) <= max_chars:
            return text
        return f"{text[:max_chars]}..."


class ContextChunker:
    """Handles chunking of PR context to fit within token limits."""
    
    def __init__(self, config_path: str = ".github/pr-agent-config.yml"):
        """Initialize the context chunker with configuration."""
        self.config_path = config_path
        self.config = self._load_configuration()
        
        # Initialize components
        self.chunking_config = ChunkingConfig.from_dict(self.config)
        self.priority_mapping = PriorityMapping.from_config(self.config)
        self.token_counter = TokenCounter(self.chunking_config.encoding_name)
        
        logger.info(f"ContextChunker initialized with max_tokens={self.chunking_config.max_tokens}")
    
    def _load_configuration(self) -> Dict[str, Any]:
        """Load and validate configuration file."""
        config_file = Path(self.config_path)
        if not config_file.exists():
            logger.info(f"Config file {self.config_path} not found, using defaults")
            return {}
        
        if not YAML_AVAILABLE:
            logger.warning("PyYAML not available, using defaults")
            return {}
        
        try:
            with config_file.open("r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            logger.info(f"Successfully loaded configuration from {self.config_path}")
            return config
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in {self.config_path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            return {}
    
    def _validate_pr_data(self, pr_data: Any) -> Dict[str, Any]:
        """Validate and sanitize PR data input."""
        if not isinstance(pr_data, dict):
            logger.error(f"Expected dict, got {type(pr_data).__name__}")
            return {}
        
        # Ensure all expected keys exist
        validated_data = {
            "reviews": pr_data.get("reviews", []),
            "check_runs": pr_data.get("check_runs", []), 
            "files": pr_data.get("files", []),
            "ci_logs": pr_data.get("ci_logs", ""),
            "full_diff": pr_data.get("full_diff", "")
        }
        
        return validated_data
    
    def _format_reviews(self, reviews: List[Dict[str, Any]]) -> str:
        """Format review comments with enhanced error handling."""
        if not isinstance(reviews, list):
            logger.warning("Reviews should be a list")
            return ""
        
        lines: List[str] = []
        for i, review in enumerate(reviews):
            try:
                if not isinstance(review, dict):
                    logger.warning(f"Review {i} is not a dict, skipping")
                    continue
                
                user_data = review.get("user", {})
                if isinstance(user_data, dict):
                    user = user_data.get("login", "unknown")
                else:
                    user = str(user_data) if user_data else "unknown"
                
                state = review.get("state", "unknown")
                body = review.get("body", "")
                
                if isinstance(body, str) and len(body) > 500:
                    body = f"{body[:497]}..."
                
                lines.append(f"- **{user}** ({state}): {body}")
            except Exception as e:
                logger.warning(f"Failed to format review {i}: {e}")
                continue
        
        return "\n".join(lines)
    
    def _format_check_runs(self, check_runs: List[Dict[str, Any]]) -> str:
        """Format check run results with enhanced error handling."""
        if not isinstance(check_runs, list):
            logger.warning("Check runs should be a list")
            return ""
        
        lines: List[str] = []
        for i, check in enumerate(check_runs):
            try:
                if not isinstance(check, dict):
                    logger.warning(f"Check run {i} is not a dict, skipping")
                    continue
                
                name = check.get("name", "unknown")
                conclusion = check.get("conclusion", "unknown")
                output = check.get("output", {})
                
                lines.append(f"- **{name}**: {conclusion}")
                
                if isinstance(output, dict):
                    summary = output.get("summary", "")
                    if summary and isinstance(summary, str) and len(summary) > 200:
                        summary = f"{summary[:197]}..."
                    if summary:
                        lines.append(f"  {summary}")
            except Exception as e:
                logger.warning(f"Failed to format check run {i}: {e}")
                continue
        
        return "\n".join(lines)
    
    def _format_files(self, files: List[Dict[str, Any]]) -> str:
        """Format changed files with enhanced error handling."""
        if not isinstance(files, list):
            logger.warning("Files should be a list")
            return ""
        
        lines: List[str] = []
        for i, f in enumerate(files):
            try:
                if not isinstance(f, dict):
                    logger.warning(f"File {i} is not a dict, skipping")
                    continue
                
                filename = f.get("filename", "unknown")
                additions = int(f.get("additions", 0))
                deletions = int(f.get("deletions", 0))
                
                lines.append(f"- `{filename}` (+{additions}/-{deletions})")
            except Exception as e:
                logger.warning(f"Failed to format file {i}: {e}")
                continue
        
        return "\n".join(lines)
    
    def _build_sections(self, pr_data: Dict[str, Any]) -> List[Tuple[int, str, str]]:
        """Build prioritized sections from PR data."""
        sections: List[Tuple[int, str, str]] = []
        
        # Extract and format reviews
        reviews = pr_data.get("reviews", [])
        if reviews:
            review_text = self._format_reviews(reviews)
            if review_text:
                priority = self.priority_mapping.map_dict.get("review_comments", 0)
                sections.append((priority, "reviews", review_text))
        
        # Extract and format check runs
        check_runs = pr_data.get("check_runs", [])
        if check_runs:
            checks_text = self._format_check_runs(check_runs)
            if checks_text:
                priority = self.priority_mapping.map_dict.get("test_failures", 1)
                sections.append((priority, "check_runs", checks_text))
        
        # Extract and format files
        files = pr_data.get("files", [])
        if files:
            files_text = self._format_files(files)
            if files_text:
                priority = self.priority_mapping.map_dict.get("changed_files", 2)
                sections.append((priority, "files", files_text))
        
        # Sort by priority (lower index = higher priority)
        sections.sort(key=lambda x: x[0])
        
        return sections
    
    def _build_limited_content(self, pr_data: Dict[str, Any]) -> Tuple[str, bool]:
        """Build size-limited content from PR data based on priority."""
        sections = self._build_sections(pr_data)
        was_truncated = False
        
        result_parts: List[str] = []
        total_tokens = 0
        
        for _, name, content in sections:
            content_tokens = self.token_counter.count_tokens(content)
            
            if total_tokens + content_tokens <= self.chunking_config.max_tokens:
                # Content fits completely
                result_parts.append(f"## {name.replace('_', ' ').title()}\n{content}")
                total_tokens += content_tokens
            else:
                # Need to truncate or skip this section
                remaining_tokens = self.chunking_config.max_tokens - total_tokens
                
                if remaining_tokens > self.chunking_config.truncation_threshold:
                    # Truncate content to fit
                    available_for_content = remaining_tokens - 50  # Reserve for truncation message
                    truncated = self.token_counter.truncate_to_tokens(content, available_for_content)
                    
                    # Ensure we end at a logical boundary
                    if "\n" in truncated:
                        truncated = truncated.rsplit("\n", 1)[0]
                    
                    truncated += "\n\n[... truncated due to context size limits ...]"
                    result_parts.append(f"## {name.replace('_', ' ').title()} (truncated)\n{truncated}")
                    was_truncated = True
                
                break  # Stop processing additional sections
        
        # Return original data as fallback if no sections were processed
        if not result_parts:
            logger.warning("No sections could be processed, returning original data")
            return json.dumps(pr_data, indent=2), False
        
        return "\n\n".join(result_parts), was_truncated
    
    def process_context(self, pr_data: Dict[str, Any]) -> ProcessingResult:
        """
        Process PR context data and return chunked content.
        
        Args:
            pr_data: Dictionary containing PR information
            
        Returns:
            ProcessingResult with processed content and metadata
        """
        # Validate input
        validated_data = self._validate_pr_data(pr_data)
        if not validated_data:
            logger.error("Invalid PR data provided")
            return ProcessingResult(
                content="",
                was_truncated=False,
                original_keys=[],
                token_count=0,
                chunk_count=0
            )
        
        # Process content
        content, was_truncated = self._build_limited_content(validated_data)
        
        # Calculate metadata
        token_count = self.token_counter.count_tokens(content)
        chunk_count = 1 if content else 0
        
        logger.info(
            f"Processed {len(validated_data)} sections, "
            f"token count: {token_count}, truncated: {was_truncated}"
        )
        
        return ProcessingResult(
            content=content,
            was_truncated=was_truncated,
            original_keys=list(pr_data.keys()),
            token_count=token_count,
            chunk_count=chunk_count
        )


def main() -> None:
    """Main entry point - reads from stdin, writes to stdout."""
    try:
        _configure_logging()
        chunker = ContextChunker()
        
        # Read and validate input
        input_data = sys.stdin.read()
        if not input_data.strip():
            logger.info("Empty input provided")
            print(json.dumps({"content": "", "chunked": False, "original_keys": []}), 
                  file=sys.stdout)
            return
        
        # Parse JSON with enhanced error handling
        try:
            pr_data = json.loads(input_data)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            print(json.dumps({"error": f"Invalid JSON: {e}"}), file=sys.stderr)
            sys.exit(1)
        
        # Process the data
        result = chunker.process_context(pr_data)
        
        # Output results
        output = {
            "content": result.content,
            "chunked": result.was_truncated,
            "original_keys": result.original_keys,
            "token_count": result.token_count,
            "chunk_count": result.chunk_count
        }
        
        print(json.dumps(output, indent=2), file=sys.stdout)
        
    except KeyboardInterrupt:
        logger.info("Processing interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(json.dumps({"error": f"Processing failed: {e}"}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()