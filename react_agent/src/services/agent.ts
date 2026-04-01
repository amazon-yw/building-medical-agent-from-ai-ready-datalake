export interface ChatMessage {
  role: "user" | "model";
  text: string;
}

export async function streamAgentResponse(
  prompt: string,
  sessionId: string,
  onText: (text: string) => void,
  onToolCall?: (name: string) => void,
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
      const text = line.slice(6);

      if (text === "[DONE]") {
        onDone?.();
        continue;
      }
      if (text.startsWith("[ERROR]")) {
        onText(`\n\n❌ ${text}`);
        continue;
      }

      // Detect tool markers
      if (text.startsWith("🔧")) {
        const name = text.replace("🔧", "").trim().split("\n")[0].replace(/\*/g, "").trim();
        onToolCall?.(name);
        continue;
      }
      if (text.startsWith("📥")) continue;
      if (text.includes("Result:")) {
        const isError = text.startsWith("❌");
        const result = text.split("Result:")[1]?.trim() || "";
        onToolResult?.(result, isError);
        continue;
      }

      onText(text);
    }
  }
}
