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
      const raw = line.slice(6).trim();
      if (!raw) continue;

      try {
        const event = JSON.parse(raw);
        switch (event.type) {
          case "text":
            onText(event.content || "");
            break;
          case "tool_call":
            onToolCall?.(event.name || "");
            break;
          case "tool_input":
            // skip for now, could display if needed
            break;
          case "tool_result":
            onToolResult?.(event.result || "", event.isError || false);
            break;
          case "error":
            onText(`\n\n❌ Error: ${event.content}`);
            break;
          case "done":
            onDone?.();
            break;
        }
      } catch {
        // non-JSON line, treat as text
        onText(raw);
      }
    }
  }
}
