"""Run a local in-memory MCP validation without changing LinkedIn state.

This intentionally calls only the login gate and write tools with confirmation
flags disabled. It is not a live Like/comment test and must never be used to
claim that a LinkedIn write completed.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastmcp import Client

from linkedin_mcp_server.server import create_mcp_server

OUTPUT = Path("non_destructive_e2e_result.json")
POST_URL = "https://www.linkedin.com/posts/e2e-validation-placeholder"
EXPECTED_TOOLS = {
    "get_login_status",
    "begin_linkedin_login",
    "get_post_engagement_status",
    "like_post",
    "comment_on_post",
}


def result_data(result: Any) -> Any:
    """Extract a JSON-compatible result from a FastMCP tool response."""
    structured = getattr(result, "structured_content", None)
    if structured is not None:
        return structured
    return getattr(result, "content", result)


async def main() -> None:
    server = create_mcp_server(tool_timeout=30.0)
    async with Client(server) as client:
        tool_names = {tool.name for tool in await client.list_tools()}
        login = await client.call_tool("get_login_status", {}, raise_on_error=False)
        like_dry_run = await client.call_tool(
            "like_post",
            {"post_url": POST_URL, "confirm_like": False},
            raise_on_error=False,
        )
        comment_dry_run = await client.call_tool(
            "comment_on_post",
            {
                "post_url": POST_URL,
                "comment_text": "Non-destructive validation only.",
                "confirm_comment": False,
            },
            raise_on_error=False,
        )

    report = {
        "mode": "non_destructive_local_mcp_e2e",
        "live_linkedin_write_attempted": False,
        "expected_tools_present": sorted(EXPECTED_TOOLS.intersection(tool_names)),
        "missing_expected_tools": sorted(EXPECTED_TOOLS.difference(tool_names)),
        "login_status": result_data(login),
        "like_with_confirmation_false": result_data(like_dry_run),
        "comment_with_confirmation_false": result_data(comment_dry_run),
    }
    OUTPUT.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
