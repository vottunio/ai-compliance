import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { createMcpServer } from "./server_core.js";

const server = createMcpServer();
const transport = new StdioServerTransport();
await server.connect(transport);
console.error("MCP stdio server is running...");
