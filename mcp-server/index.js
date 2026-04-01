import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio";
import { createMcpServer } from "./server_core.js";

const server = createMcpServer();
const transport = new StdioServerTransport();
await server.connect(transport);
console.log("MCP stdio server is running...");

