export interface ChatMessage {
  role: "user" | "model";
  text: string;
}

export async function streamAgentResponse(
  prompt: string,
  sessionId: string,
  onText: (text: string) => void,
  onToolCall?: (name: string, input: string) => void,
  onToolResult?: (result: string, isError: boolean) => void,
  onDone?: () => void
): Promise<void> {
  const resp = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, sessionId }),
  });

  if (!resp.ok) throw new Error(`Server error: ${resp.status}`);

  const reader = resp.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      let text = line.slice(6);

      if (text === "[DONE]") { onDone?.(); continue; }
      if (text.startsWith("[ERROR]")) { onText(`\n\n❌ ${text}`); continue; }

      // Check for embedded tool markers within the text
      // Pattern: \n\n🔧 **tool_name**\n📥 Input: `{...}`\n
      const toolCallMatch = text.match(/🔧\s*\*{0,2}(\w+)\*{0,2}/);
      const toolInputMatch = text.match(/📥\s*Input:\s*`?({[^`]*})`?/);
      const toolResultMatch = text.match(/(✅|❌)\s*Result:\s*(.*)/);

      if (toolCallMatch) {
        // Split: text before tool marker goes as text, tool marker as tool_call
        const idx = text.indexOf("🔧");
        const before = text.substring(0, idx).replace(/\\n/g, "\n").trim();
        if (before) onText(before);

        const name = toolCallMatch[1];
        const input = toolInputMatch ? toolInputMatch[1] : "";
        onToolCall?.(name, input);
        continue;
      }

      if (toolResultMatch) {
        const isError = toolResultMatch[1] === "❌";
        const result = toolResultMatch[2].trim();
        onToolResult?.(result, isError);
        continue;
      }

      // Regular text - unescape \n
      text = text.replace(/\\n/g, "\n");
      onText(text);
    }
  }
}
