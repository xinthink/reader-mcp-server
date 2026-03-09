#!/usr/bin/env python3
"""
Update a document in Readwise Reader.

This script modifies an existing document using a JSON payload.

USAGE:
    echo '<json_payload>' | python scripts/update_document.py
    python scripts/update_document.py --file payload.json
    python scripts/update_document.py --file payload.json --dry-run

OPTIONS:
    --file <path>    Read JSON payload from file (default: stdin)
    --dry-run        Validate payload without updating document
    --help           Show this help message

INPUT PAYLOAD (stdin or --file):
    {
        "id": "...",                        // REQUIRED - Document ID to update
        "title": "...",                     // optional - New title
        "location": "archive",              // optional - new, later, shortlist, archive, feed
        "tags": ["tag1", "tag2"],           // optional - Replace tags (clears existing)
        "notes": "...",                     // optional - Update notes
        "seen": true                        // optional - Mark as seen/unseen
    }

    Note: Tags specified will REPLACE existing tags, not append.

OUTPUT:
    JSON object to stdout:
    {
        "id": "<document id>",
        "updated": true,
        "document": {
            "id": "...",
            "title": "...",
            "location": "...",
            "tags": {...},
            ...
        }
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
    # Archive a document
    echo '{"id": "abc123", "location": "archive"}' | python scripts/update_document.py

    # Update tags and notes
    echo '{
        "id": "abc123",
        "tags": ["read", "important"],
        "notes": "Great reference for project X"
    }' | python scripts/update_document.py

    # Mark as seen
    echo '{"id": "abc123", "seen": true}' | python scripts/update_document.py

    # Validate without updating
    python scripts/update_document.py --file update.json --dry-run

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
    """Validate the update document payload."""
    if "id" not in payload:
        raise APIError(
            type="validation_error",
            message="Missing required field: id",
            hint="Provide the document ID to update",
            exit_code=EXIT_INVALID_ARGS,
        )

    if payload.get("location"):
        valid_locations = {"new", "later", "shortlist", "archive", "feed"}
        if payload["location"] not in valid_locations:
            raise APIError(
                type="validation_error",
                message=f"Invalid location: {payload['location']}",
                hint=f"Must be one of: {', '.join(valid_locations)}",
                exit_code=EXIT_INVALID_ARGS,
            )


def update_document(client, payload: dict) -> dict:
    """Update a document via the API."""
    doc_id = payload.pop("id")
    response = client.patch(f"/update/{doc_id}/", json=payload)
    data = handle_response(response, client)

    return {
        "id": doc_id,
        "updated": True,
        "document": data,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Update a document in Readwise Reader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--file", help="Read JSON payload from file (default: stdin)")
    parser.add_argument("--dry-run", action="store_true", help="Validate without updating")

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

    # Update document
    with create_client() as client:
        try:
            result = update_document(client, payload)
            output_json(result)
        except APIError as e:
            output_error(e)


if __name__ == "__main__":
    main()
