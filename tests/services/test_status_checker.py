"""Tests for the status checker: a failed check must not read as 'not running'."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from api.services.status_checker import StatusChecker


@pytest.fixture
def checker(test_settings):
    """StatusChecker with test settings; each test scripts the SSH response."""
    with patch("api.services.status_checker.settings", test_settings):
        yield StatusChecker()


@pytest.mark.asyncio
async def test_zwift_unknown_when_check_times_out(checker):
    """A slow PC tells us nothing about Zwift, so running must not be False."""
    checker.ssh.execute_powershell = AsyncMock(side_effect=asyncio.TimeoutError())

    status = await checker.check_zwift_running()

    assert status.running is None


@pytest.mark.asyncio
async def test_zwift_not_running_when_no_process_found(checker):
    """Get-Process finding nothing is a real answer: Zwift is not running."""
    checker.ssh.execute_powershell = AsyncMock(return_value=("", "", 1))

    status = await checker.check_zwift_running()

    assert status.running is False


@pytest.mark.asyncio
async def test_zwift_running_when_process_found(checker):
    """A process record reports Zwift as running."""
    checker.ssh.execute_powershell = AsyncMock(
        return_value=('{"Id": 42, "CPU": 1.5, "WorkingSet64": 1048576}', "", 0)
    )

    status = await checker.check_zwift_running()

    assert status.running is True
    assert status.process_id == 42


@pytest.mark.asyncio
async def test_obs_unknown_when_check_times_out(checker):
    """OBS gets the same treatment as Zwift."""
    checker.ssh.execute_powershell = AsyncMock(side_effect=asyncio.TimeoutError())

    status = await checker.check_obs_running()

    assert status.running is None


@pytest.mark.asyncio
async def test_sunshine_unknown_when_check_times_out(checker):
    """A failed Sunshine check is unknown, not stopped."""
    checker.ssh.execute_powershell = AsyncMock(side_effect=asyncio.TimeoutError())

    status = await checker.check_sunshine_status()

    assert status.running is None
    assert status.status == "Unknown"


@pytest.mark.asyncio
async def test_sunshine_stopped_is_reported_as_stopped(checker):
    """A real Stopped answer stays a definite False."""
    checker.ssh.execute_powershell = AsyncMock(return_value=('{"Status": "Stopped"}', "", 0))

    status = await checker.check_sunshine_status()

    assert status.running is False
    assert status.status == "Stopped"
