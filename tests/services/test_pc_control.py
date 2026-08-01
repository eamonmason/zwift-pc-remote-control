"""Tests for PC control service."""

from unittest.mock import AsyncMock, patch

import pytest

from api.config import Settings
from api.services.pc_control import PCControlService

PLUG_IP = "192.168.1.175"


@pytest.fixture
def pc_control_service(test_settings):
    """Create PCControlService instance with test settings."""
    with patch("api.services.pc_control.settings", test_settings):
        service = PCControlService()
        return service


@pytest.fixture
def plug_settings():
    """Settings with a plug configured and every wait shortened for tests."""
    return Settings(
        pc_name="test-pc",
        pc_ip="192.168.1.100",
        pc_mac="AA:BB:CC:DD:EE:FF",
        pc_user="testuser",
        ssh_key_path="/tmp/test_key",
        zwift_plug_ip=PLUG_IP,
        plug_switch_timeout=1,
        plug_settle_seconds=5,
        plug_poll_interval=1,
        plug_idle_watts=10.0,
        plug_idle_samples=3,
        shutdown_timeout=600,
    )


@pytest.fixture
def plug_service(plug_settings):
    """PCControlService with a plug configured, mocked Shelly, and no real sleeping."""
    with (
        patch("api.services.pc_control.settings", plug_settings),
        patch("api.services.pc_control.shelly") as mock_shelly,
        patch("api.services.pc_control.asyncio.sleep") as mock_sleep,
        patch("api.services.pc_control.ping_host") as mock_ping,
    ):
        mock_shelly.get_switch_state = AsyncMock(return_value=False)
        mock_shelly.get_power = AsyncMock(return_value=0.5)
        mock_shelly.set_switch = AsyncMock(return_value=True)
        mock_shelly.wait_for_switch_state = AsyncMock(return_value=True)
        mock_ping.return_value = (False, None)

        service = PCControlService()
        service.mock_shelly = mock_shelly
        service.mock_sleep = mock_sleep
        service.mock_ping = mock_ping
        yield service


def fake_clock(step: float = 10.0):
    """A monotonic clock that advances by `step` on every read."""
    state = {"t": 0.0}

    def _now():
        state["t"] += step
        return state["t"]

    return _now


@pytest.mark.asyncio
async def test_wake_pc_success(pc_control_service):
    """Test successful WoL packet sending."""
    with patch("api.services.pc_control.send_wol_packet") as mock_wol:
        mock_wol.return_value = True

        result = await pc_control_service.wake_pc()

        assert result is True
        mock_wol.assert_called_once()


@pytest.mark.asyncio
async def test_wake_pc_failure(pc_control_service):
    """Test WoL packet sending failure."""
    with patch("api.services.pc_control.send_wol_packet") as mock_wol:
        mock_wol.return_value = False

        result = await pc_control_service.wake_pc()

        assert result is False


@pytest.mark.asyncio
async def test_wait_for_network_success(pc_control_service):
    """Test successful network availability wait."""
    with patch("api.services.pc_control.wait_for_ping") as mock_wait:
        mock_wait.return_value = True

        result = await pc_control_service.wait_for_network()

        assert result is True
        mock_wait.assert_called_once()


@pytest.mark.asyncio
async def test_wait_for_ssh_success(pc_control_service):
    """Test successful SSH availability wait."""
    pc_control_service.ssh.wait_for_availability = AsyncMock(return_value=True)

    result = await pc_control_service.wait_for_ssh()

    assert result is True
    pc_control_service.ssh.wait_for_availability.assert_called_once()


@pytest.mark.asyncio
async def test_wait_for_desktop_success(pc_control_service):
    """Test successful desktop load detection."""
    pc_control_service.ssh.execute_powershell = AsyncMock(return_value=("explorer.exe", "", 0))

    result = await pc_control_service.wait_for_desktop()

    assert result is True


@pytest.mark.asyncio
async def test_wait_for_desktop_timeout(pc_control_service):
    """Test desktop load timeout."""
    # Mock empty output (explorer not found)
    pc_control_service.ssh.execute_powershell = AsyncMock(return_value=("", "", 1))

    # Reduce timeout for faster test
    with patch("api.services.pc_control.settings") as mock_settings:
        mock_settings.desktop_timeout = 1
        mock_settings.pc_ip = "192.168.1.100"
        mock_settings.pc_user = "testuser"
        mock_settings.ssh_key_path = "/tmp/test_key"
        mock_settings.ssh_connect_timeout = 5

        result = await pc_control_service.wait_for_desktop()

        assert result is False


