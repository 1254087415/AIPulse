"""Tests for retry and log_stage decorators."""

import logging

import pytest

from aipulse.core.decorators import log_stage, with_retry


@pytest.mark.unit
async def test_with_retry_succeeds_after_retries(caplog) -> None:
    caplog.set_level(logging.WARNING)
    attempts = 0

    @with_retry(max_retries=3, exceptions=(RuntimeError,))
    async def flaky() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("fail")
        return "ok"

    result = await flaky()
    assert result == "ok"
    assert attempts == 3
    assert "attempt 1/3 failed" in caplog.text


@pytest.mark.unit
async def test_with_retry_raises_after_exhausted(caplog) -> None:
    caplog.set_level(logging.WARNING)

    @with_retry(max_retries=2, exceptions=(RuntimeError,))
    async def always_fails() -> str:
        raise RuntimeError("fail")

    with pytest.raises(RuntimeError, match="fail"):
        await always_fails()

    assert "attempt 2/2 failed" in caplog.text


@pytest.mark.unit
async def test_log_stage_logs_start_and_complete(caplog) -> None:
    caplog.set_level(logging.INFO)

    @log_stage("test_stage")
    async def stage() -> str:
        return "done"

    result = await stage()
    assert result == "done"
    assert "[stage:test_stage] starting" in caplog.text
    assert "[stage:test_stage] completed" in caplog.text


@pytest.mark.unit
async def test_log_stage_logs_failure(caplog) -> None:
    caplog.set_level(logging.INFO)

    @log_stage("failing_stage")
    async def stage() -> str:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await stage()

    assert "[stage:failing_stage] starting" in caplog.text
    assert "[stage:failing_stage] failed" in caplog.text
