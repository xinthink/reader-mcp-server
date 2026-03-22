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
    --limit <int>          Maximum results per page (1-100, default: 20)
    --with-content         Include full HTML content in response
    --cursor <str>         Pagination cursor for next page
    --all                  Fetch all pages automatically (uses JSON Lines format)
    --output <file>        Output file path (.jsonl recommended for --all)
    --help                 Show this help message

OUTPUT (standard mode):
    JSON object to stdout:
    {
        "count": <total matching documents>,
        "fetched": <number of results in this response>,
        "next_cursor": "<cursor for next page or null>",
        "results": [...]
    }

OUTPUT (--all mode, JSON Lines format):
    Line 1 (metadata): {"metadata": {"total": N, "query": {...}, "timestamp": "..."}}
    Lines 2-N (data): {"id": "...", "title": "...", ...}
    Last line (summary): {"summary": {"fetched": N, "end": true}}

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

    # Fetch all documents in archive (JSON Lines format)
    python scripts/list_documents.py --location archive --all

    # Fetch all and write to file
    python scripts/list_documents.py --location archive --all --output archive.jsonl

    # Filter by multiple tags
    python scripts/list_documents.py --tag important --tag reference

    # Get a specific document by ID
    python scripts/list_documents.py --id "abc123def456"

    # Pipe to grep for filtering
    python scripts/list_documents.py --all | grep "python"
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Optional

# Add scripts folder to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils import (
    APIError,
    EXIT_INVALID_ARGS,
    EXIT_RATE_LIMIT,
    MAX_RETRIES,
    RateLimitError,
    create_client,
    handle_response,
    raise_error,
    output_json,
    output_jsonlines,
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
        valid_categories = {"article", "email", "rss", "highlight", "note", "pdf", "epub", "tweet", "video"}
        if args.category not in valid_categories:
            raise ValueError(
                f"Invalid category: {args.category}. Must be one of: {', '.join(sorted(valid_categories))}"
            )
        params["category"] = args.category

    if args.tag:
        if len(args.tag) > 5:
            raise ValueError("Maximum 5 tags allowed")
        params["tags"] = args.tag

    if args.updated_after:
        params["updatedAfter"] = args.updated_after

    if args.id:
        params["id"] = args.id

    if args.limit is not None:
        # Validate limit range (API accepts 1-100)
        if args.limit < 1 or args.limit > 100:
            raise ValueError("limit must be between 1 and 100")
        params["limit"] = args.limit

    if args.with_content:
        params["withHtmlContent"] = True

    if args.cursor:
        params["pageCursor"] = args.cursor

    return params


def fetch_page(client, params: dict) -> dict:
    """Fetch a single page of results."""
    # Build query params, excluding None values
    query_params = {k: v for k, v in params.items() if v is not None}

    response = client.get("/list/", params=query_params)
    return handle_response(response, client)


async def fetch_all_pages_generator(
    client, params: dict
) -> AsyncGenerator[dict, None]:
    """
    Fetch all pages, yielding documents one at a time in JSON Lines format.

    Yields:
        1. Metadata dict first: {"metadata": {"total": N, "query": {...}, "timestamp": "..."}}
        2. Document dicts for each document
        3. Summary dict last: {"summary": {"fetched": N, "end": true}}
    """
    total_count = 0
    fetched_count = 0
    page_params = {**params}
    cursor = page_params.get("pageCursor", None)
    retry_count = 0
    first_page = True

    # Remove pageCursor from params for the first request
    if cursor:
        page_params["pageCursor"] = cursor
    else:
        page_params.pop("pageCursor", None)

    while True:
        try:
            data = fetch_page(client, page_params)
        except RateLimitError as e:
            if retry_count >= MAX_RETRIES:
                raise APIError(
                    type="rate_limit_exceeded",
                    message=f"Rate limit exceeded after {MAX_RETRIES} retries",
                    hint="Consider reducing request frequency or waiting before retrying",
                    exit_code=EXIT_RATE_LIMIT,
                )
            await asyncio.sleep(e.retry_after_seconds)
            retry_count += 1
            continue  # Retry the request

        # Reset retry count on success
        retry_count = 0

        # On first page, yield metadata
        if first_page:
            total_count = data.get("count", 0)
            # Build query info for metadata (strip None values)
            query_info = {
                "location": params.get("location"),
                "category": params.get("category"),
                "tags": params.get("tags", []),
                "updatedAfter": params.get("updatedAfter"),
                "withContent": params.get("withHtmlContent", False),
            }
            metadata = {
                "metadata": {
                    "total": total_count,
                    "query": query_info,
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                }
            }
            yield metadata
            first_page = False

        # Yield each document from this page
        results = data.get("results", [])
        for doc in results:
            yield doc
            fetched_count += 1

        # Check for more pages
        cursor = data.get("nextPageCursor")
        if not cursor:
            break

        page_params["pageCursor"] = cursor
        await asyncio.sleep(0.01)  # Short break between pages

    # Yield summary at the end
    yield {
        "summary": {
            "fetched": fetched_count,
            "end": True,
        }
    }


async def async_main():
    """Async main function to support async generators."""
    parser = argparse.ArgumentParser(
        description="List documents from Readwise Reader library",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--location", help="Filter by location (new, later, shortlist, archive, feed)")
    parser.add_argument("--category", help="Filter by category (article, email, rss, highlight, note, pdf, epub, tweet, video)")
    parser.add_argument("--tag", action="append", help="Filter by tag (can be specified multiple times)")
    parser.add_argument("--updated-after", help="Filter by update time (ISO 8601)")
    parser.add_argument("--id", help="Get specific document by ID")
    parser.add_argument("--limit", type=int, default=20, help="Max results per page (default: 20)")
    parser.add_argument("--with-content", action="store_true", help="Include HTML content")
    parser.add_argument("--cursor", help="Pagination cursor")
    parser.add_argument("--all", action="store_true", help="Fetch all pages (uses JSON Lines format)")
    parser.add_argument("--output", help="Output file path (.json or .jsonl recommended)")

    args = parser.parse_args()

    params = build_params(args)
    try:
        with create_client() as client:
            if args.all:
                # Use streaming JSON Lines format
                generator = fetch_all_pages_generator(client, params)
                await output_jsonlines(generator, args.output)
            else:
                # Standard JSON format
                data = fetch_page(client, params)
                # Add fetched count
                data["fetched"] = len(data.get("results", []))
                if args.output:
                    # Write to file
                    with open(args.output, "w") as f:
                        f.write(json.dumps(data, indent=2, default=str))
                else:
                    output_json(data)
    except RateLimitError as e:
        raise_error(e)
    except ValueError as e:
        raise_error(APIError(
            type="validation_error",
            message=str(e),
            hint="Check your input parameters",
            exit_code=EXIT_INVALID_ARGS
        ))
    except APIError as e:
        raise_error(e)


def main():
    """Main entry point."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
