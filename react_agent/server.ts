import express from "express";
import cors from "cors";
import {
  BedrockAgentCoreClient,
  InvokeAgentRuntimeCommand,
} from "@aws-sdk/client-bedrock-agent-runtime";

const app = express();
app.use(cors());
app.use(express.json());

const REGION = process.env.AWS_REGION || process.env.AWS_DEFAULT_REGION || "us-east-1";
const AGENT_ARN = process.env.AGENT_ARN || "";

const client = new BedrockAgentCoreClient({ region: REGION });

app.post("/api/chat", async (req, res) => {
  const { prompt, sessionId } = req.body;
  if (!AGENT_ARN) {
    return res.status(500).json({ error: "AGENT_ARN not set" });
  }

  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");

  try {
    const cmd = new InvokeAgentRuntimeCommand({
      agentRuntimeArn: AGENT_ARN,
      payload: Buffer.from(JSON.stringify({ prompt })),
      runtimeSessionId: sessionId,
      contentType: "application/json",
      accept: "application/json",
    });

    const response = await client.send(cmd);
    const body = response.response;

    if (body) {
      const raw = await body.transformToByteArray();
      const text = new TextDecoder().decode(raw);
      // Forward each line as SSE
      for (const line of text.split("\n")) {
        if (line.trim()) {
          res.write(`data: ${line}\n\n`);
        }
      }
    }
  } catch (err: any) {
    res.write(`data: {"error": "${err.message}"}\n\n`);
  }

  res.end();
});

app.get("/api/health", (_req, res) => {
  res.json({ status: "ok", region: REGION, agentArn: AGENT_ARN ? "set" : "missing" });
});

const PORT = 3001;
app.listen(PORT, () => {
  console.log(`API server running on http://0.0.0.0:${PORT}`);
  console.log(`AGENT_ARN: ${AGENT_ARN || "(not set)"}`);
  console.log(`REGION: ${REGION}`);
});
