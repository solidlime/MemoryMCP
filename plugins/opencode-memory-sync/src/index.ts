import type { PluginInput, Hooks } from "@opencode-ai/plugin";

const MCP_URL = process.env.MEMORY_MCP_URL || "http://localhost:26262";
const API_KEY = process.env.MEMORY_MCP_API_KEY || "";
const PERSONA = process.env.MEMORY_MCP_PERSONA || "default";

async function ingest(sessionID: string, events: Array<{
  type: string;
  summary: string;
  detail?: string;
  metadata?: Record<string, unknown>;
}>) {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (API_KEY) headers["Authorization"] = `Bearer ${API_KEY}`;

  try {
    const res = await fetch(`${MCP_URL}/api/events/ingest`, {
      method: "POST",
      headers,
      body: JSON.stringify({ session_id: sessionID, persona: PERSONA, events }),
    });
    if (!res.ok) {
      console.error(`[memory-sync] ingest failed: ${res.status} ${await res.text()}`);
    }
  } catch (err) {
    console.error(`[memory-sync] ingest error: ${err}`);
  }
}

export async function server(input: PluginInput, _options?: Record<string, unknown>): Promise<Hooks> {
  console.log(`[memory-sync] connected — sending to ${MCP_URL} as "${PERSONA}"`);
  let sessionID: string | null = null;

  return {
    // Track session start via first message
    "chat.message": async (input, _output) => {
      sessionID = input.sessionID;
      await ingest(sessionID, [{
        type: "session.started",
        summary: `OpenCode session started: ${sessionID}`,
        metadata: { platform: "opencode", model: input.model?.modelID },
      }]);
    },

    // Capture tool calls before execution
    "tool.execute.before": async (input, _output) => {
      if (!sessionID) sessionID = input.sessionID;
      await ingest(sessionID, [{
        type: "tool.called",
        summary: `🔧 ${input.tool}`,
        detail: JSON.stringify(input.callID),
        metadata: { platform: "opencode", tool: input.tool, callID: input.callID },
      }]);
    },

    // Capture tool results after execution
    "tool.execute.after": async (input, output) => {
      if (!sessionID) sessionID = input.sessionID;
      const detail = output.output?.slice(0, 200) || "";
      await ingest(sessionID, [{
        type: "tool.result",
        summary: `✅ ${input.tool}`,
        detail: detail || undefined,
        metadata: { platform: "opencode", tool: input.tool, callID: input.callID },
      }]);
    },

    // Capture session compaction
    "experimental.session.compacting": async (input, output) => {
      if (!sessionID) sessionID = input.sessionID;
      await ingest(sessionID, [{
        type: "session.compact",
        summary: `📦 Session compacting`,
        detail: output.context?.join("\n")?.slice(0, 200) || undefined,
        metadata: { platform: "opencode" },
      }]);
    },

    // Cleanup on dispose
    dispose: async () => {
      if (sessionID) {
        await ingest(sessionID, [{
          type: "session.stopped",
          summary: `OpenCode session ended: ${sessionID}`,
          metadata: { platform: "opencode" },
        }]);
      }
      console.log("[memory-sync] disconnected");
    },
  };
}
