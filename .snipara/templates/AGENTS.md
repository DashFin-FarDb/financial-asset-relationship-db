# AGENTS.md

## Snipara Context Workflow

This project uses Snipara Hosted MCP for project context and reviewed memory.

- Endpoint: `https://api.snipara.com/mcp/context-free`
- Auth: use `SNIPARA_API_KEY` from the environment. Never commit keys.
- For Codex, expose the endpoint as a streamable HTTP MCP server and load the
  key from `SNIPARA_API_KEY`.
- At the start of every new thread, validate hosted MCP with a tool-oriented
  call such as `snipara_settings`, `tools/list`, or a lightweight
  `snipara_context_query`. Do not treat empty MCP resources/templates as an
  outage because Snipara may be tool-only.
- In Codex, if only a minimal Snipara tool subset appears, force precise tool
  discovery for `snipara_recall`, `snipara_context_query`, and
  `snipara_settings` before concluding the MCP server is incomplete.
- If a session appears to expose only a subset of expected Snipara tools, call
  `snipara_help(list_all=true)` and compare exact tool names before concluding
  that a tool is unavailable. Do not infer absence from one broad discovery
  pass or a ranked tool-search result.
- If Codex still exposes only a partial surface after exact discovery, use
  `snipara-companion recall`, `snipara-companion query`, and
  `snipara-companion task-commit` as the reliable local fallback, then restart
  or reload Codex after MCP config changes.

Agent task lifecycle:

1. Start every new thread by validating hosted MCP availability, then use
   project-scoped `snipara_recall` and a targeted `snipara_context_query` before
   falling back to local documentation search.
2. Use `snipara_context_query` for docs, business context, client/project truth, architecture notes, runbooks, and narrative source material.
3. When `snipara_context_query` returns `answer_pack`, treat it as the first-pass response plan: use its source facts, caveats, source map, and verification checklist before drafting claims.
4. Use `snipara_get_chunk` to load cited source sections returned by reference-based queries before relying on precise wording.
5. For coding tasks, choose a workflow mode before editing: LITE for small
   single-phase changes, FULL managed workflow for multi-file, risky,
   release/deploy, architectural, compaction-prone, or future-maintainer-sensitive
   work.
6. Use whichever structural code graph tools are exposed in the current session
   for callers, imports, neighbors, and path questions. Tool exposure can vary.
7. On paid Context plans, use `snipara_code_symbol_card` for agent-ready symbol
   context and `snipara_code_impact` before risky multi-file changes, PR
   reviews, routes, services, jobs, auth, billing, deployment, schema, migrations,
   or explicit "what is missing" assessments.
8. Use `snipara_plan` or `snipara_decompose` only for FULL-mode work and only
   when the hosted server exposes them.
9. When the LLM has produced a visible multi-phase plan and `snipara-companion`
   is installed, keep the machine plan in JSON and run
   `snipara-companion workflow start --goal "<goal>" --plan-file <plan_json_file>`.
   Use `workflow phase-start` / `workflow phase-commit` per phase, and after
   `workflow resume` rerun `workflow phase-start <phase_id>` before editing
   again. For runtime-bound phases, capture compact rehydratable Sandbox state
   with `workflow runtime-checkpoint <phase_id> --summary "<state>" --rehydrate-file <state.json>`.
10. Use local file reads, `rg`, git commands, and test commands for exact edits,
    current working-tree state, and verification.
11. Treat every `snipara_code_*` response as indexed context: check indexed
    commit SHA, indexing time, included file sample, coverage, freshness warnings,
    and sync guidance before relying on it. If `git status --short` is dirty,
    warn that the indexed graph may not include local edits.
12. Use Snipara Sandbox only when sandboxed execution, repeatable validation, or
    isolated transformations materially help.
13. If a broad query is slow, retry once with a narrow keyword query before
    falling back to local search.
14. When generated hooks are enabled, `snipara-companion pre-tool`, `post-tool`,
    and `stuck-guard status` provide runtime Rescue Pack checks for repeated
    failures, empty searches, and risky workflows.
15. End each substantial phase with `snipara_end_of_task_commit` or
    `snipara-companion workflow phase-commit` when companion manages the plan.
    End the whole managed workflow with `snipara-companion final-commit`.
16. Use `snipara_remember_if_novel` for one reusable memory while avoiding
    duplicates, and use `snipara_remember` for explicit direct memory writes.
17. Do not store secrets, tokens, passwords, private keys, raw logs, transient
    command output, or unreviewed guesses in memory.
