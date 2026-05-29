#!/bin/bash
# Gemini PreCompress Hook for Snipara Context Checkpointing
# Writes only JSON to stdout.

PROJECT_DIR="${GEMINI_PROJECT_DIR:-$PWD}"
CHECKPOINT_FILE="$PROJECT_DIR/.gemini/.session-context"
INPUT=$(cat)

if [ -n "$INPUT" ]; then
  mkdir -p "$(dirname "$CHECKPOINT_FILE")"
  printf '%s' "$INPUT" > "$CHECKPOINT_FILE"
  echo "Snipara PreCompress checkpoint saved" >&2
fi

jq -n '{ suppressOutput: true }'
