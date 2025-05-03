# Reader MCP Server

<a href="https://glama.ai/mcp/servers/@xinthink/reader-mcp-server">
  <img width="380" height="200" src="https://glama.ai/mcp/servers/@xinthink/reader-mcp-server/badge" alt="Reader MCP Server" />
</a>

## Overview
A Model Context Protocol (MCP) server that seamlessly integrates with your [Readwise Reader](https://readwise.io/reader_api) library. This server enables MCP-compatible clients like Claude and VS Code to interact with your Reader library, providing capabilities for document listing, retrieval, and updates. It serves as a bridge between MCP clients and your personal knowledge repository in Readwise Reader.

## Components

### Tools

- `list_documents`
  - List documents from Reader with flexible filtering and pagination.
  - **Input:**
    - `location` (string, optional): Folder to filter by. One of `new`, `later`, `shortlist`, `archive`, `feed`.
    - `updatedAfter` (string, optional): Only return documents updated after this ISO8601 timestamp.
    - `withContent` (boolean, optional): If true, include HTML content in results (default: false).
    - `pageCursor` (string, optional): Pagination cursor for fetching the next page.
  - **Returns:**
    - JSON object with a list of documents, each including metadata and (optionally) content, plus pagination info.

## Usage with MCP Clients

### Claude Desktop / VS Code / Other MCP Clients
To use this server with Claude Desktop, VS Code, or any MCP-compatible client, add the following configuration to your client settings (e.g., `claude_desktop_config.json` or `.vscode/mcp.json`):

#### uv (local server)
```json
{
  "mcpServers": {
    "reader": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/your/reader/server",
        "run",
        "main.py"
      ],
      "env": {
        "ACCESS_TOKEN": "your_readwise_access_token"
      }
    }
  }
}
```
- Replace `/absolute/path/to/your/reader/server` with the actual path to this project directory.
- Replace `your_readwise_access_token` with your actual Readwise Reader API access token.
- Alternatively, you can specify the `ACCESS_TOKEN` in an `.env` file located in the project directory.

---
For more information, see the [Readwise Reader API documentation](https://readwise.io/reader_api) and [MCP documentation](https://modelcontextprotocol.io/).
