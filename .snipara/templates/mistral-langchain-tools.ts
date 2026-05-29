import { ChatMistralAI } from "@langchain/mistralai";
import { tool } from "@langchain/core/tools";
import { z } from "zod";

const SNIPARA_MCP_URL = process.env.SNIPARA_MCP_URL || "https://api.snipara.com/mcp/context-free";
const SNIPARA_API_KEY = process.env.SNIPARA_API_KEY;

if (!SNIPARA_API_KEY) {
  throw new Error("Missing SNIPARA_API_KEY");
}

async function callSniparaTool(toolName: string, args: Record<string, unknown>): Promise<string> {
  const response = await fetch(SNIPARA_MCP_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": SNIPARA_API_KEY,
    },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: Date.now(),
      method: "tools/call",
      params: {
        name: toolName,
        arguments: args,
      },
    }),
  });

  const payload = (await response.json()) as { error?: unknown; result?: unknown };
  if (!response.ok || payload.error) {
    throw new Error("Snipara MCP call failed: " + JSON.stringify(payload.error || payload));
  }

  return JSON.stringify(payload.result || {});
}

export const sniparaRecallTool = tool(
  async ({ query, type }) =>
    callSniparaTool("snipara_recall", {
      query,
      ...(type ? { type } : {}),
    }),
  {
    name: "snipara_recall",
    description: "Recall durable Snipara decisions, preferences, and validated learnings.",
    schema: z.object({
      query: z.string().describe("Focused memory query."),
      type: z.enum(["decision", "learning", "context", "preference"]).optional(),
    }),
  }
);

export const sniparaContextQueryTool = tool(
  async ({ query, maxTokens }) =>
    callSniparaTool("snipara_context_query", {
      query,
      max_tokens: maxTokens,
      return_references: true,
    }),
  {
    name: "snipara_context_query",
    description: "Retrieve optimized source context, docs, runbooks, and source-truth references.",
    schema: z.object({
      query: z.string().describe("Question or task needing project context."),
      maxTokens: z.number().int().positive().max(12000).default(4000),
    }),
  }
);

export const sniparaSettingsTool = tool(() => callSniparaTool("snipara_settings", {}), {
  name: "snipara_settings",
  description: "Validate the hosted Snipara MCP server and project settings.",
  schema: z.object({}),
});

const beforeRequestHook = (req: Request): Request => {
  const headers = new Headers(req.headers);
  headers.set("X-Snipara-Client", "mistral-langchain");
  return new Request(req, { headers });
};

const requestErrorHook = async (err: unknown, req: Request): Promise<void> => {
  console.warn("Mistral request failed", { url: req.url, err });
};

const responseHook = async (res: Response, req: Request): Promise<void> => {
  void req;
  void res;
};

export const mistralWithSniparaTools = new ChatMistralAI({
  model: process.env.MISTRAL_MODEL || "mistral-large-latest",
  temperature: 0,
  maxRetries: 2,
  beforeRequestHooks: [beforeRequestHook],
  requestErrorHooks: [requestErrorHook],
  responseHooks: [responseHook],
}).bindTools([sniparaRecallTool, sniparaContextQueryTool, sniparaSettingsTool]);
