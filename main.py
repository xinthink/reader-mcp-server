#!/usr/bin/env python3
"""
Reader MCP Server

This MCP server connects to the Readwise Reader API and exposes tools to:
- List documents with filtering options
- Create/save new documents
- Update single documents
- Bulk update multiple documents
- Delete documents
- List tags
- Check authentication
"""

import os
import sys
import httpx
import logging
from dotenv import load_dotenv
from typing import Dict, Any, Optional, cast, Literal, List
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from models import (
    ReaderDocument,
    ListDocumentResponse,
    RateLimitError,
    AuthCheckResponse,
    CreateDocumentResponse,
    UpdateDocumentResponse,
    BulkUpdateResponse,
    BulkUpdateResult,
    DeleteDocumentResponse,
    Tag,
    ListTagsResponse,
)


# Configure logging to stderr (MCP protocol requirement for stdio servers)
logger = logging.getLogger("reader-mcp-server")
logger.setLevel(logging.INFO)

# Only add handler if not already added (prevents duplicate logs)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)

# Reader API endpoints
READER_API_BASE_URL = "https://readwise.io/api/v3"
VALID_LOCATIONS = {"new", "later", "shortlist", "archive", "feed"}
VALID_SAVE_LOCATIONS = {"new", "later", "archive", "feed"}
VALID_CATEGORIES = {"article", "email", "rss", "highlight", "note", "pdf", "epub", "tweet", "video"}


@dataclass
class ReaderContext:
    """Reader API Context"""
    access_token: str
    client: httpx.AsyncClient


@asynccontextmanager
async def reader_lifespan(_: FastMCP):
    """Manage the lifecycle of Reader API client"""
    # Get access token from environment variables
    load_dotenv()
    # Support READWISE_ACCESS_TOKEN as primary, with backward compatibility for ACCESS_TOKEN
    access_token = os.environ.get("READWISE_ACCESS_TOKEN") or os.environ.get("ACCESS_TOKEN")
    if not access_token:
        logger.error(
            "READWISE_ACCESS_TOKEN environment variable is not set "
            "(ACCESS_TOKEN is also supported for backward compatibility). "
            "Get your token from: https://readwise.io/access_token"
        )
        raise ValueError(
            "READWISE_ACCESS_TOKEN environment variable is not set. "
            "Get your token from: https://readwise.io/access_token"
        )

    # Create HTTP client
    async with httpx.AsyncClient(
        base_url=READER_API_BASE_URL,
        headers={"Authorization": f"Token {access_token}"},
        timeout=30.0
    ) as client:
        # Provide context
        yield ReaderContext(access_token=access_token, client=client)


# Create MCP server
mcp = FastMCP(
    "reader-api",
    lifespan=reader_lifespan,
    dependencies=["httpx"]
)


def get_reader_context() -> ReaderContext:
    """Get Reader API context"""
    ctx = mcp.get_context()
    return cast(ReaderContext, ctx.request_context.lifespan_context)


def _validate_location(location: str, valid_set: set = VALID_LOCATIONS) -> None:
    """Validate location parameter."""
    if location not in valid_set:
        raise ValueError(
            f"Invalid location '{location}'. "
            f"Must be one of: {', '.join(sorted(valid_set))}"
        )


def _validate_category(category: str) -> None:
    """Validate category parameter."""
    if category not in VALID_CATEGORIES:
        raise ValueError(
            f"Invalid category '{category}'. "
            f"Must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
        )


def _validate_iso8601_datetime(dt: str) -> bool:
    """Validate ISO 8601 datetime format."""
    try:
        if not dt or "T" not in dt:
            return False
        # Basic ISO 8601 check - should end with Z or have timezone offset
        if not (dt.endswith("Z") or "+" in dt or "-" in dt[-6:]):
            return False
        return True
    except (TypeError, ValueError):
        return False


def _rate_limit_error(response: httpx.Response) -> RateLimitError:
    """Create a rate limit error with retry_after from response headers."""
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            retry_after_seconds = int(retry_after)
        except ValueError:
            retry_after_seconds = 60
    else:
        retry_after_seconds = 60

    return RateLimitError(
        message=f"Rate limit exceeded. Retry after {retry_after_seconds} seconds.",
        retry_after_seconds=retry_after_seconds,
    )


