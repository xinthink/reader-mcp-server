#!/usr/bin/env python3
"""
Delete documents from Readwise Reader.

This script removes one or more documents from your Reader library using a JSON payload.

USAGE:
    echo '<json_payload>' | python scripts/delete_document.py
    python scripts/delete_document.py --file payload.json
    python scripts/delete_document.py --file payload.json --confirm

OPTIONS:
    --file <path>    Read JSON payload from file (default: stdin)
    --confirm        Skip confirmation prompt
    --help           Show this help message

INPUT PAYLOAD (stdin or --file):
    {
        "ids": ["id1", "id2", ...]    // REQUIRED - Array of document IDs to delete
    }

OUTPUT:
    JSON object to stdout:
    {
        "deleted": 2,
        "ids": ["id1", "id2"]
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
    20 requests per minute. Script handles retries automatically.

EXAMPLES:
    # Delete a single document
    echo '{"ids": ["abc123"]}' | python scripts/delete_document.py --confirm

    # Delete multiple documents
    echo '{"ids": ["abc123", "def456", "ghi789"]}' | python scripts/delete_document.py

    # Delete from file
    python scripts/delete_document.py --file to_delete.json --confirm

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
    handle_response,
    raise_error,
    output_json,
    read_payload,
)


def validate_payload(payload: dict) -> None:
    """Validate the delete document payload."""
    if "ids" not in payload:
        raise APIError(
            type="validation_error",
            message="Missing required field: ids",
            hint="Provide an 'ids' array with document IDs to delete",
            exit_code=EXIT_INVALID_ARGS,
        )

    ids = payload["ids"]
    if not isinstance(ids, list):
        raise APIError(
            type="validation_error",
            message="'ids' must be an array",
            exit_code=EXIT_INVALID_ARGS,
        )

    if len(ids) == 0:
        raise APIError(
            type="validation_error",
            message="'ids' array cannot be empty",
            exit_code=EXIT_INVALID_ARGS,
        )


def delete_document(client, doc_id: str) -> bool:
    """Delete a single document via the API."""
    response = client.delete(f"/delete/{doc_id}/")
    handle_response(response, client)
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Delete documents from Readwise Reader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--file", help="Read JSON payload from file (default: stdin)")
    parser.add_argument("--confirm", action="store_true", help="Skip confirmation prompt")

    args = parser.parse_args()

    # Read payload
    try:
        payload = read_payload(args.file)
    except APIError as e:
        raise_error(e)

    # Validate payload
    try:
        validate_payload(payload)
    except APIError as e:
        raise_error(e)

    ids = payload["ids"]

    # Confirmation prompt
    if not args.confirm:
        print(f"About to delete {len(ids)} document(s).", file=sys.stderr)
        response = input("Confirm? [y/N]: ")
        if response.lower() != "y":
            print("Cancelled.", file=sys.stderr)
            output_json({"deleted": 0, "ids": [], "status": "cancelled"})
            return

    # Delete documents
    deleted_ids = []
    with create_client() as client:
        for doc_id in ids:
            try:
                delete_document(client, doc_id)
                deleted_ids.append(doc_id)
            except APIError as e:
                # Log error but continue with remaining documents
                print(f"Error deleting {doc_id}: {e.message}", file=sys.stderr)

    output_json({
        "deleted": len(deleted_ids),
        "ids": deleted_ids,
    })


if __name__ == "__main__":
    main()
