"""Async wrappers for synchronous DB operations."""

import asyncio
from functools import partial


async def run_sync(func, *args, **kwargs):
    """Run a synchronous function in a thread."""
    if kwargs:
        func = partial(func, **kwargs)
    return await asyncio.to_thread(func, *args)
