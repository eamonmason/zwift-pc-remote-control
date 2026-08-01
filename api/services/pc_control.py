"""PC control service for Wake-on-LAN, SSH commands, and Zwift management."""

import asyncio
import logging
import time

from api.config import settings
from api.utils import shelly
from api.utils.network import ping_host, send_wol_packet, wait_for_ping
from api.utils.ssh_client import SSHClient

logger = logging.getLogger(__name__)


class PCControlService:
    """Service for controlling the Zwift PC remotely."""

    def __init__(self):
        """Initialize PC control service with SSH client."""
        self.ssh = SSHClient(
            host=settings.pc_ip,
            username=settings.pc_user,
            key_path=settings.ssh_key_path,
            connect_timeout=settings.ssh_connect_timeout,
        )

    @property
    def plug_enabled(self) -> bool:
        """Whether a smart plug is configured in front of the PC."""
        return bool(settings.zwift_plug_ip)

    async def power_on_plug(self) -> bool:
        """
        Ensure the plug feeding the PC is energised, ready for a WoL packet.

        Fails loudly: a PC with no mains cannot answer a magic packet, so there
        is no point continuing a start sequence without power.

        Returns:
            True if the PC has mains power (or no plug is configured)
        """
        if not self.plug_enabled:
            logger.debug("No plug configured - assuming the PC is already on mains")
            return True

        plug_ip = settings.zwift_plug_ip
        state = await shelly.get_switch_state(plug_ip)

        if state is None:
            logger.error(f"Plug {plug_ip} is unreachable - cannot guarantee mains power to the PC")
            return False

        if state:
            logger.info(f"Plug {plug_ip} is already on")
            return True

        logger.info(f"Plug {plug_ip} is off - switching it on")
        if not await shelly.set_switch(plug_ip, True):
            logger.error(f"Plug {plug_ip} rejected the switch-on command")
            return False

        if not await shelly.wait_for_switch_state(
            plug_ip, True, timeout=settings.plug_switch_timeout
        ):
            return False

        # The NIC needs a moment to come up before it will honour a magic packet.
        logger.info(f"Waiting {settings.plug_settle_seconds}s for the PC's NIC to settle")
        await asyncio.sleep(settings.plug_settle_seconds)
        return True

    async def wait_for_pc_powered_down(self) -> bool:
        """
        Wait until the PC is genuinely powered down, not merely off the network.

        Two phases, sharing one overall timeout:

        1. Wait for ping to stop answering.
        2. Wait for the plug's power draw to settle at idle. This is the phase
           that survives a Windows Update install, where the network is already
           down but the machine is still drawing full power.

        Without a metering plug the second phase cannot be confirmed, and this
        returns False so the caller leaves mains on.

        Returns:
            True if the PC was confirmed powered down within the timeout
        """
        deadline = time.monotonic() + settings.shutdown_timeout

        logger.info("Waiting for the PC to stop responding to ping...")
        while time.monotonic() < deadline:
            is_online, _ = await ping_host(settings.pc_ip, timeout=1)
            if not is_online:
                break
            await asyncio.sleep(settings.plug_poll_interval)
        else:
            logger.warning(f"PC still answering ping after {settings.shutdown_timeout}s")
            return False

        logger.info("PC is off the network")

        if not self.plug_enabled:
            return True

        # Windows may now spend a long time installing updates with the network
        # down. Only a sustained drop in power draw proves it has finished.
        logger.info(
            f"Waiting for power draw to settle at or below {settings.plug_idle_watts}W "
            f"for {settings.plug_idle_samples} consecutive readings"
        )
        idle_readings = 0
        while time.monotonic() < deadline:
            power = await shelly.get_power(settings.zwift_plug_ip)

            if power is None:
                # An unreadable plug proves nothing, so it does not count.
                logger.warning(f"Could not read power draw from {settings.zwift_plug_ip}")
                idle_readings = 0
            elif power <= settings.plug_idle_watts:
                idle_readings += 1
                logger.info(
                    f"Power draw {power}W is idle ({idle_readings}/{settings.plug_idle_samples})"
                )
                if idle_readings >= settings.plug_idle_samples:
                    logger.info("PC is powered down")
                    return True
            else:
                if idle_readings:
                    logger.info(f"Power draw back up to {power}W - restarting the idle count")
                else:
                    logger.info(f"Power draw {power}W - PC is still busy (updates?)")
                idle_readings = 0

            await asyncio.sleep(settings.plug_poll_interval)

        logger.warning(
            f"Power draw did not settle within {settings.shutdown_timeout}s - "
            "leaving mains on rather than cutting power mid-write"
        )
        return False

    async def power_off_plug(self) -> bool:
        """
        Cut mains to the PC.

        Never fatal and never assumes: leaving power on is always safer than
        cutting it, so every uncertain case returns False with the plug on. The
        ping gate is the check that actually prevents de-energising a running PC.

        Returns:
            True if mains are confirmed off (or no plug is configured)
        """
        if not self.plug_enabled:
            logger.debug("No plug configured - nothing to switch off")
            return True

        plug_ip = settings.zwift_plug_ip

        is_online, _ = await ping_host(settings.pc_ip, timeout=1)
        if is_online:
            logger.error(
                f"{settings.pc_name} is still answering ping - refusing to cut mains. "
                "Leaving power ON."
            )
            return False

        state = await shelly.get_switch_state(plug_ip)
        if state is None:
            logger.warning(f"Plug {plug_ip} is unreachable - leaving mains on, cut it manually")
            return False

        if not state:
            logger.info(f"Plug {plug_ip} is already off")
            return True

        if not await shelly.set_switch(plug_ip, False):
            logger.warning(f"Plug {plug_ip} rejected the switch-off command")
            return False

        return await shelly.wait_for_switch_state(
            plug_ip, False, timeout=settings.plug_switch_timeout
        )

    async def wake_pc(self) -> bool:
        """
        Send Wake-on-LAN packet to wake the PC.

        Returns:
            True if WoL packet was sent successfully
        """
        logger.info(f"Sending WoL packet to {settings.pc_name} ({settings.pc_mac})")
        return await send_wol_packet(settings.pc_mac, settings.pc_ip)

    async def wait_for_network(self) -> bool:
        """
        Wait for PC to respond to ping after WoL.

        Returns:
            True if PC responded within timeout
        """
        return await wait_for_ping(settings.pc_ip, timeout=settings.wol_timeout, check_interval=2)

    async def wait_for_ssh(self) -> bool:
        """
        Wait for SSH to become available on the PC.

        Returns:
            True if SSH became available within timeout
        """
        return await self.ssh.wait_for_availability(timeout=settings.ssh_timeout, check_interval=2)

    async def wait_for_desktop(self) -> bool:
        """
        Wait for Windows desktop to load (explorer.exe process).

        Returns:
            True if desktop loaded within timeout
        """
        logger.info("Waiting for Windows desktop to load...")
        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < settings.desktop_timeout:
            try:
                stdout, _, return_code = await self.ssh.execute_powershell(
                    "Get-Process explorer -ErrorAction SilentlyContinue | Select-Object -First 1"
                )
                if return_code == 0 and stdout:
                    elapsed = int(asyncio.get_event_loop().time() - start_time)
                    logger.info(f"Desktop loaded (took {elapsed}s)")
                    return True
            except Exception as e:
                logger.debug(f"Desktop check failed: {e}")

            await asyncio.sleep(2)

        logger.warning(f"Desktop did not load within {settings.desktop_timeout}s")
        return False

    async def kill_zwift_processes(self) -> bool:
        """
        Kill any existing Zwift processes (ZwiftLauncher, ZwiftApp, Zwift).

        This is necessary before launching Zwift to ensure a clean start,
        especially if a previous launcher instance is stuck.

        Returns:
            True if processes were killed or none were running
        """
        logger.info("Killing any existing Zwift processes...")
        try:
            script = """
                $killed = @()
                $processes = Get-Process -Name 'ZwiftApp','ZwiftLauncher','Zwift' -ErrorAction SilentlyContinue
                if ($processes) {
                    $processes | ForEach-Object {
                        $killed += $_.ProcessName
                        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
                    }
                    Start-Sleep -Seconds 2
                    Write-Host "Killed: $($killed -join ', ')"
                } else {
                    Write-Host 'No Zwift processes found'
                }
            """
            stdout, stderr, return_code = await self.ssh.execute_powershell(script, timeout=10)
            logger.info(f"Zwift processes: {stdout.strip()}")
            return True
        except Exception as e:
            logger.warning(f"Error killing Zwift processes: {e}")
            # Not critical - continue anyway
            return True

    async def stop_sunshine(self) -> bool:
        """
        Stop Sunshine service to free NVENC encoder (~11% encoder + 2-3% CPU).

        Returns:
            True if service was stopped successfully or already stopped
        """
        logger.info("Stopping Sunshine service...")
        try:
            script = "$service = Get-Service SunshineService -ErrorAction SilentlyContinue; if (-not $service) { Write-Host 'Service not found'; exit 1 }; if ($service.Status -eq 'Running') { Stop-Service -Name SunshineService -Force -ErrorAction Stop; Start-Sleep -Seconds 2 }; $process = Get-Process sunshine -ErrorAction SilentlyContinue; if ($process) { Stop-Process -Id $process.Id -Force; Start-Sleep -Seconds 1 }; $verify = Get-Service SunshineService; if ($verify.Status -eq 'Stopped') { Write-Host 'Stopped successfully'; exit 0 } else { Write-Host 'Failed to stop'; exit 1 }"
            stdout, stderr, return_code = await self.ssh.execute_powershell(script, timeout=15)
            if return_code == 0:
                logger.info("Sunshine service stopped successfully")
                return True
            else:
                logger.warning(f"Failed to stop Sunshine: {stdout}")
                return False
        except Exception as e:
            logger.error(f"Error stopping Sunshine service: {e}")
            return False

    async def start_sunshine(self) -> bool:
        """
        Start Sunshine service for remote game streaming.

        Note: Sunshine consumes ~11% NVENC encoder + 2-3% CPU.

        Returns:
            True if service was started successfully or already running
        """
        logger.info("Starting Sunshine service...")
        try:
            script = "$service = Get-Service SunshineService -ErrorAction SilentlyContinue; if (-not $service) { Write-Host 'Service not found'; exit 1 }; if ($service.Status -eq 'Stopped') { Start-Service -Name SunshineService -ErrorAction Stop }; Start-Sleep -Seconds 3; $process = Get-Process sunshine -ErrorAction SilentlyContinue; $serviceCheck = Get-Service SunshineService; if ($serviceCheck.Status -eq 'Running' -and $process) { Write-Host 'Started successfully'; exit 0 } else { Write-Host 'Service running but process not detected'; exit 1 }"
            stdout, stderr, return_code = await self.ssh.execute_powershell(script, timeout=15)
            if return_code == 0:
                logger.info("Sunshine service started successfully")
                return True
            else:
                logger.warning(f"Sunshine may not be fully operational: {stdout}")
                return False
        except Exception as e:
            logger.error(f"Error starting Sunshine service: {e}")
            return False

    async def launch_zwift(self) -> bool:
        """
        Launch Zwift via scheduled task.

        Returns:
            True if scheduled task was triggered successfully
        """
        logger.info("Launching Zwift via scheduled task...")
        try:
            command = f'schtasks /Run /TN "{settings.zwift_scheduled_task}"'
            stdout, stderr, return_code = await self.ssh.execute(command)
            if return_code == 0:
                logger.info("Zwift launch task triggered")
                return True
            else:
                logger.error(f"Failed to launch Zwift: {stderr}")
                return False
        except Exception as e:
            logger.error(f"Error launching Zwift: {e}")
            return False

    async def activate_zwift_launcher(self) -> bool:
        """
        Send keyboard input to Zwift launcher (Tab, Tab, Enter).

        After the Zwift launcher opens, it requires keyboard interaction
        to actually start the main Zwift application:
        - Press Tab twice to navigate to the Launch button
        - Press Enter to activate it

        Uses a scheduled task to run in the user's interactive session,
        which is necessary due to Windows session isolation (SSH runs in
        Session 0, user desktop is in Session 1).

        Returns:
            True if keyboard input was sent successfully
        """
        logger.info("Activating Zwift launcher via scheduled task...")
        try:
            # Trigger the ZwiftLauncherKeys scheduled task
            # This task runs in the user's interactive session where it can
            # access the launcher window and send keyboard input
            command = f'schtasks /Run /TN "{settings.zwift_launcher_keys_task}"'
            stdout, stderr, return_code = await self.ssh.execute(command, timeout=10)

            if return_code == 0:
                logger.info("Launcher activation task triggered")
                # Wait for the automation script to complete (30s internal wait + 5s buffer)
                logger.info("Waiting 35 seconds for launcher automation to complete...")
                await asyncio.sleep(35)
                return True
            else:
                logger.warning(f"Failed to trigger launcher activation: {stderr}")
                return False
        except Exception as e:
            logger.warning(f"Error activating Zwift launcher: {e}")
            # Not critical - Zwift might launch anyway
            return False

    async def launch_sauce(self) -> bool:
        """
        Launch Sauce for Zwift via scheduled task.

        Returns:
            True if scheduled task was triggered successfully
        """
        logger.info("Launching Sauce for Zwift via scheduled task...")
        try:
            command = f'schtasks /Run /TN "{settings.sauce_scheduled_task}"'
            stdout, stderr, return_code = await self.ssh.execute(command)
            if return_code == 0:
                logger.info("Sauce launch task triggered")
                return True
            else:
                logger.warning(f"Failed to launch Sauce: {stderr}")
                # Not critical - continue anyway
                return True
        except Exception as e:
            logger.warning(f"Error launching Sauce: {e}")
            # Not critical - continue anyway
            return True

    async def wait_for_zwift(self) -> bool:
        """
        Wait for Zwift process to start.

        Returns:
            True if Zwift process was detected within timeout
        """
        logger.info("Waiting for Zwift to start...")
        start_time = asyncio.get_event_loop().time()

        while (asyncio.get_event_loop().time() - start_time) < settings.zwift_timeout:
            try:
                stdout, _, return_code = await self.ssh.execute_powershell(
                    "Get-Process ZwiftApp -ErrorAction SilentlyContinue | Select-Object -First 1"
                )
                if return_code == 0 and stdout:
                    elapsed = int(asyncio.get_event_loop().time() - start_time)
                    logger.info(f"Zwift started (took {elapsed}s)")
                    return True
            except Exception as e:
                logger.debug(f"Zwift check failed: {e}")

            await asyncio.sleep(2)

        logger.warning(f"Zwift did not start within {settings.zwift_timeout}s")
        return False

    async def set_process_priorities(self) -> bool:
        """
        Set process priorities (Zwift: High, OBS: BelowNormal).

        Returns:
            True if priorities were set successfully
        """
        logger.info("Setting process priorities...")
        try:
            script = """
                $zwift = Get-Process ZwiftApp -ErrorAction SilentlyContinue
                if ($zwift) {
                    $zwift.PriorityClass = 'High'
                    Write-Host 'Zwift: High priority'
                }

                $obs = Get-Process obs64 -ErrorAction SilentlyContinue
                if ($obs) {
                    $obs.PriorityClass = 'BelowNormal'
                    Write-Host 'OBS: BelowNormal priority'
                }
            """
            stdout, stderr, return_code = await self.ssh.execute_powershell(script)
            logger.info(f"Process priorities set: {stdout}")
            return True
        except Exception as e:
            logger.warning(f"Could not set process priorities: {e}")
            # Not critical - continue anyway
            return True

    async def shutdown_pc(self) -> bool:
        """
        Shutdown the PC.

        The return code matters: the stop sequence uses it to decide whether the
        PC was ever asked to shut down, and cutting mains to a PC that is still
        running would risk a corrupt filesystem.

        Returns:
            True if the shutdown command was accepted by the PC
        """
        logger.info("Sending shutdown command...")
        try:
            command = "shutdown /s /t 5"
            stdout, stderr, return_code = await self.ssh.execute(command, timeout=10)
            if return_code != 0:
                logger.error(f"Shutdown command failed (rc={return_code}): {stderr.strip()}")
                return False
            logger.info("Shutdown command sent")
            return True
        except Exception as e:
            logger.error(f"Error sending shutdown command: {e}")
            return False

    async def full_start_sequence(self) -> dict:
        """
        Execute the full wake-and-launch-zwift sequence.

        Returns:
            Dictionary with step results and overall success
        """
        results = {
            "plug_powered": False,
            "wol_sent": False,
            "network_available": False,
            "ssh_available": False,
            "desktop_loaded": False,
            "sunshine_stopped": False,
            "zwift_killed": False,
            "zwift_launched": False,
            "sauce_launched": False,
            "zwift_running": False,
            "priorities_set": False,
            "success": False,
        }

        try:
            # Step 1: Ensure the PC has mains power (a de-energised NIC cannot
            # hear a magic packet)
            results["plug_powered"] = await self.power_on_plug()
            if not results["plug_powered"]:
                return results

            # Step 2: Send WoL packet
            results["wol_sent"] = await self.wake_pc()
            if not results["wol_sent"]:
                return results

            # Step 3: Wait for network
            results["network_available"] = await self.wait_for_network()
            if not results["network_available"]:
                return results

            # Step 4: Wait for SSH
            results["ssh_available"] = await self.wait_for_ssh()
            if not results["ssh_available"]:
                return results

            # Step 5: Wait for desktop
            results["desktop_loaded"] = await self.wait_for_desktop()
            if not results["desktop_loaded"]:
                return results

            # Step 6: Stop Sunshine
            results["sunshine_stopped"] = await self.stop_sunshine()

            # Step 7: Kill any existing Zwift processes
            results["zwift_killed"] = await self.kill_zwift_processes()

            # Step 8: Launch Zwift
            results["zwift_launched"] = await self.launch_zwift()
            if not results["zwift_launched"]:
                return results

            # Step 9: Activate Zwift launcher
            await self.activate_zwift_launcher()

            # Step 10: Launch Sauce
            results["sauce_launched"] = await self.launch_sauce()

            # Step 11: Wait for Zwift to start
            results["zwift_running"] = await self.wait_for_zwift()
            if not results["zwift_running"]:
                return results

            # Step 12: Set process priorities
            results["priorities_set"] = await self.set_process_priorities()

            # All critical steps succeeded
            results["success"] = True
            logger.info("Full start sequence completed successfully")
            return results

        except Exception as e:
            logger.error(f"Error in start sequence: {e}")
            return results

    async def wake_only_sequence(self) -> dict:
        """
        Wake PC and wait for network/SSH only (no Zwift launch).

        Returns:
            Dictionary with step results and overall success
        """
        results = {
            "plug_powered": False,
            "wol_sent": False,
            "network_available": False,
            "ssh_available": False,
            "success": False,
        }

        try:
            # Step 1: Ensure the PC has mains power
            results["plug_powered"] = await self.power_on_plug()
            if not results["plug_powered"]:
                return results

            # Step 2: Send WoL packet
            results["wol_sent"] = await self.wake_pc()
            if not results["wol_sent"]:
                return results

            # Step 3: Wait for network
            results["network_available"] = await self.wait_for_network()
            if not results["network_available"]:
                return results

            # Step 4: Wait for SSH
            results["ssh_available"] = await self.wait_for_ssh()
            if not results["ssh_available"]:
                return results

            results["success"] = True
            logger.info("Wake sequence completed successfully")
            return results

        except Exception as e:
            logger.error(f"Error in wake sequence: {e}")
            return results
