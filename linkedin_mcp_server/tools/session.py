"""Login-state tools for explicit, user-controlled LinkedIn authentication.

The engagement tools added to this server use these same states as their hard
preflight. A missing or stale session is never repaired by a post-action tool:
the user must explicitly start and complete the existing browser login flow.
"""

from __future__ import annotations

import logging
from typing import Any

from fastmcp import Context, FastMCP

from linkedin_mcp_server.bootstrap import (
    RuntimePolicy,
    current_login_generation,
    get_runtime_policy,
    initialize_bootstrap,
    start_login_if_needed,
)
from linkedin_mcp_server.config.schema import DEFAULT_TOOL_TIMEOUT_SECONDS
from linkedin_mcp_server.core.exceptions import AuthenticationError, NetworkError
from linkedin_mcp_server.drivers.browser import ensure_authenticated, get_profile_dir
from linkedin_mcp_server.exceptions import (
    AuthMissingOnOwnerError,
    AuthStaleOnOwnerError,
    AuthenticationInProgressError,
    AuthenticationStartedError,
    BrowserBusyError,
    BrowserSetupFailedError,
    BrowserSetupInProgressError,
    BrowserShutdownUnconfirmedError,
    DockerHostLoginRequiredError,
)
from linkedin_mcp_server.session_state import (
    load_source_state,
    portable_cookie_path,
    source_state_path,
)
from linkedin_mcp_server.drivers.browser import profile_exists

logger = logging.getLogger(__name__)


def _source_session_files_ready() -> bool:
    """Return whether the durable source-session files are complete and parseable.

    This intentionally only reports local session availability. The live check is
    performed separately by :func:`ensure_authenticated`, which starts the
    existing browser lifecycle and validates the stored session against LinkedIn.
    """
    profile_dir = get_profile_dir()
    return (
        profile_exists(profile_dir)
        and portable_cookie_path(profile_dir).exists()
        and source_state_path(profile_dir).exists()
        and load_source_state(profile_dir) is not None
    )


def _result(
    status: str,
    message: str,
    *,
    ready: bool = False,
    user_action_required: bool = False,
    source_session_present: bool | None = None,
) -> dict[str, Any]:
    """Build the stable, non-sensitive session status contract."""
    result: dict[str, Any] = {
        "status": status,
        "ready": ready,
        "user_action_required": user_action_required,
        "message": message,
    }
    if source_session_present is not None:
        result["source_session_present"] = source_session_present
    return result


async def _live_login_status() -> dict[str, Any]:
    """Return session readiness without triggering automatic interactive login."""
    source_session_present = _source_session_files_ready()
    if not source_session_present:
        return _result(
            "login_required",
            "No complete LinkedIn source session is available. Start the user-controlled login flow before attempting any engagement action.",
            user_action_required=True,
            source_session_present=False,
        )

    try:
        # Unlike get_ready_extractor(), this check does not call bootstrap's
        # automatic login gate. It only validates the existing session and must
        # never open a replacement login window as a side effect.
        await ensure_authenticated()
    except BrowserBusyError:
        return _result(
            "profile_conflict",
            "Another LinkedIn MCP process currently owns the browser profile. The saved session was not changed; wait for it to finish before retrying.",
            user_action_required=False,
            source_session_present=True,
        )
    except BrowserShutdownUnconfirmedError:
        return _result(
            "profile_conflict",
            "A prior LinkedIn browser did not close cleanly, so the profile is preserved. Restart the server before attempting login or engagement.",
            user_action_required=True,
            source_session_present=True,
        )
    except AuthenticationError:
        return _result(
            "expired",
            "A stored LinkedIn session exists but could not be validated. Complete the user-controlled login flow before attempting any engagement action.",
            user_action_required=True,
            source_session_present=True,
        )
    except NetworkError:
        return _result(
            "unknown",
            "LinkedIn session state could not be verified because of a network error. No engagement action was attempted; retry the status check before starting a batch.",
            user_action_required=False,
            source_session_present=True,
        )

    return _result(
        "ready",
        "A valid LinkedIn session has been verified. Engagement tools may proceed only with their own explicit confirmation flags.",
        ready=True,
        source_session_present=True,
    )


