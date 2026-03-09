"""
Shared utilities for Reader API scripts.

This module provides common functionality for all scripts:
- Authentication via READWISE_ACCESS_TOKEN environment variable
- HTTP client creation with proper headers
- Error handling with retry logic for rate limits
- Standardized exit codes and error output
"""

import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, NoReturn, Optional

import httpx
from dotenv import load_dotenv

# Exit codes
EXIT_SUCCESS = 0
EXIT_API_ERROR = 1
EXIT_AUTH_ERROR = 2
EXIT_RATE_LIMIT = 3
EXIT_INVALID_ARGS = 4

# API configuration
BASE_URL = "https://readwise.io/api/v3"
MAX_RETRIES = 3
RETRY_DELAY = 60  # seconds


@dataclass
class APIError(Exception):
    """Exception for API errors with structured information."""

    type: str
    message: str
    hint: Optional[str] = None
    exit_code: int = EXIT_API_ERROR

    def to_json(self) -> dict:
        """Convert error to JSON format for stderr output."""
        result = {"error": {"type": self.type, "message": self.message}}
        if self.hint:
            result["error"]["hint"] = self.hint
        return result


@dataclass
class RateLimitError(Exception):
    """Error response for rate limit (429) errors"""

    error_type: str = "rate_limit_error"
    message: str = "Rate limit exceeded"
    retry_after_seconds: int = 60
    exit_code: int = EXIT_RATE_LIMIT

    def to_json(self) -> dict:
        """Convert error to JSON format for stderr output."""
        return {
            "error": {
                "type": self.error_type,
                "message": self.message,
                "retry_after_seconds": self.retry_after_seconds,
            }
        }


def get_access_token() -> str:
    """
    Get the Readwise access token from environment.

    Returns:
        The access token string.

    Raises:
        APIError: If READWISE_ACCESS_TOKEN is not set.
    """
    load_dotenv()
    token = os.environ.get("READWISE_ACCESS_TOKEN")
    if not token:
        raise APIError(
            type="authentication_error",
            message="READWISE_ACCESS_TOKEN environment variable not set",
            hint="Set the environment variable or create a .env file with READWISE_ACCESS_TOKEN=your-token",
            exit_code=EXIT_AUTH_ERROR,
        )
    return token


def create_client(timeout: float = 30.0) -> httpx.Client:
    """
    Create an HTTP client with authentication headers.

    Args:
        timeout: Request timeout in seconds.

    Returns:
        Configured httpx.Client instance.
    """
    token = get_access_token()
    return httpx.Client(
        base_url=BASE_URL,
        headers={"Authorization": f"Token {token}"},
        timeout=timeout,
    )


def raise_error(error: Exception) -> NoReturn:
    """Raise an error by outputting to stderr in JSON format and exiting."""
    # Check if error has to_json method
    if hasattr(error, "to_json"):
        print(json.dumps(error.to_json()), file=sys.stderr)  # type: ignore[attr-defined]
    else:
        print(json.dumps({"error": {"type": "unknown_error", "message": str(error)}}), file=sys.stderr)
    sys.exit(getattr(error, "exit_code", EXIT_API_ERROR))


def handle_response(
    response: httpx.Response, client: httpx.Client, retry_count: int = 0
) -> dict:
    """
    Handle API response with error handling and retry logic.

    Args:
        response: The HTTP response object.
        client: The HTTP client for retry requests.
        retry_count: Current retry attempt number.

    Returns:
        Parsed JSON response data.

    Raises:
        APIError: For various error conditions.
    """
    # Success
    if response.status_code < 400:
        return response.json()

    # Rate limit - raise error for client to handle
    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", RETRY_DELAY))
        raise RateLimitError(
            message=f"Rate limit exceeded",
            retry_after_seconds=retry_after,
        )

    # Server errors - retry
    if response.status_code >= 500:
        if retry_count >= MAX_RETRIES:
            raise APIError(
                type="server_error",
                message=f"Server error: {response.status_code}",
                hint="The Readwise API may be experiencing issues. Try again later.",
                exit_code=EXIT_API_ERROR,
            )

        time.sleep(2 ** retry_count)  # Exponential backoff
        new_response = client.request(
            method=response.request.method,
            url=response.request.url,
            content=response.request.content,
        )
        return handle_response(new_response, client, retry_count + 1)

    # Authentication error
    if response.status_code == 401:
        raise APIError(
            type="authentication_error",
            message="Invalid or expired access token",
            hint="Verify your READWISE_ACCESS_TOKEN is correct at https://readwise.io/access_token",
            exit_code=EXIT_AUTH_ERROR,
        )

    # Not found
    if response.status_code == 404:
        raise APIError(
            type="not_found_error",
            message="Resource not found",
            hint="The requested document or resource does not exist",
            exit_code=EXIT_API_ERROR,
        )

    # Validation error
    if response.status_code == 400:
        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = response.text
        raise APIError(
            type="validation_error",
            message=f"Invalid request: {detail}",
            hint="Check your input parameters",
            exit_code=EXIT_INVALID_ARGS,
        )

    # Other errors
    raise APIError(
        type="api_error",
        message=f"API error: {response.status_code} - {response.text}",
        exit_code=EXIT_API_ERROR,
    )


def output_json(data: Any) -> None:
    """Output data as JSON to stdout."""
    print(json.dumps(data, indent=2, default=str))


def read_payload(file_path: Optional[str] = None) -> dict:
    """
    Read JSON payload from file or stdin.

    Args:
        file_path: Path to JSON file, or None to read from stdin.

    Returns:
        Parsed JSON data.

    Raises:
        APIError: If reading or parsing fails.
    """
    try:
        if file_path:
            with open(file_path, "r") as f:
                data = json.load(f)
        else:
            data = json.load(sys.stdin)
        return data
    except json.JSONDecodeError as e:
        raise APIError(
            type="parse_error",
            message=f"Invalid JSON: {e}",
            hint="Ensure your input is valid JSON",
            exit_code=EXIT_INVALID_ARGS,
        )
    except FileNotFoundError:
        raise APIError(
            type="file_error",
            message=f"File not found: {file_path}",
            exit_code=EXIT_INVALID_ARGS,
        )