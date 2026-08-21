"""Tests for explicit, login-first MCP session tools."""

from typing import Any, Callable, Coroutine, cast
from unittest.mock import AsyncMock

import pytest
from fastmcp import FastMCP
from fastmcp.tools import FunctionTool

from linkedin_mcp_server.core.exceptions import AuthenticationError
from linkedin_mcp_server.exceptions import AuthenticationStartedError
from linkedin_mcp_server.tools.session import register_session_tools


async def _tool_fn(
    mcp: FastMCP, name: str
) -> Callable[..., Coroutine[Any, Any, dict[str, Any]]]:
    tool = await mcp.get_tool(name)
    if tool is None:
        raise AssertionError(f"Tool {name!r} was not registered")
    return cast(FunctionTool, tool).fn


class TestSessionTools:
    async def test_login_status_requires_login_without_source_session(
        self, monkeypatch: pytest.MonkeyPatch, mock_context: Any
    ) -> None:
        monkeypatch.setattr(
            "linkedin_mcp_server.tools.session.initialize_bootstrap", lambda: None
        )
        monkeypatch.setattr(
            "linkedin_mcp_server.tools.session._source_session_files_ready",
            lambda: False,
        )
        ensure_authenticated = AsyncMock()
        monkeypatch.setattr(
            "linkedin_mcp_server.tools.session.ensure_authenticated",
            ensure_authenticated,
        )

        mcp = FastMCP("test")
        register_session_tools(mcp)
        result = await (await _tool_fn(mcp, "get_login_status"))(mock_context)

        assert result["status"] == "login_required"
        assert result["ready"] is False
        assert result["user_action_required"] is True
        ensure_authenticated.assert_not_awaited()

    async def test_login_status_returns_ready_only_after_live_validation(
        self, monkeypatch: pytest.MonkeyPatch, mock_context: Any
    ) -> None:
        monkeypatch.setattr(
            "linkedin_mcp_server.tools.session.initialize_bootstrap", lambda: None
        )
        monkeypatch.setattr(
            "linkedin_mcp_server.tools.session._source_session_files_ready",
            lambda: True,
        )
        ensure_authenticated = AsyncMock()
        monkeypatch.setattr(
            "linkedin_mcp_server.tools.session.ensure_authenticated",
            ensure_authenticated,
        )

        mcp = FastMCP("test")
        register_session_tools(mcp)
        result = await (await _tool_fn(mcp, "get_login_status"))(mock_context)

        assert result["status"] == "ready"
        assert result["ready"] is True
        assert result["user_action_required"] is False
        ensure_authenticated.assert_awaited_once()

    async def test_login_status_reports_expired_without_starting_login(
        self, monkeypatch: pytest.MonkeyPatch, mock_context: Any
    ) -> None:
        monkeypatch.setattr(
            "linkedin_mcp_server.tools.session.initialize_bootstrap", lambda: None
        )
        monkeypatch.setattr(
            "linkedin_mcp_server.tools.session._source_session_files_ready",
            lambda: True,
        )
        monkeypatch.setattr(
            "linkedin_mcp_server.tools.session.ensure_authenticated",
            AsyncMock(side_effect=AuthenticationError("invalid")),
        )

        mcp = FastMCP("test")
        register_session_tools(mcp)
        result = await (await _tool_fn(mcp, "get_login_status"))(mock_context)

        assert result["status"] == "expired"
        assert result["ready"] is False
        assert result["user_action_required"] is True

    async def test_begin_login_starts_user_controlled_flow_when_session_missing(
        self, monkeypatch: pytest.MonkeyPatch, mock_context: Any
    ) -> None:
        monkeypatch.setattr(
            "linkedin_mcp_server.tools.session.initialize_bootstrap", lambda: None
        )
        monkeypatch.setattr(
            "linkedin_mcp_server.tools.session._source_session_files_ready",
            lambda: False,
        )
        monkeypatch.setattr(
            "linkedin_mcp_server.tools.session.get_runtime_policy",
            lambda: object(),
        )
        monkeypatch.setattr(
            "linkedin_mcp_server.tools.session.current_login_generation", lambda: None
        )
        start_login = AsyncMock(
            side_effect=AuthenticationStartedError("browser opened")
        )
        monkeypatch.setattr(
            "linkedin_mcp_server.tools.session.start_login_if_needed", start_login
        )

        mcp = FastMCP("test")
        register_session_tools(mcp)
        result = await (await _tool_fn(mcp, "begin_linkedin_login"))(mock_context)

        assert result["status"] == "login_in_progress"
        assert result["user_action_required"] is True
        start_login.assert_awaited_once_with(mock_context, superseded_by=None)

    async def test_begin_login_in_docker_returns_host_login_instruction(
        self, monkeypatch: pytest.MonkeyPatch, mock_context: Any
    ) -> None:
        from linkedin_mcp_server.bootstrap import RuntimePolicy

        monkeypatch.setattr(
            "linkedin_mcp_server.tools.session.initialize_bootstrap", lambda: None
        )
        monkeypatch.setattr(
            "linkedin_mcp_server.tools.session._source_session_files_ready",
            lambda: False,
        )
        monkeypatch.setattr(
            "linkedin_mcp_server.tools.session.get_runtime_policy",
            lambda: RuntimePolicy.DOCKER,
        )
        start_login = AsyncMock()
        monkeypatch.setattr(
            "linkedin_mcp_server.tools.session.start_login_if_needed", start_login
        )

        mcp = FastMCP("test")
        register_session_tools(mcp)
        result = await (await _tool_fn(mcp, "begin_linkedin_login"))(mock_context)

        assert result["status"] == "login_required"
        assert "--login --login-viewer" in result["message"]
        start_login.assert_not_awaited()
