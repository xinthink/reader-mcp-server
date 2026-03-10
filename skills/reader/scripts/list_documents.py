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
    --all                  Fetch all pages automatically
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
"""

import argparse
import sys
import time
from pathlib import Path

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


def fetch_all_pages(client, params: dict) -> dict:
    """Fetch all pages of results with rate limit retry logic."""
    all_results = []
    total_count = 0
    page_params = {**params}
    cursor = page_params.get("pageCursor", None)
    page = 0
    retry_count = 0

    while True:
        if cursor:
            page_params["pageCursor"] = cursor
        else:
            page_params.pop("pageCursor", None)

        try:
            # print(f"fetching page {page_params}", file=sys.stderr)
            data = fetch_page(client, page_params)
        except RateLimitError as e:
            if retry_count >= MAX_RETRIES:
                raise APIError(
                    type="rate_limit_exceeded",
                    message=f"Rate limit exceeded after {MAX_RETRIES} retries",
                    hint="Consider reducing request frequency or waiting before retrying",
                    exit_code=EXIT_RATE_LIMIT,
                )
            time.sleep(e.retry_after_seconds)
            retry_count += 1
            continue  # Retry the request

        # Reset retry count on success
        retry_count = 0

        total_count = data.get("count", 0)
        results = data.get("results", [])
        all_results.extend(results)

        cursor = data.get("nextPageCursor")
        if not cursor:
            break

        page += 1
        time.sleep(0.01) # short break between pages

    return {
        "count": total_count,
        "fetched": len(all_results),
        "pages": page,
        "results": all_results,
    }


def main():
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
    parser.add_argument("--all", action="store_true", help="Fetch all pages")

    try:
        args = parser.parse_args()
        params = build_params(args)
        with create_client() as client:
            if args.all:
                data = fetch_all_pages(client, params)
            else:
                data = fetch_page(client, params)

            # Add fetched count if not present
            if "fetched" not in data:
                data["fetched"] = len(data.get("results", []))
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


if __name__ == "__main__":
    main()
