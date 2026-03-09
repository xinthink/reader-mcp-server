#!/usr/bin/env python3
"""
List all tags from Readwise Reader library.

This script retrieves all tags from your Reader library.

USAGE:
    python scripts/list_tags.py [OPTIONS]

OPTIONS:
    --cursor <str>    Pagination cursor for next page
    --all             Fetch all pages automatically
    --help            Show this help message

OUTPUT:
    JSON object to stdout:
    {
        "count": <total tags>,
        "results": [
            {
                "key": "tag-key",
                "name": "Tag Name"
            }
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
    20 requests per minute. Script handles retries automatically.

EXAMPLES:
    # List all tags
    python scripts/list_tags.py

    # Fetch all pages
    python scripts/list_tags.py --all
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Optional

# Add scripts folder to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils import (
    RateLimitError,
    create_client,
    handle_response,
    raise_error,
    output_json,
)


def fetch_tags_page(client, cursor: Optional[str] = None) -> dict:
    """Fetch a single page of tags."""
    params = {}
    if cursor:
        params["pageCursor"] = cursor

    response = client.get("/tags/", params=params)
    return handle_response(response, client)


def fetch_all_tags(client) -> dict:
    """Fetch all tags across all pages with rate limit retry logic."""
    all_tags = []
    cursor: Optional[str] = None

    while True:
        try:
            data = fetch_tags_page(client, cursor)
        except RateLimitError as e:
            # Sleep for retry_after_seconds and retry
            time.sleep(e.retry_after_seconds)
            data = fetch_tags_page(client, cursor)

        all_tags.extend(data.get("results", []))
        cursor = data.get("nextPageCursor")

        if not cursor:
            break

    return {
        "count": len(all_tags),
        "results": all_tags,
    }


def main():
    parser = argparse.ArgumentParser(
        description="List all tags from Readwise Reader library",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--cursor", help="Pagination cursor")
    parser.add_argument("--all", action="store_true", help="Fetch all pages")

    args = parser.parse_args()

    with create_client() as client:
        try:
            if args.all:
                data = fetch_all_tags(client)
            elif args.cursor:
                data = fetch_tags_page(client, args.cursor)
            else:
                data = fetch_tags_page(client)

            output_json(data)

        except RateLimitError as e:
            raise_error(e)
        except Exception as e:
            if hasattr(e, "to_json"):
                raise_error(e)  # type: ignore[arg-type]
            raise


if __name__ == "__main__":
    main()