def register_session_tools(
    mcp: FastMCP, *, tool_timeout: float = DEFAULT_TOOL_TIMEOUT_SECONDS
) -> None:
    """Register explicit login-status and login-initiation MCP tools."""

    @mcp.tool(
        timeout=tool_timeout,
        title="Get LinkedIn Login Status",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"session", "authentication"},
    )
    async def get_login_status(ctx: Context) -> dict[str, Any]:
        """Check whether a LinkedIn session is ready for a future engagement action.

        This tool never posts, reacts, comments, or starts an interactive login.
        It verifies an existing session only. A result other than ``ready`` means
        downstream engagement tools must stop without attempting a LinkedIn write.
        """
        del ctx
        initialize_bootstrap()
        return await _live_login_status()

    @mcp.tool(
        timeout=tool_timeout,
        title="Begin LinkedIn Login",
        annotations={"openWorldHint": True},
        tags={"session", "authentication"},
    )
    async def begin_linkedin_login(ctx: Context) -> dict[str, Any]:
        """Start the existing interactive LinkedIn login flow when login is needed.

        The user completes LinkedIn authentication, 2FA, captcha, or security
        challenges directly in the browser. This tool never accepts or handles a
        LinkedIn password. On Docker, it returns the host-side login requirement
        because the running container cannot safely own the interactive browser.
        """
        initialize_bootstrap()
        current = await _live_login_status()
        if current["status"] == "ready":
            return current
        if current["status"] == "profile_conflict":
            return current
        if current["status"] == "unknown":
            return current
        if get_runtime_policy() is RuntimePolicy.DOCKER:
            return _result(
                "login_required",
                "A Docker-hosted MCP requires user login on the host. Run the configured MCP package with `--login --login-viewer`, complete login in the viewer, then call get_login_status again.",
                user_action_required=True,
                source_session_present=bool(current.get("source_session_present")),
            )
        if current["status"] == "expired":
            return _result(
                "expired",
                "A stored session is stale. Run the existing server login command with `--login`, complete the browser login, then call get_login_status again. No engagement action was attempted.",
                user_action_required=True,
                source_session_present=True,
            )

        try:
            await start_login_if_needed(ctx, superseded_by=current_login_generation())
        except AuthenticationStartedError:
            return _result(
                "login_in_progress",
                "The LinkedIn login browser has opened. Complete login there, including any 2FA or security challenge, then call get_login_status again.",
                user_action_required=True,
                source_session_present=False,
            )
        except AuthenticationInProgressError:
            return _result(
                "login_in_progress",
                "LinkedIn login is already in progress in a browser window. Complete it there, then call get_login_status again.",
                user_action_required=True,
                source_session_present=False,
            )
        except (AuthMissingOnOwnerError, AuthStaleOnOwnerError):
            return _result(
                "login_required",
                "This shared browser owner cannot authenticate by itself. Start login from the attached client/browser, complete it there, then retry the status check.",
                user_action_required=True,
                source_session_present=bool(current.get("source_session_present")),
            )
        except (BrowserSetupInProgressError, BrowserSetupFailedError) as exc:
            logger.info("LinkedIn login setup is not ready: %s", exc)
            return _result(
                "setup_incomplete",
                str(exc),
                user_action_required=False,
                source_session_present=False,
            )
        except DockerHostLoginRequiredError as exc:
            return _result(
                "login_required",
                str(exc),
                user_action_required=True,
                source_session_present=bool(current.get("source_session_present")),
            )

        # A peer may have produced a session while this request was waiting, or a
        # valid session may have appeared through the browser-import path.
        return await _live_login_status()
