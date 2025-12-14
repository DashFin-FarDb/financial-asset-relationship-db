# PR Agent Context Chunking

## Overview

The PR Agent now includes intelligent context chunking to handle large PRs without hitting token limits. This prevents context overflow errors that can occur when processing PRs with many files, large diffs, or extensive review comments.

## How It Works

### Context Size Monitoring

The workflow automatically monitors the size of PR context data:
- **Threshold**: 100KB of raw PR data (reviews, files, diffs, CI logs)
- **Token Limit**: 32,000 tokens maximum context length
- **Chunking Threshold**: 30,000 tokens triggers summarization

### Chunking Strategy

When context exceeds limits, the system uses a smart chunking approach:

1. **Priority-based Processing**: Content is prioritized by importance
   - **Highest Priority**: Review comments and requested changes
   - **High Priority**: Test failures and CI errors
   - **Medium Priority**: Changed files and code diffs
   - **Low Priority**: Full diff output and CI logs

2. **Smart Chunking**: Large sections are split intelligently
   - Maintains code structure across chunks
   - Includes 2,000 token overlap for continuity
   - Preserves function boundaries and context

3. **Automatic Summarization**: When full content doesn't fit
   - Extracts key action items from reviews
   - Lists modified files with change counts
   - Highlights test failures and error messages
   - Keeps summaries under 2,000 tokens each

### Fallback Strategies

When context still exceeds limits after chunking:
- **chunk_and_summarize**: Default strategy - chunk content and summarize overflows
- **summarize_only**: Summarize all content aggressively
- **prioritize**: Only include highest priority items
- **fail**: Report error and require manual intervention

## Configuration

Configure chunking behavior in `.github/pr-agent-config.yml`:

```yaml
agent:
  context:
    max_tokens: 32000              # Maximum context length
    chunk_size: 28000              # Size of each chunk
    overlap_tokens: 2000           # Overlap between chunks
    summarization_threshold: 30000 # When to start summarizing

    chunking:
      enabled: true
      strategy: "smart"            # smart, sequential, or priority
      preserve_structure: true     # Maintain code structure

    summarization:
      enabled: true
      model: "gpt-3.5-turbo"      # Model for summaries
      max_summary_tokens: 2000     # Max tokens per summary
```

## Usage

### Automatic Operation

The chunking system works automatically:
1. PR opened or review submitted
2. Workflow fetches PR context data
3. Context size checked against threshold
4. If large: chunking applied automatically
5. Processed context used for PR analysis

### Monitoring

Check workflow output to see chunking status:
- ✅ **No chunking needed**: Context under threshold
- 🔄 **Context chunking applied**: Large context was chunked
- 📊 **Context size**: Shows actual size in bytes

### Manual Testing

Test the chunker locally:

```bash
# Install dependencies
pip install pyyaml tiktoken

# Test with example data (uses built-in example)
python .github/scripts/context_chunker.py

# Process real PR data
gh api repos/OWNER/REPO/pulls/123 | python .github/scripts/context_chunker.py

# Test without tiktoken (heuristic mode)
pip uninstall -y tiktoken
python .github/scripts/context_chunker.py
```

**Note**: The script will automatically detect if `tiktoken` is available and use the appropriate estimation method.

## Benefits

### Prevents Errors
- No more "context length exceeded" failures
- Handles PRs of any size
- Graceful degradation when limits approached

### Maintains Quality
- Prioritizes important information
- Preserves code structure and context
- Includes all critical review feedback

### Improves Performance
- Faster processing of large PRs
- Reduced token usage via summarization
- Efficient use of API rate limits

## Architecture

```
PR Context Flow:

1. Fetch PR Data
   ├─ Reviews & Comments
   ├─ Changed Files & Diffs
   ├─ CI Check Results
   └─ Test Failures

2. Estimate Context Size
   ├─ Calculate token count
   └─ Compare to threshold

3. Apply Chunking (if needed)
   ├─ Split by priority
   ├─ Maintain overlap
   └─ Preserve structure

4. Generate Summaries (if needed)
   ├─ Extract action items
   ├─ List key changes
   └─ Highlight failures

5. Process with PR Agent
   └─ Use optimized context
```

