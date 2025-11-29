#!/usr/bin/env python3
"""
Context Chunker for PR Agent
Handles large context by chunking and summarizing content when approaching token limits.
"""

import re
import yaml
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ContextChunk:
    """Represents a chunk of context"""
    content: str
    tokens: int
    priority: int
    chunk_type: str  # review_comments, code_changes, test_failures, ci_logs, full_diff


class ContextChunker:
    """Manages context chunking for PR agent to avoid token limit errors"""
    
    def __init__(self, config_path: str = ".github/pr-agent-config.yml"):
        """Initialize chunker with configuration"""
        self.config = self._load_config(config_path)
        self.max_tokens = self.config.get('agent', {}).get('context', {}).get('max_tokens', 32000)
        self.chunk_size = self.config.get('agent', {}).get('context', {}).get('chunk_size', 28000)
        self.overlap = self.config.get('agent', {}).get('context', {}).get('overlap_tokens', 2000)
        self.summarization_threshold = self.config.get('agent', {}).get('context', {}).get('summarization_threshold', 30000)
        
        # Priority mapping
        priority_order = self.config.get('limits', {}).get('fallback', {}).get('priority_order', [])
        self.priority_map = {item: idx for idx, item in enumerate(priority_order)}
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file"""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Warning: Could not load config from {config_path}: {e}")
            return {}
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        Rough approximation: ~4 characters per token for English text.
        """
        # More accurate estimation considering code structure
        tokens = len(text) / 4
        
        # Add extra tokens for code structure
        code_chars = len(re.findall(r'[{}()\[\];]', text))
        tokens += code_chars * 0.5
        
        return int(tokens)
    
    def extract_content_sections(self, pr_data: Dict) -> Dict[str, str]:
        """Extract different sections from PR data"""
        sections = {}
        
        # Review comments (highest priority)
        if 'reviews' in pr_data:
            comments = []
            for review in pr_data.get('reviews', []):
                if review.get('state') == 'changes_requested':
                    comments.append(f"**{review.get('user', {}).get('login', 'Unknown')}:** {review.get('body', '')}")
            sections['review_comments'] = '\n\n'.join(comments)
        
        # Test failures
        if 'check_runs' in pr_data:
            failures = []
            for check in pr_data.get('check_runs', []):
                if check.get('conclusion') == 'failure':
                    failures.append(f"**{check.get('name')}:** {check.get('output', {}).get('summary', '')}")
            sections['test_failures'] = '\n\n'.join(failures)
        
        # Changed files
        if 'files' in pr_data:
            files_content = []
            for file in pr_data.get('files', []):
                files_content.append(f"**{file.get('filename')}** (+{file.get('additions', 0)} -{file.get('deletions', 0)})")
                if 'patch' in file and file.get('patch'):
                    files_content.append(f"```diff\n{file['patch']}\n```")
            sections['changed_files'] = '\n\n'.join(files_content)
        
        # CI logs (summarized)
        if 'ci_logs' in pr_data:
            sections['ci_logs'] = pr_data['ci_logs']
        
        # Full diff
        if 'diff' in pr_data:
            sections['full_diff'] = pr_data['diff']
        
        return sections
    
    def create_chunks(self, sections: Dict[str, str]) -> List[ContextChunk]:
        """Create prioritized chunks from sections"""
        chunks = []
        
        for section_type, content in sections.items():
            if not content:
                continue
            
            tokens = self.estimate_tokens(content)
            priority = self.priority_map.get(section_type, 999)
            
            # If section is small enough, keep as single chunk
            if tokens <= self.chunk_size:
                chunks.append(ContextChunk(
                    content=content,
                    tokens=tokens,
                    priority=priority,
                    chunk_type=section_type
                ))
            else:
                # Split large sections into multiple chunks
                sub_chunks = self._split_content(content, section_type, priority)
                chunks.extend(sub_chunks)
        
        # Sort by priority
        chunks.sort(key=lambda x: x.priority)
        return chunks
    
    def _split_content(self, content: str, chunk_type: str, priority: int) -> List[ContextChunk]:
        """Split large content into smaller chunks with overlap"""
        chunks = []
        lines = content.split('\n')
        
        current_chunk = []
        current_tokens = 0
        
        for line in lines:
            line_tokens = self.estimate_tokens(line)
            
            if current_tokens + line_tokens > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_content = '\n'.join(current_chunk)
                chunks.append(ContextChunk(
                    content=chunk_content,
                    tokens=current_tokens,
                    priority=priority,
                    chunk_type=chunk_type
                ))
                
                # Start new chunk with overlap
                overlap_lines = self._get_overlap_lines(current_chunk)
                current_chunk = overlap_lines + [line]
                current_tokens = sum(self.estimate_tokens(l) for l in current_chunk)
            else:
                current_chunk.append(line)
                current_tokens += line_tokens
        
        # Add final chunk
        if current_chunk:
            chunk_content = '\n'.join(current_chunk)
            chunks.append(ContextChunk(
                content=chunk_content,
                tokens=current_tokens,
                priority=priority,
                chunk_type=chunk_type
            ))
        
        return chunks
    
    def _get_overlap_lines(self, lines: List[str]) -> List[str]:
        """Get overlap lines for continuity between chunks"""
        overlap_tokens = 0
        overlap_lines = []
        
        # Take last N lines that fit in overlap budget
        for line in reversed(lines):
            line_tokens = self.estimate_tokens(line)
            if overlap_tokens + line_tokens <= self.overlap:
                overlap_lines.insert(0, line)
                overlap_tokens += line_tokens
            else:
                break
        
        return overlap_lines
    
    def summarize_chunk(self, chunk: ContextChunk) -> str:
        """Create a summary of a chunk"""
        # Extract key information
        summary_parts = [f"[{chunk.chunk_type.upper()} SUMMARY]"]
        
        if chunk.chunk_type == "review_comments":
            # Extract action items from comments
            action_items = re.findall(r'(?:fix|add|update|remove|refactor|change)\s+[^\n.!?]{10,100}', 
                                     chunk.content, re.IGNORECASE)
            if action_items:
                summary_parts.append("Action items:")
                summary_parts.extend([f"- {item.strip()}" for item in action_items[:5]])
        
        elif chunk.chunk_type == "changed_files":
            # Extract file names and change counts
            files = re.findall(r'\*\*([^*]+)\*\*\s+\(\+(\d+)\s+-(\d+)\)', chunk.content)
            if files:
                summary_parts.append("Modified files:")
                summary_parts.extend([f"- {f[0]} (+{f[1]} -{f[2]})" for f in files[:10]])
        
        elif chunk.chunk_type == "test_failures":
            # Extract test names and error messages
            failures = re.findall(r'\*\*([^*]+)\*\*:', chunk.content)
            if failures:
                summary_parts.append("Failed tests:")
                summary_parts.extend([f"- {f}" for f in failures[:5]])
        
        summary = '\n'.join(summary_parts)
        
        # Ensure summary is within token limit
        summary_tokens = self.estimate_tokens(summary)
        max_summary = self.config.get('agent', {}).get('context', {}).get('summarization', {}).get('max_summary_tokens', 2000)
        
        if summary_tokens > max_summary:
            # Truncate summary
            target_chars = int(max_summary * 4)  # Rough conversion
            summary = summary[:target_chars] + "\n... (truncated)"
        
        return summary
    
    def process_context(self, pr_data: Dict) -> Tuple[str, bool]:
        """
        Process PR context and return optimized content.
        Returns: (processed_content, was_chunked)
        """
        # Extract sections
        sections = self.extract_content_sections(pr_data)
        
        # Calculate total tokens
        total_tokens = sum(self.estimate_tokens(content) for content in sections.values())
        
        # If under threshold, return as is
        if total_tokens <= self.summarization_threshold:
            full_content = '\n\n---\n\n'.join([
                f"## {section_type.replace('_', ' ').title()}\n\n{content}"
                for section_type, content in sections.items()
            ])
            return full_content, False
        
        # Create chunks
        chunks = self.create_chunks(sections)
        
        # Build context within token limit
        result_parts = []
        current_tokens = 0
        
        for chunk in chunks:
            if current_tokens + chunk.tokens <= self.max_tokens:
                # Include full chunk
                result_parts.append(f"## {chunk.chunk_type.replace('_', ' ').title()}\n\n{chunk.content}")
                current_tokens += chunk.tokens
            elif current_tokens + self.estimate_tokens(self.summarize_chunk(chunk)) <= self.max_tokens:
                # Include summary
                summary = self.summarize_chunk(chunk)
                result_parts.append(summary)
                current_tokens += self.estimate_tokens(summary)
            else:
                # Skip this chunk
                result_parts.append(f"[{chunk.chunk_type.upper()} - Omitted due to context limit]")
        
        processed_content = '\n\n---\n\n'.join(result_parts)
        return processed_content, True


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
