#!/usr/bin/env python3
"""
List all tags from Readwise Reader library.

This script retrieves all tags from your Reader library.

USAGE:
    python scripts/list_tags.py [OPTIONS]

OPTIONS:
    --cursor <str>    Pagination cursor for next page
    --all             Fetch all pages automatically
    --output <str>    Output format: json (default), simple
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

    With --output simple:
    tag-key: Tag Name
    tag-key-2: Another Tag

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

    # Simple output format
    python scripts/list_tags.py --output simple

REFERENCES:
    - Usage Guide: references/usage-guide.md
"""

import argparse
import sys
from pathlib import Path

# Add scripts folder to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils import (
    create_client,
    handle_response,
    output_error,
    output_json,
)


def fetch_tags_page(client, cursor: str = None) -> dict:
    """Fetch a single page of tags."""
    params = {}
    if cursor:
        params["pageCursor"] = cursor

    response = client.get("/tags/", params=params)
    return handle_response(response, client)


def fetch_all_tags(client) -> dict:
    """Fetch all tags across all pages."""
    all_tags = []
    cursor = None

    while True:
        data = fetch_tags_page(client, cursor)
        all_tags.extend(data.get("results", []))
        cursor = data.get("nextPageCursor")

        if not cursor:
            break

    return {
        "count": len(all_tags),
        "results": all_tags,
    }


def format_simple(data: dict) -> str:
    """Format tags as simple key: name output."""
    lines = []
    for tag in data.get("results", []):
        lines.append(f"{tag.get('key', '')}: {tag.get('name', '')}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="List all tags from Readwise Reader library",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--cursor", help="Pagination cursor")
    parser.add_argument("--all", action="store_true", help="Fetch all pages")
    parser.add_argument("--output", choices=["json", "simple"], default="json", help="Output format")

    args = parser.parse_args()

    with create_client() as client:
        try:
            if args.all:
                data = fetch_all_tags(client)
            elif args.cursor:
                data = fetch_tags_page(client, args.cursor)
            else:
                data = fetch_tags_page(client)

            if args.output == "simple":
                print(format_simple(data))
            else:
                output_json(data)

        except Exception as e:
            if hasattr(e, "to_json"):
                output_error(e)
            raise


if __name__ == "__main__":
    main()
