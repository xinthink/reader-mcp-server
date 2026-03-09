#!/usr/bin/env python3
"""
Create a new document in Readwise Reader.

This script saves a URL or content to your Reader library using a JSON payload.

USAGE:
    echo '<json_payload>' | python scripts/create_document.py
    python scripts/create_document.py --file payload.json
    python scripts/create_document.py --file payload.json --dry-run

OPTIONS:
    --file <path>    Read JSON payload from file (default: stdin)
    --dry-run        Validate payload without creating document
    --help           Show this help message

INPUT PAYLOAD (stdin or --file):
    {
        "url": "https://...",              // REQUIRED - URL to save
        "title": "...",                    // optional - Override title
        "author": "...",                   // optional - Override author
        "summary": "...",                  // optional - Override summary
        "published_date": "YYYY-MM-DD",    // optional - Publication date
        "image_url": "...",                // optional - Cover image URL
        "location": "new",                 // optional - new, later, archive, feed (default: new)
        "category": "...",                 // optional - Override category
        "tags": ["tag1", "tag2"],          // optional - Tags to apply
        "notes": "...",                    // optional - Personal notes
        "html": "...",                     // optional - Custom HTML content
        "should_clean_html": true          // optional - Clean HTML (default: true)
    }

OUTPUT:
    JSON object to stdout:
    {
        "id": "<new document id>",
        "url": "<reader url>",
        "title": "<document title>",
        "status": "created" or "updated"
    }

ERRORS:
    Exit codes:
        0 - Success
        1 - API error
        2 - Authentication error
        3 - Rate limit exceeded
        4 - Invalid arguments

    Errors are written to stderr in JSON format:
    {"error": {"type": "...", "message": "...", "hint": "..."}}

AUTHENTICATION:
    Requires READWISE_ACCESS_TOKEN environment variable.
    Get token from: https://readwise.io/access_token

RATE LIMITS:
    50 requests per minute. Script handles retries automatically.

EXAMPLES:
    # Save a URL
    echo '{"url": "https://example.com/article"}' | python scripts/create_document.py

    # Save with title and tags
    echo '{
        "url": "https://example.com/article",
        "title": "My Article",
        "tags": ["important", "reference"]
    }' | python scripts/create_document.py

    # Save from file with custom location
    python scripts/create_document.py --file article.json

    # Validate without creating
    python scripts/create_document.py --file article.json --dry-run

REFERENCES:
    - Usage Guide: references/usage-guide.md
"""

import argparse
import json
import sys
from pathlib import Path

# Add scripts folder to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils import (
    APIError,
    EXIT_INVALID_ARGS,
    create_client,
    handle_response,
    output_error,
    output_json,
    read_payload,
)


def validate_payload(payload: dict) -> None:
    """Validate the create document payload."""
    if "url" not in payload:
        raise APIError(
            type="validation_error",
            message="Missing required field: url",
            hint="Provide a URL to save in the payload",
            exit_code=EXIT_INVALID_ARGS,
        )

    if payload.get("location"):
        valid_locations = {"new", "later", "archive", "feed"}
        if payload["location"] not in valid_locations:
            raise APIError(
                type="validation_error",
                message=f"Invalid location: {payload['location']}",
                hint=f"Must be one of: {', '.join(valid_locations)}",
                exit_code=EXIT_INVALID_ARGS,
            )


def create_document(client, payload: dict) -> dict:
    """Create a document via the API."""
    response = client.post("/save/", json=payload)
    data = handle_response(response, client)

    return {
        "id": data.get("id"),
        "url": data.get("url"),
        "title": data.get("title"),
        "status": "created" if response.status_code == 201 else "updated",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Create a new document in Readwise Reader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--file", help="Read JSON payload from file (default: stdin)")
    parser.add_argument("--dry-run", action="store_true", help="Validate without creating")

    args = parser.parse_args()

    # Read payload
    try:
        payload = read_payload(args.file)
    except APIError as e:
        output_error(e)

    # Validate payload
    try:
        validate_payload(payload)
    except APIError as e:
        output_error(e)

    # Dry run - just validate
    if args.dry_run:
        output_json({"status": "valid", "payload": payload})
        return

    # Create document
    with create_client() as client:
        try:
            result = create_document(client, payload)
            output_json(result)
        except APIError as e:
            output_error(e)


if __name__ == "__main__":
    main()
