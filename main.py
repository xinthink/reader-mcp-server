#!/usr/bin/env python3
"""
Reader API MCP Server

This MCP server connects to the Readwise Reader API and exposes resources to retrieve document lists
based on specified time ranges, locations, or types.
"""

import os
import httpx
import logging
from dotenv import load_dotenv
from typing import Dict, Any, cast
from contextlib import asynccontextmanager
from dataclasses import dataclass
from mcp.server.fastmcp import FastMCP


# Set up logging
logger = logging.getLogger("reader-mcp-server")

# Reader API endpoints
READER_API_BASE_URL = "https://readwise.io/api/v3"


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
    access_token = os.environ.get("ACCESS_TOKEN")
    if not access_token:
        logger.error("ACCESS_TOKEN environment variable is not set")
        raise ValueError("ACCESS_TOKEN environment variable is not set")

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


def validate_list_params(location: str, after: str, with_content: str) -> Dict[str, str]:
    """
    Validate and filter list documents parameters.

    Args:
        location: The location parameter to validate
        after: The timestamp parameter to validate
        with_content: Whether to include html_content in results

    Returns:
        Dict containing valid parameters
    """
    valid_locations = {'new', 'later', 'shortlist', 'archive', 'feed'}
    params = {}

    if location in valid_locations:
        params['location'] = location
    else:
        logger.warning(f"Invalid location: {location}, parameter will be ignored")

    try:
        # Basic ISO 8601 format validation
        if 'T' in after and (after.endswith('Z') or '+' in after):
            params['updatedAfter'] = after
        else:
            logger.warning(f"Invalid ISO 8601 datetime: {after}, parameter will be ignored")
    except (TypeError, ValueError):
        logger.warning(f"Invalid datetime format: {after}, parameter will be ignored")

    if with_content and with_content.lower() in {'true', 'false'}:
        params['withHtmlContent'] = with_content.lower() == 'true'

    return params


@mcp.resource("reader://documents/location={location};after={after};withContent={with_content}",
              mime_type="application/json")
async def list_documents(location: str, after: str, with_content: str) -> Dict[str, Any]:
    """
    List documents based on location (folder), last modification time, and optionally include html content.

    Args:
        location: The location where documents are stored. Valid values are: new, later, shortlist, archive, feed
        after: ISO 8601 datetime to filter documents modified after this time
        withContent: If true, include HTML content in each document (default: false)

    Returns:
        A dict containing count, results list and pagination cursor
    """
    ctx = get_reader_context()
    logger.debug(f"list documents @{location} after {after} withContent={with_content}")

    try:
        params = validate_list_params(location, after, with_content)
        response = await ctx.client.get("/list/", params=params)
        response.raise_for_status()
        data = response.json()
        return data
    except Exception as e:
        logger.error(f"Error retrieving document list: {str(e)}")
        raise


if __name__ == "__main__":
    # Run server
    mcp.run()
