import { randomUUID } from "node:crypto";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { createMcpExpressApp } from "@modelcontextprotocol/sdk/server/express.js";
import { isInitializeRequest } from "@modelcontextprotocol/sdk/types.js";
import { createMcpServer } from "./server_core.js";

const PORT = Number(process.env.PORT || 3001);
const MCP_PATH = "/mcp";
const sessionHeader = (value) => (Array.isArray(value) ? value[0] : value);

const transports = {};
const app = createMcpExpressApp();

app.post(MCP_PATH, async (req, res) => {
  try {
    const sessionId = sessionHeader(req.headers["mcp-session-id"]);
    let transport;

    if (sessionId && transports[sessionId]) {
      transport = transports[sessionId];
    } else if (!sessionId && isInitializeRequest(req.body)) {
      transport = new StreamableHTTPServerTransport({
        sessionIdGenerator: () => randomUUID(),
        onsessioninitialized: (sid) => {
          transports[sid] = transport;
        }
      });
      transport.onclose = async () => {
        if (transport?.sessionId) delete transports[transport.sessionId];
      };
      const server = createMcpServer();
      await server.connect(transport);
      await transport.handleRequest(req, res, req.body);
      return;
    } else {
      res.status(400).json({
        jsonrpc: "2.0",
        error: { code: -32000, message: "Bad Request: No valid session ID provided" },
        id: null
      });
      return;
    }

    await transport.handleRequest(req, res, req.body);
  } catch (error) {
    if (!res.headersSent) {
      res.status(500).json({
        jsonrpc: "2.0",
        error: { code: -32603, message: "Internal server error" },
        id: null
      });
    }
  }
});

app.get(MCP_PATH, async (req, res) => {
  const sessionId = sessionHeader(req.headers["mcp-session-id"]);
  if (!sessionId || !transports[sessionId]) {
    res.status(400).send("Invalid or missing session ID");
    return;
  }
  await transports[sessionId].handleRequest(req, res);
});

app.delete(MCP_PATH, async (req, res) => {
  const sessionId = sessionHeader(req.headers["mcp-session-id"]);
  if (!sessionId || !transports[sessionId]) {
    res.status(400).send("Invalid or missing session ID");
    return;
  }
  await transports[sessionId].handleRequest(req, res);
});

app.listen(PORT, (error) => {
  if (error) {
    console.error("Failed to start Streamable HTTP MCP server:", error);
    process.exit(1);
  }
  console.log(`MCP Streamable HTTP server listening on :${PORT}${MCP_PATH}`);
});
