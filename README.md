# Reader MCP Server

## Overview
A Model Context Protocol (MCP) server implementation that exposes your [Readwise Reader](https://readwise.io/reader_api) documents as resources. This server enables unified retrieval and integration of your reading highlights and documents from Readwise Reader.

## Components
- Exposes Readwise Reader documents as MCP resources
- Supports filtering documents by folder (`location`) and time (`after`)
- Returns standard JSON responses with pagination support

### Resources
- Retrieve documents in a specific folder and after a specific time:
  ```
  reader://documents/location={location};after={after}
  ```
  - `location` options: `new`, `later`, `shortlist`, `archive`, `feed`
  - `after`: ISO 8601 timestamp, e.g. `2025-01-01T00:00:00Z`

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