@pytest.mark.asyncio
async def test_stop_sunshine_success(pc_control_service):
    """Test successful Sunshine service stop."""
    pc_control_service.ssh.execute_powershell = AsyncMock(
        return_value=("Stopped successfully", "", 0)
    )

    result = await pc_control_service.stop_sunshine()

    assert result is True


@pytest.mark.asyncio
async def test_stop_sunshine_not_found(pc_control_service):
    """Test Sunshine service not found."""
    pc_control_service.ssh.execute_powershell = AsyncMock(return_value=("Service not found", "", 1))

    result = await pc_control_service.stop_sunshine()

    assert result is False


@pytest.mark.asyncio
async def test_start_sunshine_success(pc_control_service):
    """Test successful Sunshine service start."""
    pc_control_service.ssh.execute_powershell = AsyncMock(
        return_value=("Started successfully", "", 0)
    )

    result = await pc_control_service.start_sunshine()

    assert result is True


@pytest.mark.asyncio
async def test_launch_zwift_success(pc_control_service):
    """Test successful Zwift launch via scheduled task."""
    pc_control_service.ssh.execute = AsyncMock(return_value=("SUCCESS", "", 0))

    result = await pc_control_service.launch_zwift()

    assert result is True


@pytest.mark.asyncio
async def test_launch_zwift_failure(pc_control_service):
    """Test Zwift launch failure."""
    pc_control_service.ssh.execute = AsyncMock(return_value=("", "Task not found", 1))

    result = await pc_control_service.launch_zwift()

    assert result is False


@pytest.mark.asyncio
async def test_activate_zwift_launcher_success(pc_control_service, monkeypatch):
    """Test successful Zwift launcher activation via scheduled task."""
    pc_control_service.ssh.execute = AsyncMock(
        return_value=("SUCCESS: Attempted to run the scheduled task", "", 0)
    )

    # Mock asyncio.sleep to avoid 35-second delay
    async def mock_sleep(seconds):
        pass

    monkeypatch.setattr("asyncio.sleep", mock_sleep)

    result = await pc_control_service.activate_zwift_launcher()

    assert result is True

    # Verify scheduled task was triggered
    call_args = pc_control_service.ssh.execute.call_args
    command = call_args[0][0]
    assert 'schtasks /Run /TN "ZwiftLauncherKeys"' in command


@pytest.mark.asyncio
async def test_activate_zwift_launcher_failure(pc_control_service):
    """Test Zwift launcher activation failure."""
    pc_control_service.ssh.execute = AsyncMock(
        return_value=("", "ERROR: The system cannot find the path specified", 1)
    )

    result = await pc_control_service.activate_zwift_launcher()

    assert result is False


@pytest.mark.asyncio
async def test_activate_zwift_launcher_exception(pc_control_service):
    """Test Zwift launcher activation handles exceptions gracefully."""
    pc_control_service.ssh.execute = AsyncMock(side_effect=Exception("SSH connection lost"))

    result = await pc_control_service.activate_zwift_launcher()

    # Should return False, not raise exception (non-critical operation)
    assert result is False


@pytest.mark.asyncio
async def test_launch_sauce_success(pc_control_service):
    """Test successful Sauce launch."""
    pc_control_service.ssh.execute = AsyncMock(return_value=("SUCCESS", "", 0))

    result = await pc_control_service.launch_sauce()

    assert result is True


@pytest.mark.asyncio
async def test_launch_sauce_failure(pc_control_service):
    """Test Sauce launch failure (non-critical)."""
    pc_control_service.ssh.execute = AsyncMock(return_value=("", "Task not found", 1))

    # Should still return True (non-critical operation)
    result = await pc_control_service.launch_sauce()

    assert result is True


@pytest.mark.asyncio
async def test_wait_for_zwift_success(pc_control_service):
    """Test successful Zwift process detection."""
    pc_control_service.ssh.execute_powershell = AsyncMock(return_value=("ZwiftApp", "", 0))

    result = await pc_control_service.wait_for_zwift()

    assert result is True


