---
name: reader
description: |
  Interact with Readwise Reader library to list, create, update, and delete documents. Use when the user wants to manage their saved articles, reading lists, or retrieve document content. Triggers on mentions of "Readwise Reader", "Reader API", or requests to save/read/archive web articles.
---

# Reader

Interact with Readwise Reader library using executable scripts.

## Quick Start

All Reader operations are available as scripts in the `scripts/` subdirectory:

| Script | Purpose | Input |
|--------|---------|-------|
| `list_documents.py` | Query documents | CLI flags |
| `create_document.py` | Save URL/content | JSON payload |
| `update_document.py` | Modify document | JSON payload |
| `bulk_update_documents.py` | Batch modify (max 50) | JSON payload |
| `delete_document.py` | Remove documents | JSON payload |
| `list_tags.py` | List all tags | CLI flags |

## Authentication

Set the `READWISE_ACCESS_TOKEN` environment variable using one of these methods:

### Method 1: Using a `.env` file

Create a `.env` file in the project directory:

```bash
READWISE_ACCESS_TOKEN=your-token-here
```

The scripts automatically load environment variables from `.env` using `python-dotenv`.

### Method 2: Command line

**Export in shell:**
```bash
export READWISE_ACCESS_TOKEN=your-token-here
```

**Or inline for a single command:**
```bash
READWISE_ACCESS_TOKEN=your-token-here python scripts/list_documents.py
```

### Getting your token

Get your token from: https://readwise.io/access_token

## Setup

Install the required dependencies before using the scripts:

```bash
pip install -r scripts/requirements.txt
```

The scripts require:
- `httpx` - Async HTTP client for API requests
- `python-dotenv` - Environment variable management

## Common Workflows

### List documents in a folder

```bash
python scripts/list_documents.py --location later --limit 10
```

### Save a URL with tags

```bash
echo '{"url": "https://example.com/article", "tags": ["important"]}' | python scripts/create_document.py
```

### Archive a document

```bash
echo '{"id": "doc-id", "location": "archive"}' | python scripts/update_document.py
```

### Bulk archive multiple documents

```bash
echo '{"updates": [{"id": "doc1", "location": "archive"}, {"id": "doc2", "location": "archive"}]}' | python scripts/bulk_update_documents.py
```

## Error Handling

| Exit Code | Meaning | Action |
|-----------|---------|--------|
| 0 | Success | Parse stdout |
| 1 | API error | Check stderr for details |
| 2 | Auth error | Verify `READWISE_ACCESS_TOKEN` |
| 3 | Rate limit | Wait and retry |
| 4 | Invalid input | Fix payload/flags |

Errors are written to stderr in JSON format:
```json
{"error": {"type": "...", "message": "...", "hint": "..."}}
```

## Rate Limits

Scripts automatically handle retries for rate limits (429) and server errors (5xx).
No action needed unless exit code 3.

## Resources

- **Usage Guide**: [references/usage-guide.md](references/usage-guide.md)
