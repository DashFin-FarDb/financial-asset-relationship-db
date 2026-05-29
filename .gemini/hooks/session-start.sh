#!/bin/bash
# Gemini SessionStart Hook for Snipara Context Restoration
# Gemini hooks require strict stdout JSON. Keep logs on stderr.

PROJECT_DIR="${GEMINI_PROJECT_DIR:-$PWD}"
CHECKPOINT_FILE="$PROJECT_DIR/.gemini/.session-context"
WORKFLOW_FILE="$PROJECT_DIR/.snipara/workflow/current.json"
CONTEXT=""

if [ -f "$CHECKPOINT_FILE" ]; then
  CHECKPOINT_CONTEXT=$(cat "$CHECKPOINT_FILE")
  if [ -n "$CHECKPOINT_CONTEXT" ]; then
    CONTEXT="## Snipara Session Checkpoint

$CHECKPOINT_CONTEXT"
  fi
fi

if [ -f "$WORKFLOW_FILE" ]; then
  WORKFLOW_STATUS=$(jq -r '.status // empty' "$WORKFLOW_FILE" 2>/dev/null || true)
  if [ "$WORKFLOW_STATUS" != "completed" ]; then
    WORKFLOW_CONTEXT=$(cat "$WORKFLOW_FILE")
    if [ -n "$WORKFLOW_CONTEXT" ]; then
      if [ -n "$CONTEXT" ]; then
        CONTEXT="$CONTEXT

---

## Snipara Managed Workflow State

$WORKFLOW_CONTEXT"
      else
        CONTEXT="## Snipara Managed Workflow State

$WORKFLOW_CONTEXT"
      fi
    fi
  fi
fi

if [ -n "$CONTEXT" ]; then
  jq -n --arg content "$CONTEXT" '{
    hookSpecificOutput: { additionalContext: $content },
    suppressOutput: true
  }'
else
  jq -n '{ suppressOutput: true }'
fi
