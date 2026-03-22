#!/usr/bin/env python3
"""
List all tags from Readwise Reader library.

This script retrieves all tags from your Reader library.

USAGE:
    python scripts/list_tags.py [OPTIONS]

OPTIONS:
    --cursor <str>    Pagination cursor for next page
    --all             Fetch all pages automatically (uses JSON Lines format)
    --output <file>   Output file path (.json or .jsonl recommended)
    --help            Show this help message

OUTPUT (standard mode):
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

OUTPUT (--all mode, JSON Lines format):
    Line 1 (metadata): {"metadata": {"total": N, "query": {}, "timestamp": "..."}}
    Lines 2-N (data): {"key": "...", "name": "..."}
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
    # List all tags
    python scripts/list_tags.py

    # Fetch all pages (JSON Lines format to stdout)
    python scripts/list_tags.py --all

    # Fetch all and write to file
    python scripts/list_tags.py --all --output tags.jsonl

    # Pipe to grep for filtering
    python scripts/list_tags.py --all | grep "important"
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


def fetch_tags_page(client, cursor: Optional[str] = None) -> dict:
    """Fetch a single page of tags."""
    params = {}
    if cursor:
        params["pageCursor"] = cursor

    response = client.get("/tags/", params=params)
    return handle_response(response, client)


async def fetch_all_tags_generator(client) -> AsyncGenerator[dict, None]:
    """
    Fetch all tags, yielding one at a time in JSON Lines format.

    Yields:
        1. Metadata dict first: {"metadata": {"total": N, "query": {}, "timestamp": "..."}}
        2. Tag dicts for each tag
        3. Summary dict last: {"summary": {"fetched": N, "end": true}}
    """
    fetched_count = 0
    cursor: Optional[str] = None
    retry_count = 0
    first_page = True
    total_count = 0

    while True:
        try:
            data = fetch_tags_page(client, cursor)
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
            continue

        # Reset retry count on success
        retry_count = 0

        # On first page, yield metadata
        if first_page:
            total_count = data.get("count", 0)
            metadata = {
                "metadata": {
                    "total": total_count,
                    "query": {},
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                }
            }
            yield metadata
            first_page = False

        # Yield each tag from this page
        results = data.get("results", [])
        for tag in results:
            yield tag
            fetched_count += 1

        # Check for more pages
        cursor = data.get("nextPageCursor")
        if not cursor:
            break

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
        description="List all tags from Readwise Reader library",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--cursor", help="Pagination cursor")
    parser.add_argument("--all", action="store_true", help="Fetch all pages (uses JSON Lines format)")
    parser.add_argument("--output", help="Output file path (.json or .jsonl recommended)")

    args = parser.parse_args()

    try:
        with create_client() as client:
            if args.all:
                # Use streaming JSON Lines format
                generator = fetch_all_tags_generator(client)
                await output_jsonlines(generator, args.output)
            else:
                # Standard JSON format
                if args.cursor:
                    data = fetch_tags_page(client, args.cursor)
                else:
                    data = fetch_tags_page(client)

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
    except Exception as e:
        if hasattr(e, "to_json"):
            raise_error(e)  # type: ignore[arg-type]
        raise


def main():
    """Main entry point."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
