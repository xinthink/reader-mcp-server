# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Model Context Protocol (MCP) server that integrates with Readwise Reader API. It exposes a `list_documents` tool that allows MCP-compatible clients like Claude Desktop to interact with a user's Readwise Reader library.

## Commands for Development

### Running the Server

To run the server locally:
```bash
uv run main.py
```

### Dependencies

This project uses `uv` for dependency management. Key dependencies include:
- `mcp[cli]` - The Model Context Protocol Python SDK
- `httpx` - For async HTTP requests to the Readwise API
- `dotenv` - For loading environment variables

To install dependencies:
```bash
uv sync
```

### Environment Setup

The server requires an `ACCESS_TOKEN` environment variable with a Readwise Reader API token. This can be provided either:
1. As an environment variable
2. In a `.env` file in the project directory

## Code Architecture

### Core Components

1. **main.py** - The main server implementation:
   - Uses FastMCP from the MCP Python SDK
   - Implements the `list_documents` tool
   - Manages the Readwise API client lifecycle
   - Handles parameter validation and API communication

2. **models.py** - Data models:
   - `ReaderDocument` - Represents a document from Readwise Reader
   - `ListDocumentResponse` - Response format for the document list API

### Key Implementation Details

- The server uses the FastMCP framework which handles all MCP protocol details
- It connects to the Readwise Reader API at `https://readwise.io/api/v3`
- The `list_documents` tool supports filtering by location, update time, content inclusion, and pagination
- Authentication is handled via the ACCESS_TOKEN environment variable
- The server implements proper error handling and logging

### MCP Integration

The server exposes one tool:
- `list_documents` - Lists documents from the Readwise Reader library with flexible filtering options

This follows the MCP pattern where tools allow LLMs to take actions (in this case, retrieving document information from an external API).

## Reader Skill

This repository also includes a standalone skill (`skills/reader/` directory) that provides equivalent functionality through direct API knowledge rather than MCP server integration.

### Skill Structure

```
skills/reader/
├── SKILL.md              # Main skill file with frontmatter
└── references/
    ├── api-reference.md  # Complete API documentation
    ├── authentication.md # Token setup guide
    ├── rate-limits.md    # Rate limiting info
    ├── list-documents.md # List API examples
    ├── create-document.md # Save API examples
    └── update-document.md # Update/Delete examples
```

### Installation

The skill can be installed via:
```bash
npx skills add ./skills/reader
```

Or manually linked:
```bash
ln -s $(pwd)/skills/reader ~/.claude/skills/reader
```

### Key Differences from MCP Server

- **MCP Server**: Programmatic tool for MCP-compatible clients (Claude Desktop, VS Code)
- **Skill**: Knowledge package that teaches agents to use Reader API directly

Both serve the same purpose but through different integration patterns.