@pytest.mark.asyncio
async def test_wait_for_zwift_timeout(pc_control_service):
    """Test Zwift process detection timeout."""
    # Mock empty output (Zwift not found)
    pc_control_service.ssh.execute_powershell = AsyncMock(return_value=("", "", 1))

    # Reduce timeout for faster test
    with patch("api.services.pc_control.settings") as mock_settings:
        mock_settings.zwift_timeout = 1
        mock_settings.pc_ip = "192.168.1.100"
        mock_settings.pc_user = "testuser"
        mock_settings.ssh_key_path = "/tmp/test_key"
        mock_settings.ssh_connect_timeout = 5

        result = await pc_control_service.wait_for_zwift()

        assert result is False


@pytest.mark.asyncio
async def test_set_process_priorities_success(pc_control_service):
    """Test successful process priority setting."""
    pc_control_service.ssh.execute_powershell = AsyncMock(
        return_value=("Zwift: High priority\nOBS: BelowNormal priority", "", 0)
    )

    result = await pc_control_service.set_process_priorities()

    assert result is True


@pytest.mark.asyncio
async def test_set_process_priorities_exception(pc_control_service):
    """Test process priority setting handles exceptions gracefully."""
    pc_control_service.ssh.execute_powershell = AsyncMock(side_effect=Exception("SSH error"))

    # Should return True (non-critical operation)
    result = await pc_control_service.set_process_priorities()

    assert result is True


@pytest.mark.asyncio
async def test_shutdown_pc_success(pc_control_service):
    """Test successful PC shutdown."""
    pc_control_service.ssh.execute = AsyncMock(return_value=("", "", 0))

    result = await pc_control_service.shutdown_pc()

    assert result is True


@pytest.mark.asyncio
async def test_shutdown_pc_failure(pc_control_service):
    """Test PC shutdown failure."""
    pc_control_service.ssh.execute = AsyncMock(side_effect=Exception("Connection lost"))

    result = await pc_control_service.shutdown_pc()

    assert result is False


@pytest.mark.asyncio
async def test_shutdown_pc_nonzero_return_code(pc_control_service):
    """A rejected shutdown command must not report success.

    The stop sequence keys the power cut off this result, so a false positive
    here would mean cutting mains to a PC that was never asked to shut down.
    """
    pc_control_service.ssh.execute = AsyncMock(return_value=("", "Access is denied.", 5))

    result = await pc_control_service.shutdown_pc()

    assert result is False


@pytest.mark.asyncio
async def test_full_start_sequence_success(pc_control_service):
    """Test successful full start sequence."""
    # Mock all steps to succeed
    pc_control_service.wake_pc = AsyncMock(return_value=True)
    pc_control_service.wait_for_network = AsyncMock(return_value=True)
    pc_control_service.wait_for_ssh = AsyncMock(return_value=True)
    pc_control_service.wait_for_desktop = AsyncMock(return_value=True)
    pc_control_service.stop_sunshine = AsyncMock(return_value=True)
    pc_control_service.launch_zwift = AsyncMock(return_value=True)
    pc_control_service.launch_sauce = AsyncMock(return_value=True)
    pc_control_service.wait_for_zwift = AsyncMock(return_value=True)
    pc_control_service.set_process_priorities = AsyncMock(return_value=True)

    result = await pc_control_service.full_start_sequence()

    assert result["success"] is True
    assert result["wol_sent"] is True
    assert result["network_available"] is True
    assert result["ssh_available"] is True
    assert result["desktop_loaded"] is True
    assert result["sunshine_stopped"] is True
    assert result["zwift_launched"] is True
    assert result["sauce_launched"] is True
    assert result["zwift_running"] is True
    assert result["priorities_set"] is True


@pytest.mark.asyncio
async def test_full_start_sequence_wol_failure(pc_control_service):
    """Test full start sequence fails at WoL step."""
    pc_control_service.wake_pc = AsyncMock(return_value=False)

    result = await pc_control_service.full_start_sequence()

    assert result["success"] is False
    assert result["wol_sent"] is False
    # Subsequent steps should not be attempted
    assert result["network_available"] is False


@pytest.mark.asyncio
async def test_full_start_sequence_zwift_launch_failure(pc_control_service):
    """Test full start sequence fails at Zwift launch."""
    # Mock steps up to Zwift launch
    pc_control_service.wake_pc = AsyncMock(return_value=True)
    pc_control_service.wait_for_network = AsyncMock(return_value=True)
    pc_control_service.wait_for_ssh = AsyncMock(return_value=True)
    pc_control_service.wait_for_desktop = AsyncMock(return_value=True)
    pc_control_service.stop_sunshine = AsyncMock(return_value=True)
    pc_control_service.launch_zwift = AsyncMock(return_value=False)

    result = await pc_control_service.full_start_sequence()

    assert result["success"] is False
    assert result["zwift_launched"] is False
    # Subsequent steps should not be attempted
    assert result["sauce_launched"] is False


