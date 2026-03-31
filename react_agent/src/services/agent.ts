export interface ChatMessage {
  role: "user" | "model";
  text: string;
  toolCalls?: { name: string; input: string; result: string; elapsed: string; isError: boolean }[];
}

const API_URL = "";

export async function streamAgentResponse(
  prompt: string,
  sessionId: string,
  onChunk: (chunk: string) => void,
  onToolCall?: (name: string) => void,
  onToolResult?: (name: string, result: string, elapsed: string, isError: boolean) => void
): Promise<void> {
  const resp = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, sessionId }),
  });

  if (!resp.ok) throw new Error(`Server error: ${resp.status}`);

  const reader = resp.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";
  let toolStart = 0;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      let text = line.slice(6).trim();
      if (!text) continue;

      // Try to parse JSON chunks
      try {
        const parsed = JSON.parse(text);
        if (parsed.error) {
          onChunk(`\n\n❌ Error: ${parsed.error}`);
          continue;
        }
        text = parsed.content || parsed.response || parsed.text || text;
      } catch {
        // plain text, use as-is
      }

      // Tool call markers
      if (text.startsWith("🔧")) {
        const name = text.replace("🔧", "").trim().split("\n")[0].replace(/\*/g, "").trim();
        toolStart = Date.now();
        onToolCall?.(name);
        continue;
      }
      if (text.startsWith("📥")) continue; // tool input, skip for now
      if (text.includes("Result:")) {
        const elapsed = toolStart ? `${((Date.now() - toolStart) / 1000).toFixed(1)}s` : "";
        const isError = text.startsWith("❌");
        const result = text.split("Result:")[1]?.trim() || "";
        onToolResult?.("", result, elapsed, isError);
        toolStart = 0;
        continue;
      }

      onChunk(text);
    }
  }
}
