"""Explicit, login-gated LinkedIn post engagement tools."""

from __future__ import annotations

import logging
from typing import Any

from fastmcp import Context, FastMCP

from linkedin_mcp_server.config.schema import DEFAULT_TOOL_TIMEOUT_SECONDS
from linkedin_mcp_server.core.exceptions import AuthenticationError
from linkedin_mcp_server.dependencies import get_ready_extractor
from linkedin_mcp_server.error_handler import raise_tool_error
from linkedin_mcp_server.tools.session import _live_login_status

logger = logging.getLogger(__name__)


def _login_required_receipt(
    post_url: str,
    action: str,
    login_status: dict[str, Any],
    *,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Return a no-write receipt when the login preflight is not ready."""
    return {
        "post_url": post_url,
        "action": action,
        "request_id": request_id,
        "status": login_status["status"],
        "message": login_status["message"],
        "initial_state": {},
        "final_state": {},
        "verified": False,
        "evidence": {"login_status": login_status["status"]},
    }


async def _engagement_extractor(
    ctx: Context,
    *,
    tool_name: str,
    extractor: Any | None,
) -> tuple[dict[str, Any], Any | None]:
    """Run the shared login gate before resolving a browser extractor."""
    login_status = await _live_login_status()
    if not login_status["ready"]:
        return login_status, None
    if extractor is not None:
        return login_status, extractor
    return login_status, await get_ready_extractor(ctx, tool_name=tool_name)


def register_engagement_tools(
    mcp: FastMCP, *, tool_timeout: float = DEFAULT_TOOL_TIMEOUT_SECONDS
) -> None:
    """Register post engagement tools that report only verified visible actions."""

    @mcp.tool(
        timeout=tool_timeout,
        title="Get Post Engagement Status",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"post", "engagement", "verification"},
        exclude_args=["extractor"],
    )
    async def get_post_engagement_status(
        post_url: str,
        ctx: Context,
        comment_text: str | None = None,
        extractor: Any | None = None,
    ) -> dict[str, Any]:
        """Read the authenticated account's visible reaction and optional exact comment.

        This tool never clicks, types, submits, or starts login. If a valid
        session is unavailable, it returns the login status and performs no
        LinkedIn action.
        """
        try:
            login_status, active_extractor = await _engagement_extractor(
                ctx,
                tool_name="get_post_engagement_status",
                extractor=extractor,
            )
            if active_extractor is None:
                return _login_required_receipt(
                    post_url, "engagement_status", login_status
                )
            return await active_extractor.get_post_engagement_status(
                post_url, comment_text=comment_text
            )
        except AuthenticationError:
            return _login_required_receipt(
                post_url,
                "engagement_status",
                await _live_login_status(),
            )
        except ValueError as exc:
            raise_tool_error(exc, "get_post_engagement_status")
        except Exception as exc:
            raise_tool_error(exc, "get_post_engagement_status")

    @mcp.tool(
        timeout=tool_timeout,
        title="Like LinkedIn Post",
        annotations={"destructiveHint": True, "openWorldHint": True},
        tags={"post", "engagement", "actions"},
        exclude_args=["extractor"],
    )
    async def like_post(
        post_url: str,
        confirm_like: bool,
        ctx: Context,
        request_id: str | None = None,
        extractor: Any | None = None,
    ) -> dict[str, Any]:
        """Add one standard Like reaction only after explicit confirmation.

        The tool first confirms a valid user-authenticated session. It is a dry
        run when ``confirm_like`` is false, never toggles an existing reaction,
        and returns success only after LinkedIn visibly shows the final state.
        """
        try:
            login_status, active_extractor = await _engagement_extractor(
                ctx, tool_name="like_post", extractor=extractor
            )
            if active_extractor is None:
                return _login_required_receipt(
                    post_url, "like", login_status, request_id=request_id
                )
            return await active_extractor.like_post(
                post_url, confirm_like=confirm_like, request_id=request_id
            )
        except AuthenticationError:
            return _login_required_receipt(
                post_url,
                "like",
                await _live_login_status(),
                request_id=request_id,
            )
        except ValueError as exc:
            raise_tool_error(exc, "like_post")
        except Exception as exc:
            raise_tool_error(exc, "like_post")

    @mcp.tool(
        timeout=tool_timeout,
        title="Comment on LinkedIn Post",
        annotations={"destructiveHint": True, "openWorldHint": True},
        tags={"post", "engagement", "actions"},
        exclude_args=["extractor"],
    )
    async def comment_on_post(
        post_url: str,
        comment_text: str,
        confirm_comment: bool,
        ctx: Context,
        request_id: str | None = None,
        extractor: Any | None = None,
    ) -> dict[str, Any]:
        """Submit one exact comment only after explicit confirmation and verification.

        A missing, expired, or ambiguous session returns a no-write receipt. A
        duplicate exact self-comment is not submitted again. A post-click result
        is not considered successful unless the exact text and authenticated
        authorship are both visibly verified on the target post.
        """
        try:
            login_status, active_extractor = await _engagement_extractor(
                ctx, tool_name="comment_on_post", extractor=extractor
            )
            if active_extractor is None:
                return _login_required_receipt(
                    post_url, "comment", login_status, request_id=request_id
                )
            return await active_extractor.comment_on_post(
                post_url,
                comment_text,
                confirm_comment=confirm_comment,
                request_id=request_id,
            )
        except AuthenticationError:
            return _login_required_receipt(
                post_url,
                "comment",
                await _live_login_status(),
                request_id=request_id,
            )
        except ValueError as exc:
            raise_tool_error(exc, "comment_on_post")
        except Exception as exc:
            raise_tool_error(exc, "comment_on_post")
