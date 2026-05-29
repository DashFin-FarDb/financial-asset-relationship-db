# Snipara Pack: Gemini

This pack is the client-specific overlay for the generated Snipara project setup.
Use `AGENTS.md` as the shared source of agent behavior, then apply the client-specific files below.

## Hosted MCP

- Endpoint: `https://api.snipara.com/mcp/snp-52c7fbb4553349adae96da4c1040b6e6b7336938a695192932ccdf91f558fecb`
- Auth: `SNIPARA_API_KEY` from the environment or local client secret store
- Do not commit API keys or bearer tokens.

## Client Files

- `AGENTS.md`
- `.snipara/templates/gemini-mcp-reference.json`

## Recommended Setup

1. Bootstrap companion: `npx -y snipara-companion@latest init --client gemini --project snp-52c7fbb4553349adae96da4c1040b6e6b7336938a695192932ccdf91f558fecb`
2. Confirm the client can list or call the `snipara_*` MCP tools.
3. Keep exact edits, tests, and dirty working-tree checks local; use Snipara for memory, source truth, and indexed code graph context.
4. For generated local automations, run `npx -y snipara-companion@latest automations install --client gemini` when that client exposes usable automation files.

## Client Guidance

- Gemini should use Hosted MCP plus the generated AGENTS.md rules; no local shell hooks are assumed.
- Use .snipara/templates/gemini-mcp-reference.json as a field reference for the client's MCP settings.

## Agent Workflow

- Start substantial work with `snipara_recall` and `snipara_context_query`.
- Use `answer_pack` facts, caveats, source maps, and verification checks before making claims.
- Use `snipara_code_symbol_card` and `snipara_code_impact` for important symbols or risky multi-file changes when available.
- Use the installed `snipara-companion` binary for low-latency hooks; use `npx -y snipara-companion@latest` for one-off terminal commands when freshness matters.
- Use a JSON machine plan plus `snipara-companion workflow start`, `phase-start`, `phase-commit`, `workflow resume`, and `final-commit` for multi-phase work. After `workflow resume`, rerun `workflow phase-start <phase_id>` before editing again.
- Persist only durable decisions, learnings, preferences, workflows, and troubleshooting outcomes. Never persist secrets.

