<!-- snipara:workflow GEMINI.md:start -->
# Gemini Snipara Workflow

Gemini should apply this workflow automatically for project-specific work.

## Snipara Context Workflow

This workspace is bound to Snipara project `financial-asset-relationship-db` for Gemini. Agents should use Snipara automatically for project-specific context, decisions, and workflow state.

- Hosted MCP endpoint: `https://api.snipara.com/mcp/financial-asset-relationship-db`
- At the start of substantial work, validate the hosted MCP surface with a tool-oriented call, then use `snipara_recall` and a targeted `snipara_context_query` before falling back to local search.
- Do not treat empty MCP resources/templates as an outage. If the tool surface looks incomplete, call `snipara_help(list_all=true)` and compare exact tool names.
- Use `snipara_context_query` for docs, business context, architecture notes, runbooks, and source truth. Use `snipara_get_chunk` for exact cited sections when references are returned.
- For coding work, choose LITE or FULL before editing. Use FULL managed workflow for multi-file, risky, release/deploy, architectural, compaction-prone, or future-maintainer-sensitive work.
- When a visible multi-phase plan exists, keep the machine plan in JSON and run `snipara-companion workflow start --goal "<goal>" --plan-file <plan_json_file>`. Use `workflow phase-start` / `workflow phase-commit` per phase, and after `workflow resume` rerun `workflow phase-start` before editing again.
- Run `snipara_code_impact` before risky multi-file changes, PR reviews, routes, services, jobs, auth, billing, deployment, schema, migrations, or explicit "what is missing" assessments.
- Use local file reads, `rg`, git commands, and tests for exact edits and current working-tree state.
- Use Snipara Sandbox only when sandboxed execution, repeatable validation, or isolated transformations materially help. For runtime-bound phases, capture compact rehydratable state with `workflow runtime-checkpoint <phase_id> --summary "<state>" --rehydrate-file <state.json>`. Then `workflow resume` restores workflow/memory continuity plus the recorded Sandbox binding and prints a reattach or rehydrate plan. It does not snapshot or exactly restore a live Snipara Sandbox / REPL process.
- End substantial work with `snipara_end_of_task_commit` when available. For managed workflows, commit each phase with `snipara-companion workflow phase-commit` and close with `snipara-companion final-commit`.
- Store only durable decisions, learnings, preferences, and workflow context. Never store secrets, tokens, raw logs, one-off command output, or unreviewed guesses.
<!-- snipara:workflow GEMINI.md:end -->

<!-- snipara:automation GEMINI.md:start -->
# Gemini Project Context for financial-asset-relationship-db

## MCP Server Integration

This project uses Snipara for context optimization via MCP.

**Endpoint**: https://api.snipara.com/mcp/financial-asset-relationship-db

## Available MCP Tools

Current hosted contract: 125 tools. Most common ones for Gemini are listed below.

| Tool | Description |
|------|-------------|
| `snipara_ask` | Query documentation with natural language |
| `snipara_search` | Search for patterns (regex supported) |
| `snipara_context_query` | Get optimized context with token budget |
| `snipara_help` | Recommend the right tool or workflow for the task |
| `snipara_recall` | Recover durable project memory |
| `snipara_remember_if_novel` | Save memory while skipping duplicates |
| `snipara_end_of_task_commit` | Persist durable outcomes from a task summary |
| `snipara_inject` | Set session context/focus |
| `snipara_context` | Show current session context |
| `snipara_stats` | Show documentation statistics |
| `snipara_sections` | List all documentation sections |
| `snipara_read` | Read specific line ranges |

## Usage Guidelines

1. Before answering questions about the codebase, query Snipara first
2. Use `snipara_inject` to set context when starting a new task
3. Use `snipara_search` for finding specific code patterns
4. Use `snipara_ask` for conceptual/architectural questions
5. Use `snipara_context_query` with a token budget for large queries

## Example Workflow

```
1. User asks: "How does authentication work?"
2. Call snipara_context_query(query="authentication flow", max_tokens=4000)
3. Use the returned context to answer accurately
```

## Gemini CLI Commands

```bash
# List available MCP servers
gemini mcp list

# Query the Snipara server directly
gemini -p "Use snipara_ask to explain authentication"

# Non-interactive mode
gemini --prompt "Search for auth patterns" --output-format json
```
<!-- snipara:automation GEMINI.md:end -->
