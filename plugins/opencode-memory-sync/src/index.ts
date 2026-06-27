import type { PluginInput, Hooks } from "@opencode-ai/plugin";

const MCP_URL = process.env.MEMORY_MCP_URL || "http://localhost:26262";
const API_KEY = process.env.MEMORY_MCP_API_KEY || "";
const PERSONA = process.env.MEMORY_MCP_PERSONA || "default";
const INJECT_ON = (process.env.MEMORY_INJECT_ON || "first") as "first" | "always";

// Warmup non-blocking pattern — prevents 70s hang on startup
const WARMUP_KEY = Symbol.for("nous.memory-sync.warmedup");

const WARMUP_TIMEOUT_MS = 30000; // 30s

async function warmupAsync() {
  if ((globalThis as any)[WARMUP_KEY]) return;
  try {
    // TODO: 実際の warmup 処理（embedding model load + index rebuild）が実装されたらここに追加
    (globalThis as any)[WARMUP_KEY] = true;
    console.log("[nous-memory-sync] Warmup completed");
  } catch (error) {
    console.warn("[nous-memory-sync] Warmup failed, falling back to text-only mode:", error);
    (globalThis as any)[WARMUP_KEY] = true; // 失敗しても二度と再試行しない
  }
}

// Fire-and-forget: warmup を非同期で開始し、メインスレッドをブロックしない
if (!(globalThis as any)[WARMUP_KEY]) {
  warmupAsync();
}

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

// --- F-1 / F-2: Memory search & context helpers ---

interface MemoryResult {
  content: string;
  score?: number;
  tags?: string[];
  metadata?: Record<string, unknown>;
}

async function searchMemories(query: string, limit = 5): Promise<MemoryResult[]> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (API_KEY) headers["Authorization"] = `Bearer ${API_KEY}`;
  try {
    const res = await fetch(`${MCP_URL}/api/memory/search`, {
      method: "POST",
      headers,
      body: JSON.stringify({ query, persona: PERSONA, limit }),
    });
    if (!res.ok) {
      console.warn(`[memory-sync] search failed: ${res.status}`);
      return [];
    }
    return await res.json() as MemoryResult[];
  } catch (err) {
    console.warn(`[memory-sync] search error: ${err}`);
    return [];
  }
}

async function getProfile(): Promise<string | null> {
  const headers: Record<string, string> = {};
  if (API_KEY) headers["Authorization"] = `Bearer ${API_KEY}`;
  try {
    const res = await fetch(`${MCP_URL}/api/profile`, { headers });
    if (!res.ok) return null;
    const data = await res.json() as { summary?: string };
    return data?.summary ?? null;
  } catch (err) {
    console.warn(`[memory-sync] profile error: ${err}`);
    return null;
  }
}

function formatMemoryContext(memories: MemoryResult[], profile: string | null): string {
  const lines: string[] = ["[MEMORY]"];
  if (profile) {
    lines.push("", "## Profile", profile);
  }
  if (memories.length > 0) {
    lines.push("", "## Recent Knowledge");
    for (const mem of memories) {
      const score = mem.score != null ? ` [${Math.round(mem.score * 100)}%]` : "";
      lines.push(`-${score} ${mem.content}`);
    }
  }
  return lines.join("\n");
}

function formatCompactionContext(memories: MemoryResult[]): string {
  const lines: string[] = ["## Restored Session Memory"];
  for (let i = 0; i < memories.length; i++) {
    const mem = memories[i];
    lines.push("", `### Memory ${i + 1}`, mem.content);
    if (mem.tags?.length) {
      lines.push(`Tags: ${mem.tags.join(", ")}`);
    }
  }
  return lines.join("\n");
}

function isNonSyntheticUserMessage(msg: {
  info: { role: string };
  parts: Array<Record<string, unknown>>;
}): boolean {
  return msg.info.role === "user" && !msg.parts.some((p) => p.synthetic);
}

