# Reader Scripts Usage Guide

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

---

## Setup

Install the required dependencies before using the scripts:

```bash
cd skills/reader/scripts
pip install -r requirements.txt
```

The scripts require:
- `httpx` - Async HTTP client for API requests
- `python-dotenv` - Environment variable management

---

## Scripts Overview

| Script | Purpose | Input Method |
|--------|---------|--------------|
| `list_documents.py` | Query documents | CLI flags |
| `create_document.py` | Save URL/content | JSON payload |
| `update_document.py` | Modify single document | JSON payload |
| `bulk_update_documents.py` | Modify multiple documents | JSON payload |
| `delete_document.py` | Remove documents | JSON payload |
| `list_tags.py` | List all tags | CLI flags |

---

## list_documents.py

Query documents from your Reader library with flexible filtering.

### Usage

```bash
python scripts/list_documents.py [OPTIONS]
```

### CLI Options

| Option | Type | Default | Valid Values | Description |
|--------|------|---------|--------------|-------------|
| `--location` | string | - | `new`, `later`, `shortlist`, `archive`, `feed` | Filter by location |
| `--category` | string | - | `article`, `email`, `rss`, `highlight`, `note`, `pdf`, `epub`, `tweet`, `video` | Filter by category |
| `--tag` | string[] | - | Any tag key | Filter by tag (max 5, can repeat) |
| `--updated-after` | ISO 8601 | - | Date string | Filter by update time |
| `--id` | string | - | Document ID | Get specific document |
| `--limit` | integer | 20 | 1-100 | Max results per page |
| `--with-content` | boolean | false | - | Include HTML content |
| `--cursor` | string | - | - | Pagination cursor |
| `--all` | boolean | false | - | Fetch all pages (uses JSON Lines format) |
| `--output` | string | stdout | File path | Output file (`.json` for standard, `.jsonl` for --all) |

### Output Schema

**Standard Mode (default):**

```json
{
  "count": 2304,
  "fetched": 20,
  "nextPageCursor": "abc123...",
  "results": [
    {
      "id": "<document id>",
      "title": "<document title>",
      "url": "<original url>",
      "source_url": "<reader url>",
      "author": "<author name>",
      "source": "<source name>",
      "category": "<content category>",
      "location": "<current location>",
      "tags": {"tag_key": {"name": "Tag Name"}},
      "site_name": "<website name>",
      "word_count": <word count>,
      "notes": "<user notes>",
      "summary": "<document summary>",
      "published_date": "<publication date>",
      "image_url": "<cover image url>",
      "reading_progress": <0.0-1.0>,
      "created_at": "<ISO 8601 datetime>",
      "updated_at": "<ISO 8601 datetime>",
      "saved_at": "<ISO 8601 datetime>"
    }
  ]
}
```

**JSON Lines Mode (--all flag):**