@pytest.mark.asyncio
async def test_wake_only_sequence_success(pc_control_service):
    """Test successful wake-only sequence."""
    pc_control_service.wake_pc = AsyncMock(return_value=True)
    pc_control_service.wait_for_network = AsyncMock(return_value=True)
    pc_control_service.wait_for_ssh = AsyncMock(return_value=True)

    result = await pc_control_service.wake_only_sequence()

    assert result["success"] is True
    assert result["wol_sent"] is True
    assert result["network_available"] is True
    assert result["ssh_available"] is True


@pytest.mark.asyncio
async def test_wake_only_sequence_network_timeout(pc_control_service):
    """Test wake-only sequence fails at network wait."""
    pc_control_service.wake_pc = AsyncMock(return_value=True)
    pc_control_service.wait_for_network = AsyncMock(return_value=False)

    result = await pc_control_service.wake_only_sequence()

    assert result["success"] is False
    assert result["wol_sent"] is True
    assert result["network_available"] is False
    assert result["ssh_available"] is False


# --- Smart plug: powering on before WoL -------------------------------------


@pytest.mark.asyncio
async def test_power_on_plug_already_on_does_not_switch(plug_service):
    """An already-energised plug is left alone - no switching, no settle delay."""
    plug_service.mock_shelly.get_switch_state = AsyncMock(return_value=True)

    result = await plug_service.power_on_plug()

    assert result is True
    plug_service.mock_shelly.set_switch.assert_not_called()
    plug_service.mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_power_on_plug_switches_on_and_settles(plug_service):
    """A plug that is off gets switched on, confirmed, then given NIC settle time."""
    result = await plug_service.power_on_plug()

    assert result is True
    plug_service.mock_shelly.set_switch.assert_awaited_once_with(PLUG_IP, True)
    plug_service.mock_shelly.wait_for_switch_state.assert_awaited_once()
    plug_service.mock_sleep.assert_awaited_once_with(5)


@pytest.mark.asyncio
async def test_power_on_plug_unreachable_fails(plug_service):
    """An unreachable plug fails loudly - a de-energised PC cannot answer WoL."""
    plug_service.mock_shelly.get_switch_state = AsyncMock(return_value=None)

    result = await plug_service.power_on_plug()

    assert result is False
    plug_service.mock_shelly.set_switch.assert_not_called()


@pytest.mark.asyncio
async def test_power_on_plug_not_confirmed_fails(plug_service):
    """A plug that never reports "on" is not treated as powered."""
    plug_service.mock_shelly.wait_for_switch_state = AsyncMock(return_value=False)

    result = await plug_service.power_on_plug()

    assert result is False
    plug_service.mock_sleep.assert_not_called()


@pytest.mark.asyncio
async def test_power_on_plug_noop_when_unconfigured(pc_control_service, test_settings):
    """With no plug configured the API behaves exactly as it did before."""
    with (
        patch("api.services.pc_control.settings", test_settings),
        patch("api.services.pc_control.shelly") as mock_shelly,
    ):
        result = await pc_control_service.power_on_plug()

    assert result is True
    mock_shelly.get_switch_state.assert_not_called()


# --- Smart plug: cutting mains ----------------------------------------------


@pytest.mark.asyncio
async def test_power_off_plug_refuses_while_pc_still_pings(plug_service):
    """The ping gate is what stops mains being cut from a running PC."""
    plug_service.mock_ping.return_value = (True, 5)

    result = await plug_service.power_off_plug()

    assert result is False
    plug_service.mock_shelly.set_switch.assert_not_called()


@pytest.mark.asyncio
async def test_power_off_plug_switches_off(plug_service):
    """A live plug feeding a downed PC gets switched off and confirmed."""
    plug_service.mock_shelly.get_switch_state = AsyncMock(return_value=True)

    result = await plug_service.power_off_plug()

    assert result is True
    plug_service.mock_shelly.set_switch.assert_awaited_once_with(PLUG_IP, False)


@pytest.mark.asyncio
async def test_power_off_plug_already_off(plug_service):
    """An already-dead plug needs no command."""
    result = await plug_service.power_off_plug()

    assert result is True
    plug_service.mock_shelly.set_switch.assert_not_called()


