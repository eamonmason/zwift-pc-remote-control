"""Tests for the background task sequences."""

from unittest.mock import AsyncMock, patch

import pytest

from api.models import TaskStatus
from api.services.task_manager import TaskManager


@pytest.fixture
def manager():
    """A TaskManager with a fully mocked PC control service."""
    task_manager = TaskManager()
    task_manager.pc_control = AsyncMock()
    return task_manager


@pytest.mark.asyncio
async def test_run_stop_sequence_shuts_down_then_cuts_mains(manager):
    """The happy path: shutdown command, confirmation, power cut."""
    manager.pc_control.shutdown_pc.return_value = True
    manager.pc_control.wait_for_pc_powered_down.return_value = True
    manager.pc_control.power_off_plug.return_value = True
    task = manager.create_task("stop")

    with patch("api.services.task_manager.ping_host") as mock_ping:
        mock_ping.return_value = (True, 5)
        await manager.run_stop_sequence(task.task_id)

    assert manager.get_task(task.task_id).status == TaskStatus.COMPLETED
    manager.pc_control.shutdown_pc.assert_awaited_once()
    manager.pc_control.power_off_plug.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_stop_sequence_offline_pc_still_cuts_mains(manager):
    """A PC already off the network still needs its mains cut.

    This is what a machine installing updates on the way out looks like: no
    ping, but still drawing power.
    """
    manager.pc_control.wait_for_pc_powered_down.return_value = True
    manager.pc_control.power_off_plug.return_value = True
    task = manager.create_task("stop")

    with patch("api.services.task_manager.ping_host") as mock_ping:
        mock_ping.return_value = (False, None)
        await manager.run_stop_sequence(task.task_id)

    assert manager.get_task(task.task_id).status == TaskStatus.COMPLETED
    manager.pc_control.shutdown_pc.assert_not_called()
    manager.pc_control.power_off_plug.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_stop_sequence_unconfirmed_power_down_leaves_mains_on(manager):
    """No confirmation means the plug is never touched."""
    manager.pc_control.shutdown_pc.return_value = True
    manager.pc_control.wait_for_pc_powered_down.return_value = False
    task = manager.create_task("stop")

    with patch("api.services.task_manager.ping_host") as mock_ping:
        mock_ping.return_value = (True, 5)
        await manager.run_stop_sequence(task.task_id)

    failed = manager.get_task(task.task_id)
    assert failed.status == TaskStatus.FAILED
    assert "mains left on" in failed.error.lower()
    manager.pc_control.power_off_plug.assert_not_called()


@pytest.mark.asyncio
async def test_run_stop_sequence_rejected_shutdown_stops_early(manager):
    """A PC that refuses to shut down is never de-energised."""
    manager.pc_control.shutdown_pc.return_value = False
    task = manager.create_task("stop")

    with patch("api.services.task_manager.ping_host") as mock_ping:
        mock_ping.return_value = (True, 5)
        await manager.run_stop_sequence(task.task_id)

    assert manager.get_task(task.task_id).status == TaskStatus.FAILED
    manager.pc_control.wait_for_pc_powered_down.assert_not_called()
    manager.pc_control.power_off_plug.assert_not_called()


@pytest.mark.asyncio
async def test_run_start_sequence_powers_plug_before_wol(manager):
    """Nothing is sent to a PC that has no mains."""
    manager.pc_control.power_on_plug.return_value = False
    task = manager.create_task("start")

    await manager.run_start_sequence(task.task_id)

    failed = manager.get_task(task.task_id)
    assert failed.status == TaskStatus.FAILED
    assert "mains power" in failed.error.lower()
    manager.pc_control.wake_pc.assert_not_called()


@pytest.mark.asyncio
async def test_run_wake_sequence_powers_plug_before_wol(manager):
    """The wake-only path energises the plug first too."""
    manager.pc_control.power_on_plug.return_value = True
    manager.pc_control.wake_pc.return_value = True
    manager.pc_control.wait_for_network.return_value = True
    manager.pc_control.wait_for_ssh.return_value = True
    task = manager.create_task("wake")

    await manager.run_wake_sequence(task.task_id)

    assert manager.get_task(task.task_id).status == TaskStatus.COMPLETED
    manager.pc_control.power_on_plug.assert_awaited_once()