export async function server(input: PluginInput, _options?: Record<string, unknown>): Promise<Hooks> {
  const client = input.client; // capture for closures (hooks shadow outer `input`)
  console.log(`[memory-sync] connected — sending to ${MCP_URL} as "${PERSONA}"`);
  let sessionID: string | null = null;
  let isAfterCompaction = false;

  return {
    // Track session start via first message + inject memory context
    "chat.message": async (hookInput, output) => {
      sessionID = hookInput.sessionID;

      // Always ingest session.started (existing behavior)
      await ingest(sessionID, [{
        type: "session.started",
        summary: `OpenCode session started: ${sessionID}`,
        metadata: { platform: "opencode", model: hookInput.model?.modelID },
      }]);

      // --- F-1: Memory context injection ---
      try {
        const msgRes = await client.session.messages({ path: { id: hookInput.sessionID } });
        const msgs = msgRes.data ?? [];
        const hasNonSynthetic = msgs.some(isNonSyntheticUserMessage);

        const shouldInject =
          INJECT_ON === "always" ||
          !hasNonSynthetic ||
          (isAfterCompaction && msgs.filter(isNonSyntheticUserMessage).length === 1);

        if (shouldInject) {
          const query = output.message.summary?.body ?? "";
          const [memories, profile] = await Promise.all([
            searchMemories(query),
            getProfile(),
          ]);

          const contextText = formatMemoryContext(memories, profile);

          // Skip if no actual memory content to inject
          if (contextText !== "[MEMORY]") {
            output.parts.unshift({
              id: `prt-memory-context-${Date.now()}`,
              sessionID: hookInput.sessionID,
              messageID: output.message.id,
              type: "text" as const,
              text: contextText,
              synthetic: true,
            });
          }

          isAfterCompaction = false;
        }
      } catch (err) {
        console.warn(`[memory-sync] injection error: ${err}`);
        // Graceful degradation — continue without injection
      }
    },

    // Capture tool calls before execution
    "tool.execute.before": async (hookInput, _output) => {
      if (!sessionID) sessionID = hookInput.sessionID;
      await ingest(sessionID, [{
        type: "tool.called",
        summary: `🔧 ${hookInput.tool}`,
        detail: JSON.stringify(hookInput.callID),
        metadata: { platform: "opencode", tool: hookInput.tool, callID: hookInput.callID },
      }]);
    },

    // Capture tool results after execution
    "tool.execute.after": async (hookInput, output) => {
      if (!sessionID) sessionID = hookInput.sessionID;
      const detail = output.output?.slice(0, 200) || "";
      await ingest(sessionID, [{
        type: "tool.result",
        summary: `✅ ${hookInput.tool}`,
        detail: detail || undefined,
        metadata: { platform: "opencode", tool: hookInput.tool, callID: hookInput.callID },
      }]);
    },

    // Capture session compaction + track flag for post-compaction injection
    "experimental.session.compacting": async (hookInput, output) => {
      if (!sessionID) sessionID = hookInput.sessionID;
      isAfterCompaction = true;
      await ingest(sessionID, [{
        type: "session.compact",
        summary: `📦 Session compacting`,
        detail: output.context?.join("\n")?.slice(0, 200) || undefined,
        metadata: { platform: "opencode" },
      }]);
    },

    // --- F-2: Compaction recovery via event hook ---
    event: async ({ event }) => {
      if (event.type !== "session.compacted") return;
      const sid = event.properties.sessionID;
      if (!sessionID) sessionID = sid;
      isAfterCompaction = true;
      try {
        const memories = await searchMemories("", 10);
        if (memories.length > 0) {
          const contextText = formatCompactionContext(memories);
          await client.session.prompt({
            path: { id: sid },
            body: {
              parts: [{ type: "text" as const, text: contextText }],
              noReply: true,
            },
          });
        }
      } catch (err) {
        console.warn(`[memory-sync] compaction recovery error: ${err}`);
      }
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
