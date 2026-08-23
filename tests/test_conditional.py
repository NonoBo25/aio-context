import asyncio
from contextlib import asynccontextmanager

import pytest

from aio_context.conditional import unless_event


@asynccontextmanager
async def mock_context(delay_enter=0.0, delay_exit=0.0, exception_enter=None, exception_exit=None):
    """A mock context manager that records entry and exit."""
    mock_context.entered = False
    mock_context.exited = False
    
    if delay_enter:
        await asyncio.sleep(delay_enter)
        
    if exception_enter:
        raise exception_enter
        
    mock_context.entered = True
    
    try:
        yield "mock_result"
    finally:
        if delay_exit:
            await asyncio.sleep(delay_exit)
            
        if exception_exit:
            raise exception_exit
            
        mock_context.exited = True

@pytest.fixture(autouse=True)
def reset_mock_context():
    """Reset the mock_context state between tests."""
    mock_context.entered = False
    mock_context.exited = False


async def test_unless_event_not_set():
    """Core: normal execution when event is not set."""
    event = asyncio.Event()
    
    async with unless_event(mock_context(), event) as ctx:
        assert ctx == "mock_result"
        assert mock_context.entered is True
        assert mock_context.exited is False
        
    assert mock_context.exited is True


async def test_unless_event_already_set():
    """Core: event is already set before entering."""
    event = asyncio.Event()
    event.set()
    
    async with unless_event(mock_context(delay_enter=0.01), event) as ctx:
        assert ctx is None
        assert mock_context.entered is False
        
    assert mock_context.exited is False


async def test_unless_event_set_during_enter():
    """Core: event is set while context is entering."""
    event = asyncio.Event()
    
    async def set_event_later():
        await asyncio.sleep(0.05)
        event.set()
        
    task = asyncio.create_task(set_event_later())
    
    async with unless_event(mock_context(delay_enter=0.1), event) as ctx:
        assert ctx is None
        assert mock_context.entered is False
        
    assert mock_context.exited is False
    await task


async def test_unless_event_parent_task_cancelled():
    """Edge Case: Parent task is cancelled while entering context."""
    event = asyncio.Event()
    
    async def run_unless_event():
        async with unless_event(mock_context(delay_enter=0.1), event):
            pass # Should not reach here
            
    task = asyncio.create_task(run_unless_event())
    
    # Wait a bit to let it start entering
    await asyncio.sleep(0.05)
    
    # Cancel the parent task
    task.cancel()
    
    with pytest.raises(asyncio.CancelledError):
        await task
        
    # The context should not have finished entering, so exited should be False
    assert mock_context.entered is False
    assert mock_context.exited is False


async def test_unless_event_parent_task_cancelled_during_body():
    """Edge Case: Parent task is cancelled during the context body."""
    event = asyncio.Event()
    body_reached = False
    
    async def run_unless_event():
        nonlocal body_reached
        async with unless_event(mock_context(), event) as ctx:
            assert ctx == "mock_result"
            body_reached = True
            await asyncio.sleep(0.1) # Simulate long running body
            
    task = asyncio.create_task(run_unless_event())
    
    # Wait a bit to let the body start
    await asyncio.sleep(0.05)
    assert body_reached is True
    
    # Cancel the parent task
    task.cancel()
    
    with pytest.raises(asyncio.CancelledError):
        await task
        
    # The context should have been entered and then cleanly exited
    assert mock_context.entered is True
    assert mock_context.exited is True


async def test_unless_event_entry_exception():
    """Edge Case: Underlying context manager raises exception during __aenter__."""
    event = asyncio.Event()
    exc = ValueError("entry failed")
    
    with pytest.raises(ExceptionGroup):
        async with unless_event(mock_context(exception_enter=exc), event) as ctx:
            pass
            
    assert mock_context.entered is False
    assert mock_context.exited is False


async def test_unless_event_exit_exception():
    """Edge Case: Underlying context manager raises exception during __aexit__."""
    event = asyncio.Event()
    exc = ValueError("exit failed")
    
    with pytest.raises(ValueError, match="exit failed"):
        async with unless_event(mock_context(exception_exit=exc), event) as ctx:
            assert ctx == "mock_result"
            
    assert mock_context.entered is True
    assert mock_context.exited is False # Because exception prevents setting exited to True


async def test_unless_event_simultaneous_completion():
    """Edge Case: Event set and context entry finish in the exact same event loop iteration."""
    event = asyncio.Event()
    
    class SimultaneousContext:
        """A context manager that yields immediately, racing perfectly with event.set()."""
        async def __aenter__(self):
            # This yields control back to the loop once, exactly like sleep(0)
            await asyncio.sleep(0)
            return "simultaneous"
            
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    async def driver():
        # Schedule the event to be set immediately in the next loop iteration
        # This will compete with the sleep(0) inside __aenter__
        loop = asyncio.get_running_loop()
        loop.call_soon(event.set)
        
        async with unless_event(SimultaneousContext(), event) as ctx:
            return ctx
            
    # asyncio.wait(..., return_when=FIRST_COMPLETED) might return both tasks if they complete
    # in the same iteration. The code prefers enter_context_task in done.
    ctx = await driver()
    
    # If both tasks complete simultaneously, enter_context_task is in done.
    # So it yields the context. This verifies the deterministic tie-breaking logic.
    assert ctx == "simultaneous"

