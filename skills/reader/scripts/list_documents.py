#!/usr/bin/env python3
"""
List documents from Readwise Reader library.

This script retrieves documents from your Reader library with flexible
filtering options via CLI flags.

USAGE:
    python scripts/list_documents.py [OPTIONS]

OPTIONS:
    --location <str>       Filter by location: new, later, shortlist, archive, feed
    --category <str>       Filter by category (rss, email, article, pdf, etc.)
    --tag <str>            Filter by tag (can be specified multiple times, max 5)
    --updated-after <str>  Filter by update time (ISO 8601 format)
    --id <str>             Get a specific document by ID
    --limit <int>          Maximum results per page (1-1000, default: 20)
    --with-content         Include full HTML content in response
    --cursor <str>         Pagination cursor for next page
    --all                  Fetch all pages automatically
    --output <str>         Output format: json (default), summary
    --help                 Show this help message

OUTPUT:
    JSON object to stdout:
    {
        "count": <total matching documents>,
        "fetched": <number of results in this response>,
        "next_cursor": "<cursor for next page or null>",
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
    # List documents in "later" folder
    python scripts/list_documents.py --location later

    # Get recently updated documents with HTML content
    python scripts/list_documents.py --updated-after "2024-01-01T00:00:00Z" --with-content

    # Fetch all documents in archive (all pages)
    python scripts/list_documents.py --location archive --all

    # Filter by multiple tags
    python scripts/list_documents.py --tag important --tag reference

    # Get a specific document by ID
    python scripts/list_documents.py --id "abc123def456"

REFERENCES:
    - Usage Guide: references/usage-guide.md
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Add scripts folder to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils import (
    EXIT_INVALID_ARGS,
    create_client,
    handle_response,
    output_error,
    output_json,
)


def build_params(args: argparse.Namespace) -> dict:
    """Build API parameters from CLI arguments."""
    params = {}

    if args.location:
        valid_locations = {"new", "later", "shortlist", "archive", "feed"}
        if args.location not in valid_locations:
            raise ValueError(
                f"Invalid location: {args.location}. Must be one of: {', '.join(valid_locations)}"
            )
        params["location"] = args.location

    if args.category:
        params["category"] = args.category

    if args.tag:
        if len(args.tag) > 5:
            raise ValueError("Maximum 5 tags allowed")
        params["tags"] = args.tag

    if args.updated_after:
        params["updatedAfter"] = args.updated_after

    if args.id:
        params["id"] = args.id

    if args.limit:
        params["pageCursor"] = None  # First page
        params["withHtmlContent"] = args.with_content

    return params


def fetch_page(client, params: dict) -> dict:
    """Fetch a single page of results."""
    # Build query params, excluding None values
    query_params = {k: v for k, v in params.items() if v is not None}

    response = client.get("/list/", params=query_params)
    return handle_response(response, client)


def fetch_all_pages(client, params: dict) -> dict:
    """Fetch all pages of results."""
    all_results = []
    total_count = 0
    cursor = None
    page = 0

    while True:
        page_params = {**params}
        if cursor:
            page_params["pageCursor"] = cursor
        else:
            page_params.pop("pageCursor", None)

        data = fetch_page(client, page_params)
        total_count = data.get("count", 0)
        results = data.get("results", [])
        all_results.extend(results)

        cursor = data.get("nextPageCursor")
        page += 1

        if not cursor:
            break

    return {
        "count": total_count,
        "fetched": len(all_results),
        "pages": page,
        "next_cursor": None,
        "results": all_results,
    }


def format_summary(data: dict) -> str:
    """Format results as a human-readable summary."""
    lines = [
        f"Total: {data.get('count', 0)} documents",
        f"Fetched: {data.get('fetched', len(data.get('results', [])))}",
        "",
    ]

    for doc in data.get("results", [])[:20]:  # Limit to first 20 for summary
        title = doc.get("title", "Untitled")
        location = doc.get("location", "unknown")
        progress = doc.get("reading_progress", 0)
        lines.append(f"- [{location}] {title} ({progress*100:.0f}%)")

    if len(data.get("results", [])) > 20:
        lines.append(f"... and {len(data['results']) - 20} more")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="List documents from Readwise Reader library",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("EXAMPLES:")[1] if "EXAMPLES:" in __doc__ else None,
    )

    parser.add_argument("--location", help="Filter by location (new, later, shortlist, archive, feed)")
    parser.add_argument("--category", help="Filter by category")
    parser.add_argument("--tag", action="append", help="Filter by tag (can be specified multiple times)")
    parser.add_argument("--updated-after", help="Filter by update time (ISO 8601)")
    parser.add_argument("--id", help="Get specific document by ID")
    parser.add_argument("--limit", type=int, default=20, help="Max results per page (default: 20)")
    parser.add_argument("--with-content", action="store_true", help="Include HTML content")
    parser.add_argument("--cursor", help="Pagination cursor")
    parser.add_argument("--all", action="store_true", help="Fetch all pages")
    parser.add_argument("--output", choices=["json", "summary"], default="json", help="Output format")

    args = parser.parse_args()

    try:
        params = build_params(args)
    except ValueError as e:
        output_error(type("APIError", (), {
            "to_json": lambda: {"error": {"type": "validation_error", "message": str(e)}},
            "exit_code": EXIT_INVALID_ARGS
        })())

    with create_client() as client:
        try:
            if args.all:
                data = fetch_all_pages(client, params)
            elif args.cursor:
                params["pageCursor"] = args.cursor
                data = fetch_page(client, params)
            else:
                data = fetch_page(client, params)

            if args.output == "summary":
                print(format_summary(data))
            else:
                # Add fetched count if not present
                if "fetched" not in data:
                    data["fetched"] = len(data.get("results", []))
                output_json(data)

        except Exception as e:
            if hasattr(e, "to_json"):
                output_error(e)
            raise


if __name__ == "__main__":
    main()
