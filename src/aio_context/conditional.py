"""Conditional asynchronous context managers.

This module provides utilities for modifying the lifecycle of asynchronous
context managers conditionally.
"""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager, AsyncExitStack, asynccontextmanager


@asynccontextmanager
async def unless_event[AsyncCTX: AbstractAsyncContextManager](async_context: AsyncCTX, event: asyncio.Event) -> AsyncGenerator[AsyncCTX | None, None]:
    """Enters an async context manager unless an event is set.

    This function races the entering of the provided async context manager against the
    provided event. If the event is set before the context manager is fully entered,
    entering the context is canceled and None is yielded. Otherwise, the result of
    entering the context manager is yielded.

    Args:
        async_context: The async context manager to enter.
        event: The asyncio event to wait on.

    Yields:
        The result of the entered context manager, or None if the event is set first.
    """
    async with AsyncExitStack() as stack:
        async with asyncio.TaskGroup() as tg:
            enter_context_task = tg.create_task(stack.enter_async_context(async_context))
            event_wait_task = tg.create_task(event.wait())

            done, pending = asyncio.wait([enter_context_task, event_wait_task], return_when=asyncio.FIRST_COMPLETED)

            for task in pending:
                task.cancel()

        if enter_context_task in done:
            yield enter_context_task.result()
        else:
            yield None