When using `--all`, output uses [JSON Lines](https://jsonlines.org/) format for efficient streaming:

```
Line 1 (metadata): {"metadata": {"total": 2304, "query": {"location": "archive", ...}, "timestamp": "2026-03-10T15:30:00Z"}}
Line 2-N (data): {"id": "...", "title": "...", ...}
Last line (summary): {"summary": {"fetched": 2304, "end": true}}
```

Benefits of JSON Lines format:
- **Memory efficient**: Items are streamed one at a time, never buffered in memory
- **Pipe-friendly**: Each line is valid JSON, works with `grep`, `jq`, etc.
- **Progressive processing**: Consumers can process items as they arrive

To extract only data lines (skip metadata/summary):
```bash
# Skip first and last lines
python scripts/list_documents.py --all | tail -n +2 | head -n -1

# Or filter by structure
python scripts/list_documents.py --all | grep -v '"metadata"\|"summary"'
```

### Examples

```bash
# List documents in "later" folder (standard JSON to stdout)
python scripts/list_documents.py --location later

# Filter by category
python scripts/list_documents.py --category article

# Filter by multiple tags
python scripts/list_documents.py --tag important --tag reference

# Standard mode to file (complete JSON)
python scripts/list_documents.py --location later --output later.json

# Fetch all documents in archive (JSON Lines to stdout)
python scripts/list_documents.py --location archive --all

# Fetch all and write to file
python scripts/list_documents.py --location archive --all --output archive.jsonl

# Pipe to grep for filtering
python scripts/list_documents.py --all | grep "python"

# Pipe to jq for JSON processing (skip metadata/summary)
python scripts/list_documents.py --all | tail -n +2 | head -n -1 | jq '.title'
```

---

## create_document.py

Save a new URL or content to your Reader library.

### Usage

```bash
echo '<json>' | python scripts/create_document.py
python scripts/create_document.py --file payload.json
```

### Input Schema

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|--------------|-------------|
| `url` | string | **Yes** | Valid URL | Document URL to save |
| `title` | string | No | Text | Override title |
| `author` | string | No | Text | Override author |
| `summary` | string | No | Text | Override summary |
| `published_date` | ISO 8601 | No | `2020-07-14T20:11:24+00:00` | Publication date |
| `image_url` | string | No | Valid URL | Cover image URL |
| `location` | string | No | `new`, `later`, `archive`, `feed` | Initial location |
| `category` | string | No | `article`, `email`, `rss`, `highlight`, `note`, `pdf`, `epub`, `tweet`, `video` | Category |
| `tags` | string[] | No | Array of strings | Tags to apply |
| `notes` | string | No | Text | Personal notes |
| `html` | string | No | HTML | Custom HTML content |
| `should_clean_html` | boolean | No | `true`/`false` | Auto-clean HTML (default: true) |

### Output Schema

```json
{
  "id": "...",
  "url": "...",
  "title": "...",
  "status": "created" | "updated"
}
```

### Examples

```bash
# Save a URL
echo '{"url": "https://example.com/article"}' | python scripts/create_document.py

# Save with title and tags
echo '{"url": "https://example.com", "title": "My Article", "tags": ["important"]}' | python scripts/create_document.py
```

---

## update_document.py

Update a single document in your Reader library.

### Usage

```bash
echo '<json>' | python scripts/update_document.py
python scripts/update_document.py --file payload.json
```

### Input Schema

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|--------------|-------------|
| `id` | string | **Yes** | Document ID | ID of document to update |
| `title` | string | No | Text | New title |
| `author` | string | No | Text | New author |
| `summary` | string | No | Text | New summary |
| `published_date` | ISO 8601 | No | `2020-07-14T20:11:24+00:00` | New publication date |
| `image_url` | string | No | Valid URL | New cover image |
| `location` | string | No | `new`, `later`, `shortlist`, `archive`, `feed` | New location |
| `category` | string | No | `article`, `email`, `rss`, `highlight`, `note`, `pdf`, `epub`, `tweet`, `video` | New category |
| `tags` | string[] | No | Array of strings | Replace all tags |
| `notes` | string | No | Text | Replace notes (empty to clear) |
| `seen` | boolean | No | `true`/`false` | Mark as seen/unseen |

### Output Schema

```json
{
  "id": "...",
  "updated": true,
  "document": {...}
}
```

### Examples

```bash
# Archive a document
echo '{"id": "abc123", "location": "archive"}' | python scripts/update_document.py

# Update tags and notes
echo '{"id": "abc123", "tags": ["read"], "notes": "Great reference"}' | python scripts/update_document.py
```

---

## bulk_update_documents.py

Update multiple documents in a single request (max 50).

### Usage

```bash
echo '<json>' | python scripts/bulk_update_documents.py
python scripts/bulk_update_documents.py --file payload.json
```

### Input Schema

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|--------------|-------------|
| `updates` | array | **Yes** | Array of update objects | Updates to apply (max 50) |

#### Update Object Fields

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|--------------|-------------|
| `id` | string | **Yes** | Document ID | Document to update |
| `title` | string | No | Text | New title |
| `location` | string | No | `new`, `later`, `shortlist`, `archive`, `feed` | New location |
| `category` | string | No | `article`, `email`, `rss`, `highlight`, `note`, `pdf`, `epub`, `tweet`, `video` | New category |
| `tags` | string[] | No | Array of strings | Replace all tags |
| `notes` | string | No | Text | Replace notes |
| `seen` | boolean | No | `true`/`false` | Mark as seen/unseen |

### Output Schema

```json
{
  "count": 2,
  "results": [{"id": "...", "updated": true}]
}
```

### Examples

```bash
# Archive multiple documents
echo '{"updates": [{"id": "abc", "location": "archive"}, {"id": "def", "location": "archive"}]}' | python scripts/bulk_update_documents.py
```

---

## delete_document.py

Remove one or more documents from your Reader library.

### Usage

```bash
echo '<json>' | python scripts/delete_document.py
python scripts/delete_document.py --file payload.json
```

### Input Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ids` | string[] | **Yes** | Array of document IDs to delete |

### Output Schema

```json
{
  "deleted": 2,
  "ids": ["id1", "id2"]
}
```

### Examples

```bash
# Delete documents
echo '{"ids": ["abc123", "def456"]}' | python scripts/delete_document.py
```

---

## list_tags.py

List all tags in your Reader library.

### Usage

```bash
python scripts/list_tags.py [OPTIONS]
```

### CLI Options

| Option | Type | Description |
|--------|------|-------------|
| `--cursor` | string | Pagination cursor |
| `--all` | boolean | Fetch all pages (uses JSON Lines format) |
| `--output` | string | Output file (`.json` for standard, `.jsonl` for --all) |

### Output Schema

**Standard Mode (default):**

```json
{
  "count": 15,
  "results": [{"key": "tag", "name": "Tag"}]
}
```

**JSON Lines Mode (--all flag):**

```
Line 1 (metadata): {"metadata": {"total": 100, "query": {}, "timestamp": "2026-03-10T15:30:00Z"}}
Line 2-N (data): {"key": "tag-key", "name": "Tag Name"}
Last line (summary): {"summary": {"fetched": 100, "end": true}}
```

**With --output flag:**

- Standard mode: Writes complete JSON object to file
- `--all` mode: Streams JSON Lines format to file

### Examples

```bash
# List all tags (standard JSON to stdout)
python scripts/list_tags.py

# Standard mode to file
python scripts/list_tags.py --output tags.json

# Fetch all tags (JSON Lines to stdout)
python scripts/list_tags.py --all

# Fetch all and write to file
python scripts/list_tags.py --all --output tags.jsonl

# Pipe to grep for filtering
python scripts/list_tags.py --all | grep "important"
```

---

## Error Handling

### Exit Codes

| Code | Meaning | Action |
|------|---------|--------|
| 0 | Success | Parse stdout |
| 1 | API error | Check stderr, retry if transient |
| 2 | Auth error | Verify `READWISE_ACCESS_TOKEN` is correct |
| 3 | Rate limit | Wait and retry (scripts auto-retry, this means exhausted retries) |
| 4 | Invalid input | Fix payload or CLI flags |

### Error Output Format

Errors are written to stderr in JSON format:

```json
{
  "error": {
    "type": "validation_error",
    "message": "Missing required field: url",
    "hint": "Provide a URL to save in the payload"
  }
}
```

Common error types:
- `authentication_error`: Token missing or invalid
- `validation_error`: Invalid input payload/flags
- `not_found_error`: Document not found
- `rate_limit_error`: Rate limit exceeded
- `server_error`: API server issue

---

## Rate Limits

| Error Type | Retry Location | Max Retries | Backoff | Exit Code |
|------------|----------------|-------------|---------|-----------|
| **429** (rate limit) | Script-level (`--all` only) | 3 | `Retry-After` header (60s fallback) | 3 if exhausted |
| **5xx** (server) | `handle_response()` (auto) | 3 | Exponential: 2^retry (1s, 2s, 4s) | 1 if exhausted |

**Key points:**
- 429: `handle_response()` raises `RateLimitError` immediately; scripts with `--all` implement retry loop
- 5xx: Auto-retried in `handle_response()` before raising `APIError`
- Retry counter resets on success

---

## Pagination

### list_documents.py

Use `--cursor` for manual pagination or `--all` to fetch all pages automatically:

```bash
# Manual pagination (standard JSON output)
python scripts/list_documents.py --location later
# Use nextPageCursor from response for next page
python scripts/list_documents.py --location later --cursor "abc123..."

# Automatic with JSON Lines streaming
python scripts/list_documents.py --location later --all

# Automatic with file output
python scripts/list_documents.py --location later --all --output later.jsonl
```

### list_tags.py

Same pagination pattern with `--cursor` and `--all` flags:

```bash
# Single page (standard JSON)
python scripts/list_tags.py

# All pages (JSON Lines streaming)
python scripts/list_tags.py --all

# All pages to file
python scripts/list_tags.py --all --output tags.jsonl
```

### Output Format Comparison

| Mode | Format | Use Case |
|------|--------|----------|
| Standard (no flags) | JSON array | Small result sets, need random access |
| `--all` | JSON Lines | Large datasets, streaming, piping to other tools |
| `--all --output file.jsonl` | JSON Lines to file | Archiving, processing large datasets later |