@pytest.mark.asyncio
async def test_power_off_plug_unreachable_leaves_power_on(plug_service):
    """An unreachable plug is reported, never assumed off."""
    plug_service.mock_shelly.get_switch_state = AsyncMock(return_value=None)

    result = await plug_service.power_off_plug()

    assert result is False
    plug_service.mock_shelly.set_switch.assert_not_called()


# --- Smart plug: confirming the PC is really down ---------------------------


@pytest.mark.asyncio
async def test_wait_for_pc_powered_down_waits_for_draw_to_settle(plug_service):
    """Ping going quiet is not enough - power draw must settle too."""
    plug_service.mock_ping.side_effect = [(True, 5), (False, None)]
    # Windows carries on installing updates with the network down.
    plug_service.mock_shelly.get_power = AsyncMock(side_effect=[85.0, 62.0, 4.1, 3.9, 4.0])

    with patch("api.services.pc_control.time.monotonic", side_effect=fake_clock()):
        result = await plug_service.wait_for_pc_powered_down()

    assert result is True
    assert plug_service.mock_shelly.get_power.await_count == 5


@pytest.mark.asyncio
async def test_wait_for_pc_powered_down_resets_on_power_spike(plug_service):
    """A spike part-way through the idle window restarts the count."""
    plug_service.mock_shelly.get_power = AsyncMock(side_effect=[2.0, 2.0, 90.0, 2.0, 2.0, 2.0])

    with patch("api.services.pc_control.time.monotonic", side_effect=fake_clock()):
        result = await plug_service.wait_for_pc_powered_down()

    assert result is True
    assert plug_service.mock_shelly.get_power.await_count == 6


@pytest.mark.asyncio
async def test_wait_for_pc_powered_down_times_out_while_still_drawing(plug_service, plug_settings):
    """A PC still drawing power at the deadline is never confirmed down."""
    plug_settings.shutdown_timeout = 30
    plug_service.mock_shelly.get_power = AsyncMock(return_value=85.0)

    with patch("api.services.pc_control.time.monotonic", side_effect=fake_clock()):
        result = await plug_service.wait_for_pc_powered_down()

    assert result is False


@pytest.mark.asyncio
async def test_wait_for_pc_powered_down_unreadable_plug_is_not_proof(plug_service, plug_settings):
    """A plug that cannot be read never confirms a power-down."""
    plug_settings.shutdown_timeout = 30
    plug_service.mock_shelly.get_power = AsyncMock(return_value=None)

    with patch("api.services.pc_control.time.monotonic", side_effect=fake_clock()):
        result = await plug_service.wait_for_pc_powered_down()

    assert result is False


@pytest.mark.asyncio
async def test_wait_for_pc_powered_down_times_out_while_pinging(plug_service, plug_settings):
    """A PC that never stops answering ping fails the wait."""
    plug_settings.shutdown_timeout = 30
    plug_service.mock_ping.return_value = (True, 5)

    with patch("api.services.pc_control.time.monotonic", side_effect=fake_clock()):
        result = await plug_service.wait_for_pc_powered_down()

    assert result is False
    plug_service.mock_shelly.get_power.assert_not_called()


# --- Sequences ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_start_sequence_plug_failure_skips_wol(pc_control_service):
    """No mains, no point sending a magic packet."""
    pc_control_service.power_on_plug = AsyncMock(return_value=False)
    pc_control_service.wake_pc = AsyncMock(return_value=True)

    result = await pc_control_service.full_start_sequence()

    assert result["success"] is False
    assert result["plug_powered"] is False
    pc_control_service.wake_pc.assert_not_called()


@pytest.mark.asyncio
async def test_wake_only_sequence_powers_plug_before_wol(pc_control_service):
    """The wake-only path energises the plug too."""
    pc_control_service.power_on_plug = AsyncMock(return_value=True)
    pc_control_service.wake_pc = AsyncMock(return_value=True)
    pc_control_service.wait_for_network = AsyncMock(return_value=True)
    pc_control_service.wait_for_ssh = AsyncMock(return_value=True)

    result = await pc_control_service.wake_only_sequence()

    assert result["success"] is True
    assert result["plug_powered"] is True
    pc_control_service.power_on_plug.assert_awaited_once()


# The stop sequence itself lives in TaskManager (the only caller) and is
# covered in tests/services/test_task_manager.py.
