#!/bin/bash
# Gemini BeforeTool Hook for Snipara Stuck Guard
# Advisory allow by default; logs go to stderr.

INPUT=$(cat)
if [ -n "$INPUT" ] && ! printf '%s' "$INPUT" | jq empty >/dev/null 2>&1; then
  echo "Snipara BeforeTool received invalid JSON; allowing tool" >&2
  jq -n '{ decision: "allow", suppressOutput: true }'
  exit 0
fi

CONTEXT=$(snipara-companion pre-tool "$INPUT" --stuck-guard-only 2>/dev/stderr || true)
if [ -n "$CONTEXT" ]; then
  jq -n --arg content "$CONTEXT" '{
    decision: "allow",
    hookSpecificOutput: { additionalContext: $content },
    suppressOutput: true
  }'
else
  jq -n '{ decision: "allow", suppressOutput: true }'
fi
