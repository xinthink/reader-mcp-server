#!/usr/bin/env python3
"""
Reader API MCP Server

这个 MCP 服务器连接到 Readwise Reader API，并暴露资源以获取指定时间范围、位置或类型的文档列表。
"""

import os
import httpx
import logging
from dotenv import load_dotenv
from datetime import datetime
from typing import Dict, Any, cast
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp import ListResourcesRequest, ServerSession
from mcp.server.fastmcp import FastMCP, Context

# 设置日志记录
logger = logging.getLogger("reader-mcp")

# Reader API 端点
READER_API_BASE_URL = "https://readwise.io/api/v3"
READER_AUTH_URL = "https://readwise.io/api/v2/auth/"


@dataclass
class ReaderContext:
    """Reader API 上下文"""
    access_token: str
    client: httpx.AsyncClient


@asynccontextmanager
async def reader_lifespan(server: FastMCP):
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
        try:
            response = await client.get(READER_AUTH_URL) # url should be /v2/auth
            if response.status_code != 204:
                logger.error(f"验证访问令牌失败: {response.status_code}")
                raise ValueError(f"验证访问令牌失败: {response.status_code}")
            logger.info("成功连接到 Reader API")
        except Exception as e:
            logger.error(f"连接到 Reader API 时出错: {str(e)}")
            raise

        # 提供上下文
        yield ReaderContext(access_token=access_token, client=client)


# 创建 MCP 服务器
mcp = FastMCP(
    "reader-api",
    lifespan=reader_lifespan,
    dependencies=["httpx"]
)


def get_reader_context(ctx: Context[ServerSession, object]) -> ReaderContext:
    """获取 Reader API 上下文"""
    return cast(ReaderContext, ctx.request_context.lifespan_context)


@mcp.resource("reader://documents/{location}/{updated_after}")
async def list_documents(location: str, updated_after: str) -> str:
    """
    List documents based on location (folder) and last modification time.

    Args:
        location: The directory path where documents are located.
        updated_after: The timestamp to filter documents based on last modification time, it should follow the ISO 8601 datetime format.

    Returns:
        str: A formatted string listing the documents and their details, or an error message if the operation fails.
    """
    ctx = get_reader_context(mcp.get_context())
    logger.debug(f"list documents {location} {updated_after}")


    try:
        response = await ctx.client.get("/list/")
        response.raise_for_status()
        data = response.json()

        # 格式化输出
        result = f"找到 {data.get('count', 0)} 个文档\n\n"

        for doc in data.get('results', []):
            result += format_document(doc)
            result += "\n---\n"

        return result
    except Exception as e:
        return f"获取文档列表时出错: {str(e)}"


def format_document(doc: Dict[str, Any], detailed: bool = False) -> str:
    """格式化文档信息"""
    result = f"标题: {doc.get('title', '无标题')}\n"

    if doc.get('author'):
        result += f"作者: {doc['author']}\n"

    if doc.get('category'):
        result += f"类别: {doc['category']}\n"

    if doc.get('location'):
        result += f"位置: {doc['location']}\n"

    if doc.get('word_count'):
        result += f"字数: {doc['word_count']}\n"

    if doc.get('published_date'):
        result += f"发布日期: {doc['published_date']}\n"

    if doc.get('created_at'):
        result += f"创建时间: {doc['created_at']}\n"

    if doc.get('updated_at'):
        result += f"更新时间: {doc['updated_at']}\n"

    if doc.get('url'):
        result += f"URL: {doc['url']}\n"

    if doc.get('source_url'):
        result += f"源 URL: {doc['source_url']}\n"

    if detailed and doc.get('summary'):
        result += f"\n摘要: {doc['summary']}\n"

    if detailed and doc.get('notes'):
        result += f"\n笔记: {doc['notes']}\n"

    return result


if __name__ == "__main__":
    # 运行服务器
    mcp.run()
