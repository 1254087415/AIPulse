"""Decorators for retry and logging (Decorator/Proxy pattern)."""

import functools
import logging
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")

logger = logging.getLogger(__name__)


def with_retry(
    max_retries: int = 3,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator that retries an async function on failure."""

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: BaseException | None = None
            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc
                    logger.warning(
                        "%s attempt %d/%d failed: %s",
                        func.__name__,
                        attempt,
                        max_retries,
                        exc,
                    )
            assert last_exception is not None
            raise last_exception

        return wrapper

    return decorator


def log_stage(stage_name: str) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator that logs pipeline stage entry and exit."""

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            logger.info("[stage:%s] starting", stage_name)
            try:
                result = await func(*args, **kwargs)
                logger.info("[stage:%s] completed", stage_name)
                return result
            except Exception as exc:
                logger.exception("[stage:%s] failed: %s", stage_name, exc)
                raise

        return wrapper

    return decorator