## Token Estimation

The chunker uses two methods for token estimation:

### 1. Accurate Estimation (Recommended)

When `tiktoken` is available, the chunker uses OpenAI's tokenizer for precise token counting:
```python
import tiktoken
enc = tiktoken.get_encoding('cl100k_base')  # GPT-4, GPT-3.5-turbo
tokens = len(enc.encode(text))
```

**Installation**:
```bash
pip install tiktoken
```

### 2. Heuristic Fallback

When `tiktoken` is not available, uses intelligent heuristics:
- **Base Rate**: ~4 characters per token (English text)
- **Code Adjustment**: +0.5 tokens per structural character `{}()[];`
- **Whitespace Adjustment**: +0.25 tokens per whitespace sequence
- **Formatting Adjustment**: +0.3 tokens per markdown character `*_`#-`
- **Safety Margin**: +10% buffer to prevent overruns

The heuristic provides reasonable estimates but may be less accurate for:
- Non-English text
- Code-heavy content
- Complex Unicode characters

**Recommendation**: Install `tiktoken` for production use to ensure accurate context management.

## Troubleshooting

### Context Still Too Large

If chunking isn't sufficient:

1. **Increase Priority Filtering**: Edit `.github/pr-agent-config.yml`:
   ```yaml
   limits:
     max_files_per_chunk: 5        # Reduce from 10
     max_diff_lines: 2500           # Reduce from 5000
   ```

2. **Aggressive Summarization**: Change fallback strategy:
   ```yaml
   limits:
     fallback:
       on_context_overflow: "summarize_only"
   ```

3. **Manual Review**: For extremely large PRs (>1000 files), consider:
   - Breaking PR into smaller chunks
   - Using manual review instead of automated processing

### Chunking Not Triggered

If chunking should activate but doesn't:

1. Check workflow logs for context size
2. Verify threshold in config: `max_tokens: 32000`
3. Ensure dependencies installed: workflow includes `pip install pyyaml tiktoken`
4. Check token estimation accuracy:
   - With tiktoken: More accurate, may trigger earlier
   - Without tiktoken: Heuristic, may underestimate slightly

### Test Failures After Chunking

If tests fail after implementing chunking:

1. Verify context integrity with:
   ```bash
   python .github/scripts/context_chunker.py < test_pr.json
   ```

2. Check that important context isn't lost:
   - Review comments preserved?
   - File names intact?
   - Error messages included?

## Recent Improvements

### Version 1.1.0

**Accurate Token Estimation**:
- ✅ Integrated `tiktoken` for precise token counting (GPT-4/3.5-turbo compatible)
- ✅ Automatic fallback to improved heuristic when tiktoken unavailable
- ✅ Enhanced heuristic with whitespace and formatting adjustments
- ✅ 10% safety margin for heuristic mode

**Robust Error Handling**:
- ✅ Comprehensive configuration validation
- ✅ Default configuration fallback when file missing/invalid
- ✅ Graceful degradation on config errors
- ✅ Detailed error messages to stderr
- ✅ Safe defaults for all critical settings

## Future Enhancements

Potential improvements for the chunking system:

- [ ] Semantic chunking using AST parsing
- [ ] LLM-based intelligent summarization
- [ ] Caching of chunked context for repeated access
- [ ] Progressive loading of chunks as needed
- [ ] Automatic chunk size optimization based on usage patterns
- [ ] Multi-model token estimation (Claude, Llama, etc.)

## References

- Configuration: `.github/pr-agent-config.yml`
- Workflow: `.github/workflows/pr-agent.yml`
- Implementation: `.github/scripts/context_chunker.py`
- Documentation: `.github/copilot-pr-agent.md`
