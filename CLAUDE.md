# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

This project is managed with `uv`.

- **Sync dependencies**: `uv sync`
- **Run code**: `uv run python ...`
- **Run tests**: *No test suite is currently configured in `pyproject.toml`.* Once standard tools like `pytest` are added, you can run a single test using `uv run pytest <file_path>::<test_function>`.
- **Type checking**: The project includes a `py.typed` marker indicating it provides inline types. Once a type checker is added, run it via `uv run mypy src/` or `uv run pyright`.

## Architecture

`aio-context` is a minimal library providing advanced `asyncio` context management utilities for Python 3.12+.

- **Context Utilities (`src/aio_context/context.py`)**: Handles complex asynchronous lifecycles. It utilizes modern Python 3.11+ concurrency primitives—specifically `asyncio.TaskGroup` and `AsyncExitStack`—to safely manage context entry and cancellation.
- **Race Pattern**: The core architectural pattern (demonstrated in `unless_event`) is racing the initialization of an asynchronous context manager against an external `asyncio.Event`. This is used to guarantee that context entry is safely aborted (yielding `None`) and pending tasks are properly cancelled if a specific trigger event fires before the context is fully entered.