#!/usr/bin/env python3
"""
Bulk update multiple documents in Readwise Reader.

This script updates multiple documents in a single request using a JSON payload.
Maximum 50 documents can be updated per request.

USAGE:
    echo '<json_payload>' | python scripts/bulk_update_documents.py
    python scripts/bulk_update_documents.py --file payload.json
    python scripts/bulk_update_documents.py --file payload.json --dry-run

OPTIONS:
    --file <path>    Read JSON payload from file (default: stdin)
    --dry-run        Validate payload without updating documents
    --help           Show this help message

INPUT PAYLOAD (stdin or --file):
    {
        "updates": [                          // REQUIRED - Array of updates (max 50)
            {
                "id": "doc-id-1",             // REQUIRED - Document ID
                "location": "archive",        // optional - new, later, shortlist, archive, feed
                "tags": ["tag1", "tag2"],     // optional - Replace tags
                "notes": "...",               // optional - Update notes
                "seen": true                  // optional - Mark as seen/unseen
            },
            {
                "id": "doc-id-2",
                "location": "later",
                "tags": ["read-later"]
            }
        ]
    }

    Each update object must have an "id" field. Other fields are optional.
    Tags specified will REPLACE existing tags for that document.

OUTPUT:
    JSON object to stdout:
    {
        "count": 2,
        "results": [
            {"id": "doc-id-1", "updated": true},
            {"id": "doc-id-2", "updated": true}
        ]
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
    10 requests per minute. Script handles retries automatically.

EXAMPLES:
    # Archive multiple documents
    echo '{
        "updates": [
            {"id": "abc123", "location": "archive"},
            {"id": "def456", "location": "archive"}
        ]
    }' | python scripts/bulk_update_documents.py

    # Bulk update from file
    python scripts/bulk_update_documents.py --file updates.json

    # Validate without updating
    python scripts/bulk_update_documents.py --file updates.json --dry-run

REFERENCES:
    - Usage Guide: references/usage-guide.md
"""

import argparse
import sys
from pathlib import Path

# Add scripts folder to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils import (
    APIError,
    EXIT_INVALID_ARGS,
    create_client,
    output_error,
    output_json,
    read_payload,
)


def validate_payload(payload: dict) -> None:
    """Validate the bulk update payload."""
    if "updates" not in payload:
        raise APIError(
            type="validation_error",
            message="Missing required field: updates",
            hint="Provide an 'updates' array with document updates",
            exit_code=EXIT_INVALID_ARGS,
        )

    updates = payload["updates"]
    if not isinstance(updates, list):
        raise APIError(
            type="validation_error",
            message="'updates' must be an array",
            exit_code=EXIT_INVALID_ARGS,
        )

    if len(updates) == 0:
        raise APIError(
            type="validation_error",
            message="'updates' array cannot be empty",
            exit_code=EXIT_INVALID_ARGS,
        )

    if len(updates) > 50:
        raise APIError(
            type="validation_error",
            message=f"Too many updates: {len(updates)}. Maximum is 50.",
            hint="Split your updates into multiple requests",
            exit_code=EXIT_INVALID_ARGS,
        )

    valid_locations = {"new", "later", "shortlist", "archive", "feed"}
    for i, update in enumerate(updates):
        if "id" not in update:
            raise APIError(
                type="validation_error",
                message=f"Update at index {i} missing required field: id",
                exit_code=EXIT_INVALID_ARGS,
            )

        if update.get("location") and update["location"] not in valid_locations:
            raise APIError(
                type="validation_error",
                message=f"Invalid location at index {i}: {update['location']}",
                hint=f"Must be one of: {', '.join(valid_locations)}",
                exit_code=EXIT_INVALID_ARGS,
            )


def bulk_update_documents(client, payload: dict) -> dict:
    """Bulk update documents via the API."""
    client.patch("/bulk_update/", json=payload)

    # Format response
    results = []
    for update in payload["updates"]:
        results.append({"id": update["id"], "updated": True})

    return {
        "count": len(results),
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Bulk update multiple documents in Readwise Reader",
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
        return  # Never reached, but makes type checker happy

    # Validate payload
    try:
        validate_payload(payload)
    except APIError as e:
        output_error(e)
        return  # Never reached, but makes type checker happy

    # Dry run - just validate
    if args.dry_run:
        output_json({"status": "valid", "updates_count": len(payload["updates"])})
        return

    # Bulk update documents
    with create_client() as client:
        try:
            result = bulk_update_documents(client, payload)
            output_json(result)
        except APIError as e:
            output_error(e)


if __name__ == "__main__":
    main()