@mcp.tool(
    name="reader_list_documents",
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def reader_list_documents(
    id: Optional[str] = None,
    location: Optional[Literal["new", "later", "shortlist", "archive", "feed"]] = None,
    category: Optional[Literal["article", "email", "rss", "highlight", "note", "pdf", "epub", "tweet", "video"]] = None,
    tag: Optional[List[str]] = None,
    updatedAfter: Optional[str] = None,
    limit: Optional[int] = None,
    withContent: Optional[bool] = False,
    pageCursor: Optional[str] = None,
) -> ListDocumentResponse:
    """
    List documents from your Readwise Reader library.

    Args:
        id: Get a single document by ID (returns only that document)
        location: Filter by folder location (new, later, shortlist, archive, feed)
        category: Filter by category (article, email, rss, highlight, note, pdf, epub, tweet, video)
        tag: Filter by tag keys (pass empty list [] for untagged documents)
        updatedAfter: Filter by update time (ISO 8601 format, e.g., 2024-01-01T00:00:00Z)
        limit: Number of results to return (1-100, default: 100)
        withContent: Include full HTML content in response (default: false)
        pageCursor: Pagination cursor for next page

    Returns:
        ListDocumentResponse with count, results, and nextPageCursor
    """
    ctx = get_reader_context()
    logger.info(
        f"reader_list_documents: id={id}, location={location}, category={category}, "
        f"tag={tag}, updatedAfter={updatedAfter}, limit={limit}, withContent={withContent}, "
        f"pageCursor={pageCursor}"
    )

    try:
        # Validate parameters
        if location:
            _validate_location(location)
        if category:
            _validate_category(category)
        if updatedAfter and not _validate_iso8601_datetime(updatedAfter):
            logger.warning(
                f"Invalid ISO 8601 datetime: {updatedAfter}. "
                "Expected format: YYYY-MM-DDTHH:MM:SSZ"
            )
            updatedAfter = None
        if limit is not None and (limit < 1 or limit > 100):
            raise ValueError(f"Limit must be between 1 and 100. Got: {limit}")

        # Build query params
        params: Dict[str, Any] = {}
        if id:
            params["id"] = id
        if location:
            params["location"] = location
        if category:
            params["category"] = category
        if tag is not None:
            # Pass empty string for untagged, or multiple tag values
            if len(tag) == 0:
                params["tag"] = ""
            else:
                params["tag"] = tag
        if updatedAfter:
            params["updatedAfter"] = updatedAfter
        if limit:
            params["limit"] = limit
        if withContent:
            params["withHtmlContent"] = withContent
        if pageCursor:
            params["pageCursor"] = pageCursor

        # Make API request
        response = await ctx.client.get("/list/", params=params)
        response.raise_for_status()
        data = response.json()

        # Parse response
        try:
            results = [
                ReaderDocument.from_dict(doc) for doc in data.get("results", [])
            ]
            list_response = ListDocumentResponse(
                count=data.get("count", 0),
                results=results,
                nextPageCursor=data.get("nextPageCursor"),
            )
        except (TypeError, ValueError) as e:
            logger.error(f"Invalid API response format: {e}")
            raise ValueError(
                "Unexpected response format from Reader API. "
                "Expected 'count', 'results' fields."
            )

        # Return ListDocumentResponse
        return list_response

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise ValueError(
                "Authentication failed. Please check your READWISE_ACCESS_TOKEN. "
                "Get your token from: https://readwise.io/access_token"
            )
        elif e.response.status_code == 429:
            raise _rate_limit_error(e.response)
        raise
    except ValueError as e:
        raise
    except Exception as e:
        logger.error(f"Error in reader_list_documents: {str(e)}")
        raise ValueError(f"Failed to list documents: {str(e)}")


@mcp.tool(
    name="reader_create_document",
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def reader_create_document(
    url: str,
    html: Optional[str] = None,
    should_clean_html: Optional[bool] = None,
    title: Optional[str] = None,
    author: Optional[str] = None,
    summary: Optional[str] = None,
    publishedDate: Optional[str] = None,
    imageUrl: Optional[str] = None,
    location: Optional[Literal["new", "later", "archive", "feed"]] = "new",
    category: Optional[Literal["article", "email", "rss", "highlight", "note", "pdf", "epub", "tweet", "video"]] = None,
    saved_using: Optional[str] = None,
    tags: Optional[List[str]] = None,
    notes: Optional[str] = None,
) -> CreateDocumentResponse:
    """
    Save a new document (URL) to your Readwise Reader library.

    Args:
        url: (Required) URL to save. Can be a placeholder if no URL is available (e.g., https://yourapp.com#document1)
        html: Provide the document's content as valid HTML (Readwise will not scrape the URL)
        should_clean_html: Auto-clean HTML and parse metadata when html is provided (default: false)
        title: Override the detected title
        author: Override the detected author
        summary: Override the detected summary
        publishedDate: Publication date (ISO 8601 format)
        imageUrl: Cover image URL
        location: Where to save the document (new, later, archive, feed; default: new)
        category: Override the detected category (article, email, rss, highlight, note, pdf, epub, tweet, video)
        saved_using: Source identifier for the document (e.g., "MyApp")
        tags: List of tags to apply
        notes: Personal notes about the document

    Returns:
        CreateDocumentResponse with id, url, title, and status
    """
    ctx = get_reader_context()
    logger.info(f"reader_create_document: url={url}, title={title}, location={location}")

    try:
        # Validate URL
        if not url:
            raise ValueError("URL is required. Provide a valid URL to save.")

        # Validate location
        if location:
            _validate_location(location, VALID_SAVE_LOCATIONS)

        # Validate category
        if category:
            _validate_category(category)

        # Build payload
        payload: Dict[str, Any] = {"url": url}
        if html:
            payload["html"] = html
        if should_clean_html is not None:
            payload["should_clean_html"] = should_clean_html
        if title:
            payload["title"] = title
        if author:
            payload["author"] = author
        if summary:
            payload["summary"] = summary
        if publishedDate:
            payload["published_date"] = publishedDate
        if imageUrl:
            payload["image_url"] = imageUrl
        if location:
            payload["location"] = location
        if category:
            payload["category"] = category
        if saved_using:
            payload["saved_using"] = saved_using
        if tags:
            payload["tags"] = tags
        if notes:
            payload["notes"] = notes

        # Make API request
        response = await ctx.client.post("/save/", json=payload)
        response.raise_for_status()
        data = response.json()

        # Parse response
        try:
            return CreateDocumentResponse(
                id=data.get("id", ""),
                url=data.get("url", ""),
                title=data.get("title", "Untitled"),
                status="created" if response.status_code == 201 else "updated",
            )
        except (TypeError, ValueError) as e:
            logger.error(f"Invalid API response format: {e}")
            raise ValueError(
                "Unexpected response format from Reader API when creating document."
            )

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise ValueError(
                "Authentication failed. Please check your READWISE_ACCESS_TOKEN."
            )
        elif e.response.status_code == 400:
            error_detail = e.response.text
            raise ValueError(f"Invalid request: {error_detail}")
        elif e.response.status_code == 429:
            raise _rate_limit_error(e.response)
        raise
    except ValueError as e:
        raise
    except Exception as e:
        logger.error(f"Error in reader_create_document: {str(e)}")
        raise ValueError(f"Failed to create document: {str(e)}")


@mcp.tool(
    name="reader_update_document",
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def reader_update_document(
    id: str,
    title: Optional[str] = None,
    author: Optional[str] = None,
    summary: Optional[str] = None,
    published_date: Optional[str] = None,
    image_url: Optional[str] = None,
    location: Optional[Literal["new", "later", "shortlist", "archive", "feed"]] = None,
    category: Optional[Literal["article", "email", "rss", "highlight", "note", "pdf", "epub", "tweet", "video"]] = None,
    tags: Optional[List[str]] = None,
    notes: Optional[str] = None,
    seen: Optional[bool] = None,
) -> UpdateDocumentResponse:
    """
    Update a document in your Readwise Reader library.

    Args:
        id: (Required) Document ID to update
        title: New title
        author: New author
        summary: New summary
        published_date: Publication date (ISO 8601 format)
        image_url: Cover image URL
        location: New location (new, later, shortlist, archive, feed)
        category: New category (article, email, rss, highlight, note, pdf, epub, tweet, video)
        tags: Replace existing tags (note: this replaces, not appends)
        notes: Update personal notes (empty string clears notes)
        seen: Mark as seen (true) or unseen (false)

    Returns:
        UpdateDocumentResponse with id, updated status, and document
    """
    ctx = get_reader_context()
    logger.info(f"reader_update_document: id={id}, location={location}")

    try:
        # Validate ID
        if not id:
            raise ValueError("Document ID is required.")

        # Validate location
        if location:
            _validate_location(location)

        # Validate category
        if category:
            _validate_category(category)

        # Build payload
        payload: Dict[str, Any] = {}
        if title is not None:
            payload["title"] = title
        if author is not None:
            payload["author"] = author
        if summary is not None:
            payload["summary"] = summary
        if published_date is not None:
            payload["published_date"] = published_date
        if image_url is not None:
            payload["image_url"] = image_url
        if location is not None:
            payload["location"] = location
        if category is not None:
            payload["category"] = category
        if tags is not None:
            payload["tags"] = tags
        if notes is not None:
            payload["notes"] = notes
        if seen is not None:
            payload["seen"] = seen

        if not payload:
            raise ValueError(
                "No update fields provided. "
                "Provide at least one of: title, author, summary, published_date, "
                "image_url, location, category, tags, notes, seen."
            )

        # Make API request
        response = await ctx.client.patch(f"/update/{id}/", json=payload)
        response.raise_for_status()
        data = response.json()

        return UpdateDocumentResponse(
            id=id,
            updated=True,
            document=data,
        )

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise ValueError("Authentication failed. Please check your access token.")
        elif e.response.status_code == 404:
            raise ValueError(
                f"Document not found: {id}. Verify the document ID is correct."
            )
        elif e.response.status_code == 400:
            error_detail = e.response.text
            raise ValueError(f"Invalid request: {error_detail}")
        elif e.response.status_code == 429:
            raise _rate_limit_error(e.response)
        raise
    except ValueError as e:
        raise
    except Exception as e:
        logger.error(f"Error in reader_update_document: {str(e)}")
        raise ValueError(f"Failed to update document: {str(e)}")


@mcp.tool(
    name="reader_bulk_update_documents",
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def reader_bulk_update_documents(
    updates: List[Dict[str, Any]],
) -> BulkUpdateResponse:
    """
    Bulk update multiple documents (max 50 per request).

    Args:
        updates: (Required) Array of update objects. Each object must have:
            - id: (Required) Document ID to update
            - title: (Optional) New title
            - author: (Optional) New author
            - summary: (Optional) New summary
            - published_date: (Optional) Publication date (ISO 8601)
            - image_url: (Optional) Cover image URL
            - location: (Optional) New location (new, later, shortlist, archive, feed)
            - category: (Optional) New category (article, email, rss, highlight, note, pdf, epub, tweet, video)
            - tags: (Optional) Replace tags
            - notes: (Optional) Update notes
            - seen: (Optional) Mark as seen/unseen

    Returns:
        BulkUpdateResponse with count and results
    """
    ctx = get_reader_context()
    logger.info(f"reader_bulk_update_documents: {len(updates)} updates")

    try:
        # Validate updates
        if not updates:
            raise ValueError("Updates array is required and cannot be empty.")
        if len(updates) > 50:
            raise ValueError(
                f"Too many updates: {len(updates)}. Maximum is 50. "
                "Split your updates into multiple requests."
            )

        for i, update in enumerate(updates):
            if not isinstance(update, dict):
                raise ValueError(f"Update at index {i} must be an object.")
            if "id" not in update:
                raise ValueError(f"Update at index {i} missing required field: id.")
            if update.get("location"):
                _validate_location(update["location"])
            if update.get("category"):
                _validate_category(update["category"])

        # Make API request
        response = await ctx.client.patch("/bulk_update/", json={"updates": updates})
        response.raise_for_status()
        data = response.json()

        # Parse response - API returns {results: [{id, success, error?}, ...]}
        results_data = data.get("results", [])
        results = [
            BulkUpdateResult(
                id=r.get("id", ""),
                success=r.get("success", False),
                error=r.get("error"),
            )
            for r in results_data
        ]

        return BulkUpdateResponse(
            count=len(results),
            results=results,
        )

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise ValueError("Authentication failed. Please check your access token.")
        elif e.response.status_code == 400:
            error_detail = e.response.text
            raise ValueError(f"Invalid request: {error_detail}")
        elif e.response.status_code == 429:
            raise _rate_limit_error(e.response)
        raise
    except ValueError as e:
        raise
    except Exception as e:
        logger.error(f"Error in reader_bulk_update_documents: {str(e)}")
        raise ValueError(f"Failed to bulk update documents: {str(e)}")


@mcp.tool(
    name="reader_delete_document",
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def reader_delete_document(
    ids: List[str],
) -> DeleteDocumentResponse:
    """
    Delete one or more documents from your Readwise Reader library.

    Args:
        ids: (Required) Array of document IDs to delete (at least one)

    Returns:
        DeleteDocumentResponse with deleted count and ids
    """
    ctx = get_reader_context()
    logger.info(f"reader_delete_document: {len(ids)} documents")

    try:
        # Validate IDs
        if not ids:
            raise ValueError("IDs array is required and cannot be empty.")
        if not isinstance(ids, list):
            raise ValueError("IDs must be an array of document IDs.")

        deleted_ids = []
        for doc_id in ids:
            try:
                response = await ctx.client.delete(f"/delete/{doc_id}/")
                response.raise_for_status()
                deleted_ids.append(doc_id)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.warning(f"Document not found: {doc_id}, skipping...")
                else:
                    logger.error(f"Error deleting {doc_id}: {e}")

        return DeleteDocumentResponse(
            deleted=len(deleted_ids),
            ids=deleted_ids,
        )

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise ValueError("Authentication failed. Please check your access token.")
        elif e.response.status_code == 429:
            raise _rate_limit_error(e.response)
        raise
    except ValueError as e:
        raise
    except Exception as e:
        logger.error(f"Error in reader_delete_document: {str(e)}")
        raise ValueError(f"Failed to delete documents: {str(e)}")


@mcp.tool(
    name="reader_list_tags",
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def reader_list_tags() -> ListTagsResponse:
    """
    List all tags from your Readwise Reader library.

    Returns:
        ListTagsResponse with count and results
    """
    ctx = get_reader_context()
    logger.info("reader_list_tags")

    try:
        # Make API request
        response = await ctx.client.get("/tags/")
        response.raise_for_status()
        data = response.json()

        # Parse response
        try:
            results_data = data.get("results", [])
            results = [
                Tag(key=tag.get("key", ""), name=tag.get("name", ""))
                for tag in results_data
            ]
            return ListTagsResponse(
                count=data.get("count", len(results)),
                results=results,
            )
        except (TypeError, ValueError) as e:
            logger.error(f"Invalid API response format: {e}")
            raise ValueError(
                "Unexpected response format from Reader API when listing tags."
            )

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise ValueError("Authentication failed. Please check your access token.")
        elif e.response.status_code == 429:
            raise _rate_limit_error(e.response)
        raise
    except ValueError as e:
        raise
    except Exception as e:
        logger.error(f"Error in reader_list_tags: {str(e)}")
        raise ValueError(f"Failed to list tags: {str(e)}")


@mcp.tool(
    name="reader_auth_check",
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def reader_auth_check() -> AuthCheckResponse:
    """
    Verify authentication with the Readwise Reader API.

    Returns:
        AuthCheckResponse with authenticated status

    Raises:
        ValueError: If authentication fails (401) or rate limited (429)
    """
    ctx = get_reader_context()
    logger.info("reader_auth_check")

    try:
        # Make API request to auth endpoint
        response = await ctx.client.get("/auth/")
        response.raise_for_status()

        # 204 No Content means authentication is valid
        return AuthCheckResponse(authenticated=True)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise ValueError(
                "Authentication failed. Please check your READWISE_ACCESS_TOKEN. "
                "Get your token from: https://readwise.io/access_token"
            )
        elif e.response.status_code == 429:
            raise _rate_limit_error(e.response)
        raise
    except Exception as e:
        logger.error(f"Error in reader_auth_check: {str(e)}")
        raise ValueError(f"Failed to verify authentication: {str(e)}")


if __name__ == "__main__":
    # Run server
    mcp.run()
