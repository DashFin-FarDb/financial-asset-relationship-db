#!/bin/bash
# Gemini AfterTool Hook for Snipara File Tracking
# Emits strict JSON and suppresses internal output.

INPUT=$(cat)
if [ -n "$INPUT" ] && ! printf '%s' "$INPUT" | jq empty >/dev/null 2>&1; then
  echo "Snipara AfterTool received invalid JSON; continuing" >&2
  jq -n '{ suppressOutput: true }'
  exit 0
fi

CONTEXT=$(snipara-companion post-tool "$INPUT" 2>/dev/stderr || true)
if [ -n "$CONTEXT" ]; then
  jq -n --arg content "$CONTEXT" '{
    hookSpecificOutput: { additionalContext: $content },
    suppressOutput: true
  }'
else
  jq -n '{ suppressOutput: true }'
fi
