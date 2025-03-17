#!/usr/bin/env python3
"""
Reader API MCP Server

这个 MCP 服务器连接到 Readwise Reader API，并暴露资源以获取指定时间范围、位置或类型的文档列表。
"""

import os
import httpx
import logging
from dotenv import load_dotenv
from typing import Dict, Any, cast
from contextlib import asynccontextmanager
from dataclasses import dataclass
from mcp.server.fastmcp import FastMCP


# 设置日志记录
logger = logging.getLogger("reader-server")

# Reader API 端点
READER_API_BASE_URL = "https://readwise.io/api/v3"
READER_AUTH_URL = "https://readwise.io/api/v2/auth/"


@dataclass
class ReaderContext:
    """Reader API Context"""
    access_token: str
    client: httpx.AsyncClient


@asynccontextmanager
async def reader_lifespan(_: FastMCP):
    """管理 Reader API 客户端的生命周期"""
    # 从环境变量获取访问令牌
    load_dotenv()
    access_token = os.environ.get("READER_ACCESS_TOKEN")
    if not access_token:
        logger.error("未设置 READER_ACCESS_TOKEN 环境变量")
        raise ValueError("未设置 READER_ACCESS_TOKEN 环境变量")

    # 创建 HTTP 客户端
    async with httpx.AsyncClient(
        base_url=READER_API_BASE_URL,
        headers={"Authorization": f"Token {access_token}"},
        timeout=30.0
    ) as client:
        # 验证访问令牌
        # try:
        #     response = await client.get(READER_AUTH_URL) # url should be /v2/auth
        #     if response.status_code != 204:
        #         logger.error(f"验证访问令牌失败: {response.status_code}")
        #         raise ValueError(f"验证访问令牌失败: {response.status_code}")
        #     logger.info("成功连接到 Reader API")
        # except Exception as e:
        #     logger.error(f"连接到 Reader API 时出错: {str(e)}")
        #     raise

        # 提供上下文
        yield ReaderContext(access_token=access_token, client=client)


# 创建 MCP 服务器
mcp = FastMCP(
    "reader-api",
    lifespan=reader_lifespan,
    dependencies=["httpx"]
)


def get_reader_context() -> ReaderContext:
    """获取 Reader API 上下文"""
    ctx = mcp.get_context()
    return cast(ReaderContext, ctx.request_context.lifespan_context)


@mcp.resource("reader://documents/?loc={location}&after={updated_after}",
              mime_type="application/json")
async def list_documents(location: str, updated_after: str) -> Dict[str, Any]:
    """
    List documents based on location (folder) and last modification time.

    Args:
        location: The directory path where documents are located.
        updated_after: The timestamp to filter documents based on last modification time, it should follow the ISO 8601 datetime format.

    Returns:
        ListDocumentResponse: A response object containing the count, results, and pagination cursor.
    """
    ctx = get_reader_context()
    logger.debug(f"list documents {location} {updated_after}")

    try:
        response = await ctx.client.get("/list/")
        response.raise_for_status()
        data = response.json()
        return data

        # # Parse the response into ReaderDocument objects using map and the factory method
        # reader_documents = list(map(
        #     ReaderDocument.from_dict,
        #     data.get('results', [])
        # ))

        # # Create and return ListDocumentResponse
        # return ListDocumentResponse(
        #     count=data.get('count', 0),
        #     results=reader_documents,
        #     nextPageCursor=data.get('next_page_cursor')
        # )
    except Exception as e:
        logger.error(f"Error retrieving document list: {str(e)}")
        raise


if __name__ == "__main__":
    # 运行服务器
    mcp.run()
