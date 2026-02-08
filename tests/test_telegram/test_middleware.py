"""Tests for access control middleware."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from telegram.ext import filters

from tycho.telegram.middleware import build_user_filter, unauthorized_handler


class TestBuildUserFilter:
    def test_empty_list_allows_all(self):
        f = build_user_filter([])
        assert f is filters.ALL

    def test_with_users_returns_user_filter(self):
        f = build_user_filter([111, 222])
        assert isinstance(f, filters.User)

    def test_filter_contains_user_ids(self):
        f = build_user_filter([111, 222])
        assert f.user_ids == frozenset({111, 222})

    def test_single_user(self):
        f = build_user_filter([42])
        assert f.user_ids == frozenset({42})


class TestUnauthorizedHandler:
    @pytest.mark.asyncio
    async def test_replies_access_restricted(self):
        update = MagicMock()
        update.effective_message = AsyncMock()
        await unauthorized_handler(update, None)
        update.effective_message.reply_text.assert_awaited_once_with("Access restricted.")

    @pytest.mark.asyncio
    async def test_no_message_is_safe(self):
        update = MagicMock()
        update.effective_message = None
        # Should not raise
        await unauthorized_handler(update, None)
