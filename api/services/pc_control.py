"""PC control service for Wake-on-LAN, SSH commands, and Zwift management."""

import asyncio
import logging

from api.config import settings
from api.utils.network import send_wol_packet, wait_for_ping
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

    async def wake_pc(self) -> bool:
        """
        Send Wake-on-LAN packet to wake the PC.

        Returns:
            True if WoL packet was sent successfully
        """
        logger.info(f"Sending WoL packet to {settings.pc_name} ({settings.pc_mac})")
        return await send_wol_packet(settings.pc_mac)

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

        Returns:
            True if keyboard input was sent successfully
        """
        logger.info("Activating Zwift launcher (Tab, Tab, Enter)...")
        try:
            # PowerShell script to send keyboard input
            script = """
                # Wait for launcher window to appear
                Start-Sleep -Seconds 3

                # Send Tab, Tab, Enter using WScript.Shell
                $wshell = New-Object -ComObject wscript.shell
                $wshell.SendKeys('{TAB}')
                Start-Sleep -Milliseconds 500
                $wshell.SendKeys('{TAB}')
                Start-Sleep -Milliseconds 500
                $wshell.SendKeys('~')  # ~ is Enter key

                Write-Host 'Keyboard input sent to launcher'
            """
            stdout, stderr, return_code = await self.ssh.execute_powershell(script, timeout=15)
            if return_code == 0:
                logger.info("Zwift launcher activated successfully")
                return True
            else:
                logger.warning(f"Failed to activate launcher: {stderr}")
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

        Returns:
            True if shutdown command was sent successfully
        """
        logger.info("Sending shutdown command...")
        try:
            command = "shutdown /s /t 5"
            stdout, stderr, return_code = await self.ssh.execute(command, timeout=10)
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
            # Step 1: Send WoL packet
            results["wol_sent"] = await self.wake_pc()
            if not results["wol_sent"]:
                return results

            # Step 2: Wait for network
            results["network_available"] = await self.wait_for_network()
            if not results["network_available"]:
                return results

            # Step 3: Wait for SSH
            results["ssh_available"] = await self.wait_for_ssh()
            if not results["ssh_available"]:
                return results

            # Step 4: Wait for desktop
            results["desktop_loaded"] = await self.wait_for_desktop()
            if not results["desktop_loaded"]:
                return results

            # Step 5: Stop Sunshine
            results["sunshine_stopped"] = await self.stop_sunshine()

            # Step 6: Kill any existing Zwift processes
            results["zwift_killed"] = await self.kill_zwift_processes()

            # Step 7: Launch Zwift
            results["zwift_launched"] = await self.launch_zwift()
            if not results["zwift_launched"]:
                return results

            # Step 8: Activate Zwift launcher
            await self.activate_zwift_launcher()

            # Step 9: Launch Sauce
            results["sauce_launched"] = await self.launch_sauce()

            # Step 10: Wait for Zwift to start
            results["zwift_running"] = await self.wait_for_zwift()
            if not results["zwift_running"]:
                return results

            # Step 11: Set process priorities
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
            "wol_sent": False,
            "network_available": False,
            "ssh_available": False,
            "success": False,
        }

        try:
            # Step 1: Send WoL packet
            results["wol_sent"] = await self.wake_pc()
            if not results["wol_sent"]:
                return results

            # Step 2: Wait for network
            results["network_available"] = await self.wait_for_network()
            if not results["network_available"]:
                return results

            # Step 3: Wait for SSH
            results["ssh_available"] = await self.wait_for_ssh()
            if not results["ssh_available"]:
                return results

            results["success"] = True
            logger.info("Wake sequence completed successfully")
            return results

        except Exception as e:
            logger.error(f"Error in wake sequence: {e}")
            return results
