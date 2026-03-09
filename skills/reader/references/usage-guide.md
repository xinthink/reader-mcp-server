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

## Setup

Install the required dependencies before using the scripts:

```bash
cd skills/reader/scripts
pip install -r requirements.txt
```

The scripts require:
- `httpx` - Async HTTP client for API requests
- `python-dotenv` - Environment variable management

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

## Input Schemas

### create_document.py

```json
{
  "url": "https://...",              // REQUIRED
  "title": "...",                    // optional
  "author": "...",                   // optional
  "summary": "...",                  // optional
  "published_date": "YYYY-MM-DD",    // optional
  "image_url": "...",                // optional
  "location": "new",                 // optional: new, later, archive, feed
  "category": "...",                 // optional
  "tags": ["tag1", "tag2"],          // optional
  "notes": "...",                    // optional
  "html": "...",                     // optional - custom HTML content
  "should_clean_html": true          // optional - default: true
}
```

### update_document.py

```json
{
  "id": "...",                       // REQUIRED
  "title": "...",                    // optional
  "location": "...",                 // optional: new, later, shortlist, archive, feed
  "tags": ["tag1", "tag2"],          // optional - replaces existing tags
  "notes": "...",                    // optional
  "seen": true                       // optional
}
```

### bulk_update_documents.py

```json
{
  "updates": [                       // REQUIRED, max 50 items
    {"id": "...", "location": "archive"},
    {"id": "...", "tags": ["read"]}
  ]
}
```

### delete_document.py

```json
{
  "ids": ["id1", "id2", ...]         // REQUIRED, one or more document IDs
}
```

---

## Output Schemas

### list_documents.py

```json
{
  "count": 2304,
  "fetched": 20,
  "next_cursor": "abc123...",
  "results": [
    {
      "id": "doc-id",
      "title": "Document Title",
      "url": "https://original-url.com",
      "source_url": "https://read.readwise.io/...",
      "author": "Author Name",
      "source": "Source Name",
      "category": "article",
      "location": "later",
      "tags": {"tag-key": {"name": "Tag Name"}},
      "site_name": "Website",
      "word_count": 1500,
      "notes": "User notes",
      "summary": "Document summary",
      "published_date": "2024-01-15",
      "image_url": "https://...",
      "reading_progress": 0.75,
      "created_at": "2024-01-15T10:00:00Z",
      "updated_at": "2024-01-16T15:30:00Z",
      "saved_at": "2024-01-15T10:00:00Z"
    }
  ]
}
```

**Key fields:**
- `id`: Unique document identifier (used for updates/deletes)
- `location`: Current folder (new, later, shortlist, archive, feed)
- `reading_progress`: Float 0.0-1.0
- `tags`: Object with tag keys as property names

### create_document.py

```json
{
  "id": "new-doc-id",
  "url": "https://read.readwise.io/...",
  "title": "Document Title",
  "status": "created"  // or "updated" if URL already existed
}
```

### update_document.py / bulk_update_documents.py

```json
{
  "id": "doc-id",
  "updated": true,
  "document": {...}
}
```

### delete_document.py

```json
{
  "deleted": 2,
  "ids": ["id1", "id2"]
}
```

### list_tags.py

```json
{
  "count": 15,
  "results": [
    {"key": "important", "name": "Important"},
    {"key": "read-later", "name": "Read Later"}
  ]
}
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

Scripts automatically retry on rate limits (HTTP 429) and server errors (5xx).

Built-in retry behavior:
- Max 3 retries
- Respects `Retry-After` header
- Exponential backoff for server errors

No manual intervention needed unless exit code 3 (retries exhausted).

---

## Pagination

### list_documents.py

Use `--cursor` for manual pagination or `--all` to fetch all pages automatically:

```bash
# Manual pagination
python scripts/list_documents.py --location later
# Use next_cursor from response for next page
python scripts/list_documents.py --location later --cursor "abc123..."

# Automatic (fetch all)
python scripts/list_documents.py --location later --all
```

### list_tags.py

Same pagination pattern with `--cursor` and `--all` flags.
