"""Tests for PC control service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.services.pc_control import PCControlService


@pytest.fixture
def pc_control_service(test_settings):
    """Create PCControlService instance with test settings."""
    with patch("api.services.pc_control.settings", test_settings):
        service = PCControlService()
        return service


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
async def test_activate_zwift_launcher_success(pc_control_service):
    """Test successful Zwift launcher activation."""
    pc_control_service.ssh.execute_powershell = AsyncMock(
        return_value=("Keyboard input sent to launcher", "", 0)
    )

    result = await pc_control_service.activate_zwift_launcher()

    assert result is True

    # Verify PowerShell script was called
    call_args = pc_control_service.ssh.execute_powershell.call_args
    script = call_args[0][0]

    # Verify script contains expected keyboard commands
    assert "Start-Sleep -Seconds 3" in script
    assert "$wshell = New-Object -ComObject wscript.shell" in script
    assert "$wshell.SendKeys('{TAB}')" in script
    assert "Start-Sleep -Milliseconds 500" in script
    assert "$wshell.SendKeys('~')" in script  # Enter key


@pytest.mark.asyncio
async def test_activate_zwift_launcher_failure(pc_control_service):
    """Test Zwift launcher activation failure."""
    pc_control_service.ssh.execute_powershell = AsyncMock(
        return_value=("", "Failed to send keys", 1)
    )

    result = await pc_control_service.activate_zwift_launcher()

    assert result is False


@pytest.mark.asyncio
async def test_activate_zwift_launcher_exception(pc_control_service):
    """Test Zwift launcher activation handles exceptions gracefully."""
    pc_control_service.ssh.execute_powershell = AsyncMock(
        side_effect=Exception("SSH connection lost")
    )

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
