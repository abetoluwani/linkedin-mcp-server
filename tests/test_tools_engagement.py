"""Tests for login-gated post engagement MCP tools."""

from typing import Any, Callable, Coroutine, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import FastMCP
from fastmcp.tools import FunctionTool

from linkedin_mcp_server.tools.engagement import register_engagement_tools


async def _tool_fn(
    mcp: FastMCP, name: str
) -> Callable[..., Coroutine[Any, Any, dict[str, Any]]]:
    tool = await mcp.get_tool(name)
    if tool is None:
        raise AssertionError(f"Tool {name!r} was not registered")
    return cast(FunctionTool, tool).fn


class TestEngagementTools:
    async def test_like_requires_ready_login_before_resolving_extractor(
        self, monkeypatch: pytest.MonkeyPatch, mock_context: Any
    ) -> None:
        monkeypatch.setattr(
            "linkedin_mcp_server.tools.engagement._live_login_status",
            AsyncMock(
                return_value={
                    "status": "login_required",
                    "ready": False,
                    "message": "Sign in first.",
                }
            ),
        )
        get_extractor = AsyncMock()
        monkeypatch.setattr(
            "linkedin_mcp_server.tools.engagement.get_ready_extractor", get_extractor
        )
        extractor = MagicMock()

        mcp = FastMCP("test")
        register_engagement_tools(mcp)
        result = await (await _tool_fn(mcp, "like_post"))(
            "https://www.linkedin.com/posts/example-1",
            True,
            mock_context,
            request_id="request-1",
            extractor=extractor,
        )

        assert result["status"] == "login_required"
        assert result["verified"] is False
        assert result["request_id"] == "request-1"
        extractor.like_post.assert_not_called()
        get_extractor.assert_not_awaited()

    async def test_like_forwards_explicit_confirmation_and_receipt(
        self, monkeypatch: pytest.MonkeyPatch, mock_context: Any
    ) -> None:
        monkeypatch.setattr(
            "linkedin_mcp_server.tools.engagement._live_login_status",
            AsyncMock(return_value={"status": "ready", "ready": True, "message": "OK"}),
        )
        expected = {
            "post_url": "https://www.linkedin.com/posts/example-1/",
            "action": "like",
            "status": "verified",
            "verified": True,
        }
        extractor = MagicMock()
        extractor.like_post = AsyncMock(return_value=expected)

        mcp = FastMCP("test")
        register_engagement_tools(mcp)
        result = await (await _tool_fn(mcp, "like_post"))(
            "https://www.linkedin.com/posts/example-1",
            False,
            mock_context,
            request_id="request-2",
            extractor=extractor,
        )

        assert result is expected
        extractor.like_post.assert_awaited_once_with(
            "https://www.linkedin.com/posts/example-1",
            confirm_like=False,
            request_id="request-2",
        )

    async def test_comment_forwards_text_confirmation_and_request_id(
        self, monkeypatch: pytest.MonkeyPatch, mock_context: Any
    ) -> None:
        monkeypatch.setattr(
            "linkedin_mcp_server.tools.engagement._live_login_status",
            AsyncMock(return_value={"status": "ready", "ready": True, "message": "OK"}),
        )
        expected = {
            "post_url": "https://www.linkedin.com/posts/example-1/",
            "action": "comment",
            "status": "not_submitted",
            "verified": False,
        }
        extractor = MagicMock()
        extractor.comment_on_post = AsyncMock(return_value=expected)

        mcp = FastMCP("test")
        register_engagement_tools(mcp)
        result = await (await _tool_fn(mcp, "comment_on_post"))(
            "https://www.linkedin.com/posts/example-1",
            "Useful implementation detail.",
            False,
            mock_context,
            request_id="request-3",
            extractor=extractor,
        )

        assert result is expected
        extractor.comment_on_post.assert_awaited_once_with(
            "https://www.linkedin.com/posts/example-1",
            "Useful implementation detail.",
            confirm_comment=False,
            request_id="request-3",
        )

    async def test_status_tool_is_read_only_and_forwards_optional_comment_text(
        self, monkeypatch: pytest.MonkeyPatch, mock_context: Any
    ) -> None:
        monkeypatch.setattr(
            "linkedin_mcp_server.tools.engagement._live_login_status",
            AsyncMock(return_value={"status": "ready", "ready": True, "message": "OK"}),
        )
        extractor = MagicMock()
        extractor.get_post_engagement_status = AsyncMock(
            return_value={"verified": True, "reaction": {"reacted": False}}
        )

        mcp = FastMCP("test")
        register_engagement_tools(mcp)
        result = await (await _tool_fn(mcp, "get_post_engagement_status"))(
            "https://www.linkedin.com/posts/example-1",
            mock_context,
            comment_text="Useful implementation detail.",
            extractor=extractor,
        )

        assert result["verified"] is True
        extractor.get_post_engagement_status.assert_awaited_once_with(
            "https://www.linkedin.com/posts/example-1",
            comment_text="Useful implementation detail.",
        )
