"""Tests for async DB bridge."""

import pytest

from tycho.telegram.db_async import run_sync


@pytest.mark.asyncio
class TestRunSync:
    async def test_runs_sync_function(self):
        def add(a, b):
            return a + b
        result = await run_sync(add, 2, 3)
        assert result == 5

    async def test_runs_with_kwargs(self):
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"
        result = await run_sync(greet, "World", greeting="Hi")
        assert result == "Hi, World!"

    async def test_propagates_exception(self):
        def fail():
            raise ValueError("test error")
        with pytest.raises(ValueError, match="test error"):
            await run_sync(fail)

    async def test_runs_db_session(self, tg_db):
        from tycho.db import get_session
        engine, _ = tg_db
        session = await run_sync(get_session, engine)
        assert session is not None
        await run_sync(session.close)
