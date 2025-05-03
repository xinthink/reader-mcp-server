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
from typing import Dict, Any, Optional, Union, cast, Literal
from contextlib import asynccontextmanager
from dataclasses import dataclass
from mcp.server.fastmcp import FastMCP
from pydantic import Field

from models import ListDocumentResponse


# Set up logging
logger = logging.getLogger("reader-mcp-server")

# Reader API endpoints
READER_API_BASE_URL = "https://readwise.io/api/v3"
VALID_LOCATIONS = {'new', 'later', 'shortlist', 'archive', 'feed'}


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


def validate_list_params(location: Optional[Literal['new', 'later', 'shortlist', 'archive', 'feed']] = None,
                         after: Optional[str] = None,
                         with_content: Optional[bool] = False,
                         page_cursor: Optional[str] = None) -> Dict[str, Any]:
    """
    Validate and filter document list parameters.
    Args:
        location: The location parameter to validate (only supports 'new', 'later', 'shortlist', 'archive', 'feed')
        after: The timestamp parameter to validate
        with_content: Whether to include html_content
        page_cursor: Pagination cursor
    Returns:
        Dict containing valid parameters
    """

    params = {}
    if location in VALID_LOCATIONS:
        params['location'] = location
    else:
        logger.warning(f"Invalid `location`: '{location}', parameter will be ignored")
    try:
        if after and 'T' in after and (after.endswith('Z') or '+' in after):
            params['updatedAfter'] = after
        elif after:
            logger.warning(f"Invalid ISO 8601 datetime: {after}, parameter will be ignored")
    except (TypeError, ValueError):
        logger.warning(f"Invalid datetime format: {after}, parameter will be ignored")
    if with_content:
        params['withHtmlContent'] = with_content
    if page_cursor:
        params['pageCursor'] = page_cursor
    return params

@mcp.tool()
async def list_documents(
        location: Optional[Literal['new', 'later', 'shortlist', 'archive', 'feed']] = Field(
            default=None,
            description="The folder where the document is located, supports 'new', 'later', 'shortlist', 'archive', 'feed'"),
        updatedAfter: Optional[str] = Field(default=None, description="Filter by update time (ISO8601)"),
        withContent: Optional[bool] = Field(default=False, description="Whether to include HTML content"),
        pageCursor: Optional[str] = Field(default=None, description="Pagination cursor"),
    ) -> ListDocumentResponse:
    """
    Get the document list via the Reader API.
    Args:
        location: The folder where the document is located, supports 'new', 'later', 'shortlist', 'archive', 'feed' (optional)
        updatedAfter: Filter by update time (optional, ISO8601)
        withContent: Whether to include HTML content (optional, default false)
        pageCursor: Pagination cursor (optional)
    Returns:
        Document list JSON
    """
    ctx = get_reader_context()
    logger.info(f"tool list_documents: location={location}, updatedAfter={updatedAfter}, withContent={withContent}, pageCursor={pageCursor}")
    try:
        params = validate_list_params(location, updatedAfter, withContent, pageCursor)
        response = await ctx.client.get("/list/", params=params)
        response.raise_for_status()
        data = response.json()
        return data
    except Exception as e:
        logger.error(f"Error in tool list_documents: {str(e)}")
        raise


if __name__ == "__main__":
    # Run server
    mcp.run()
