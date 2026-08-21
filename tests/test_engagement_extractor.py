"""Unit tests for safe, idempotent post-engagement extractor behavior."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from linkedin_mcp_server.scraping.extractor import LinkedInExtractor


@pytest.mark.parametrize(
    ("raw_url", "expected"),
    [
        (
            "https://www.linkedin.com/feed/update/urn:li:activity:1234567890/",
            "https://www.linkedin.com/feed/update/urn:li:activity:1234567890/",
        ),
        (
            "/posts/example-founder-ships-1234567890",
            "https://www.linkedin.com/posts/example-founder-ships-1234567890/",
        ),
    ],
)
def test_canonical_post_url_accepts_direct_linkedin_post_permalinks(
    raw_url: str, expected: str
) -> None:
    assert LinkedInExtractor._canonical_post_url(raw_url) == expected


@pytest.mark.parametrize(
    "raw_url",
    [
        "https://example.com/posts/anything",
        "https://www.linkedin.com/feed/",
        "https://www.linkedin.com/in/someone/",
        "https://www.linkedin.com/feed/update/not-a-urn/",
        "not a URL",
    ],
)
def test_canonical_post_url_rejects_ambiguous_or_non_post_targets(raw_url: str) -> None:
    with pytest.raises(ValueError, match="post_url"):
        LinkedInExtractor._canonical_post_url(raw_url)


@pytest.mark.asyncio
async def test_like_dry_run_never_clicks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extractor = object.__new__(LinkedInExtractor)
    extractor._page = MagicMock()
    extractor._navigate_to_page = AsyncMock()
    extractor._reaction_state = AsyncMock(
        return_value={"available": True, "reacted": False, "raw_label": "no reaction"}
    )
    extractor._click_standard_like = AsyncMock()
    monkeypatch.setattr(
        "linkedin_mcp_server.scraping.extractor.detect_rate_limit", AsyncMock()
    )

    result = await extractor.like_post(
        "https://www.linkedin.com/posts/example-1/",
        confirm_like=False,
        request_id="dry-run-like",
    )

    assert result["status"] == "not_submitted"
    assert result["verified"] is False
    extractor._click_standard_like.assert_not_awaited()


@pytest.mark.asyncio
async def test_like_does_not_toggle_an_existing_reaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extractor = object.__new__(LinkedInExtractor)
    extractor._page = MagicMock()
    extractor._navigate_to_page = AsyncMock()
    existing = {
        "available": True,
        "reacted": True,
        "raw_label": "Reaction button state: Like",
    }
    extractor._reaction_state = AsyncMock(return_value=existing)
    extractor._click_standard_like = AsyncMock()
    monkeypatch.setattr(
        "linkedin_mcp_server.scraping.extractor.detect_rate_limit", AsyncMock()
    )

    result = await extractor.like_post(
        "https://www.linkedin.com/posts/example-1/",
        confirm_like=True,
        request_id="existing-like",
    )

    assert result["status"] == "already_liked"
    assert result["verified"] is True
    extractor._click_standard_like.assert_not_awaited()


@pytest.mark.asyncio
async def test_comment_duplicate_is_not_submitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extractor = object.__new__(LinkedInExtractor)
    extractor._page = MagicMock()
    extractor._self_profile_url_for_engagement = AsyncMock(
        return_value="https://www.linkedin.com/in/test-user/"
    )
    extractor._navigate_to_page = AsyncMock()
    existing_comment = {"present": True, "author_anchors": 1, "matches": 1}
    extractor._matching_self_comment = AsyncMock(return_value=existing_comment)
    extractor._open_comment_composer = AsyncMock()
    monkeypatch.setattr(
        "linkedin_mcp_server.scraping.extractor.detect_rate_limit", AsyncMock()
    )

    result = await extractor.comment_on_post(
        "https://www.linkedin.com/posts/example-1/",
        "A concrete technical perspective.",
        confirm_comment=True,
        request_id="duplicate-comment",
    )

    assert result["status"] == "duplicate_comment"
    assert result["verified"] is True
    extractor._open_comment_composer.assert_not_awaited()
