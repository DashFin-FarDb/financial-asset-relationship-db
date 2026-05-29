# CLAUDE.md

Canonical project context is in `AGENTS.md`. This file exists for Claude Code compatibility.

## Snipara

Use Snipara Hosted MCP before answering project-specific questions.

- Endpoint: `https://api.snipara.com/mcp/context-free`
- If a session exposes only a subset of expected Snipara tools, call `snipara_help(list_all=true)` before concluding a tool is unavailable.
- Start substantial work with `snipara_recall` and a targeted `snipara_context_query`.
- Use `snipara_context_query` for source truth and `snipara_get_chunk` for exact cited sections.
- When `snipara_context_query` returns `answer_pack`, use its facts, caveats, source map, and verification checklist before drafting claims.
- Use `snipara_code_callers`, `snipara_code_imports`, `snipara_code_neighbors`, or `snipara_code_shortest_path` for structural code questions.
- On paid Context plans, use `snipara_code_symbol_card` before editing important symbols and `snipara_code_impact` before risky multi-file changes or PR reviews.
- Check every `snipara_code_*` response for indexed commit SHA, indexing time, included files, coverage, and freshness warnings.
- Use local file reads, `rg`, `git status --short`, and tests for exact edits/current working tree; use Snipara for architecture and indexed code graph context.
- When the plan is visible and `snipara-companion` is installed, keep the machine plan in JSON, use `snipara-companion workflow start`, `phase-start`, and `phase-commit` per phase, and after `workflow resume` rerun `workflow phase-start` before editing again.
- If generated hooks are enabled, `snipara-companion pre-tool`, `post-tool`, and `stuck-guard status` provide runtime Rescue Pack checks when the agent loops on failures or empty searches.
- Use Snipara Sandbox only when sandboxed execution or repeatable validation materially helps. For runtime-bound phases, capture compact rehydratable state with `workflow runtime-checkpoint <phase_id> --summary "<state>" --rehydrate-file <state.json>`. Then `workflow resume` restores workflow and memory continuity plus the recorded Sandbox binding and prints a reattach or rehydrate plan. It does not snapshot or exactly restore a live Snipara Sandbox or REPL process.
- End substantial work with `snipara_end_of_task_commit` when available; for managed workflows, end every phase with `snipara-companion workflow phase-commit` and the task with `snipara-companion final-commit`.
- Use `snipara_remember_if_novel` or `snipara_remember` only for narrow durable memories.
- Do not store secrets, one-off command output, raw logs, or unreviewed guesses in memory.
- Use the Snipara Claude Code plugin only when slash commands, skills, or hooks are helpful; Hosted MCP remains the normal agent path.
