# Snipara Pack: OpenAI Codex

This pack is the client-specific overlay for the generated Snipara project setup.
Use `AGENTS.md` as the shared source of agent behavior, then apply the client-specific files below.

## Hosted MCP

- Endpoint: `https://api.snipara.com/mcp/context-free`
- Auth: `SNIPARA_API_KEY` from the environment or local client secret store
- Do not commit API keys or bearer tokens.

## Client Files

- `AGENTS.md`
- `.codex/config.toml`
- `.snipara/templates/codex-config.toml`

## Recommended Setup

1. Bootstrap companion: `npx -y snipara-companion@latest init --client codex --project context-free`
2. Confirm the client can list or call the `snipara_*` MCP tools.
3. Keep exact edits, tests, and dirty working-tree checks local; use Snipara for memory, source truth, and indexed code graph context.
4. For generated local automations, run `npx -y snipara-companion@latest automations install --client codex` when that client exposes usable automation files.

## Client Guidance

- Codex should use the hosted MCP surface plus AGENTS.md as the canonical project instruction file.
- The generated .snipara/templates/codex-config.toml is a merge-ready snippet for ~/.codex/config.toml if your Codex app does not read project .codex/config.toml.
- Use SNIPARA_API_KEY as the only Codex bearer_token_env_var; restart Codex after changing MCP config.
- If Codex lazily exposes only a minimal tool set, force discovery for snipara_recall, snipara_context_query, snipara_settings, and the exact htask or swarm tool names you need; use snipara_help(list_all=true) to confirm the hosted catalog before concluding the MCP surface is incomplete.
- When Codex still exposes only the minimal core tools, use snipara-orchestrator swarm-* and htask-* as the primary path for shared queues and multi-agent task work; keep snipara-companion swarm ... and htask ... as the direct hosted fallback when you only need one-off hosted calls.

## Agent Workflow

- Start substantial work with `snipara_recall` and `snipara_context_query`.
- Use `answer_pack` facts, caveats, source maps, and verification checks before making claims.
- Use `snipara_code_symbol_card` and `snipara_code_impact` for important symbols or risky multi-file changes when available.
- Use the installed `snipara-companion` binary for low-latency hooks; use `npx -y snipara-companion@latest` for one-off terminal commands when freshness matters.
- Use a JSON machine plan plus `snipara-companion workflow start`, `phase-start`, `phase-commit`, `workflow resume`, and `final-commit` for multi-phase work. After `workflow resume`, rerun `workflow phase-start <phase_id>` before editing again.
- Persist only durable decisions, learnings, preferences, workflows, and troubleshooting outcomes. Never persist secrets.

