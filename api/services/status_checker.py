"""Status checking service for PC, Zwift, and related services."""

import json
import logging

from api.config import settings
from api.models import (
    FullStatus,
    PCStatus,
    ServiceStatus,
    ZwiftStatus,
)
from api.utils.network import ping_host
from api.utils.ssh_client import SSHClient

logger = logging.getLogger(__name__)


class StatusChecker:
    """Service for checking status of PC, Zwift, and related services."""

    def __init__(self):
        """Initialize status checker with SSH client."""
        self.ssh = SSHClient(
            host=settings.pc_ip,
            username=settings.pc_user,
            key_path=settings.ssh_key_path,
            connect_timeout=settings.ssh_connect_timeout,
        )

    async def check_pc_online(self) -> PCStatus:
        """
        Check if PC is online via ping and SSH connectivity.

        Returns:
            PCStatus with online status, SSH availability, and response time
        """
        is_online, response_time_ms = await ping_host(settings.pc_ip, timeout=1)

        # Only check SSH if ping succeeds
        ssh_available = False
        if is_online:
            ssh_available = await self.ssh.is_available()

        return PCStatus(
            online=is_online,
            ssh_available=ssh_available,
            ip_address=settings.pc_ip,
            response_time_ms=response_time_ms,
        )

    async def check_zwift_running(self) -> ZwiftStatus:
        """
        Check if Zwift is running via SSH.

        Returns:
            ZwiftStatus with process information if running

        Note:
            PC must be online for this check to work
        """
        try:
            script = "Get-Process ZwiftApp -ErrorAction SilentlyContinue | Select-Object Id,CPU,WorkingSet64 | ConvertTo-Json"
            stdout, stderr, return_code = await self.ssh.execute_powershell(script, timeout=10)

            if return_code == 0 and stdout:
                # Parse JSON output
                try:
                    data = json.loads(stdout)
                    process_id = data.get("Id")
                    cpu_usage = data.get("CPU")
                    memory_bytes = data.get("WorkingSet64")

                    return ZwiftStatus(
                        running=True,
                        process_id=process_id,
                        cpu_usage=cpu_usage,
                        memory_mb=int(memory_bytes / (1024 * 1024)) if memory_bytes else None,
                    )
                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Failed to parse Zwift process info: {e}")

            return ZwiftStatus(running=False)

        except Exception as e:
            logger.error(f"Error checking Zwift status: {e}")
            return ZwiftStatus(running=False)

    async def check_sunshine_status(self) -> ServiceStatus:
        """
        Check Sunshine service status via SSH.

        Returns:
            ServiceStatus for Sunshine service
        """
        try:
            script = "Get-Service SunshineService -ErrorAction SilentlyContinue | Select-Object @{Name='Status';Expression={$_.Status.ToString()}} | ConvertTo-Json"
            stdout, stderr, return_code = await self.ssh.execute_powershell(script, timeout=10)

            if return_code == 0 and stdout:
                try:
                    data = json.loads(stdout)
                    status = data.get("Status")
                    return ServiceStatus(
                        name="SunshineService",
                        running=(status == "Running"),
                        status=status,
                    )
                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Failed to parse Sunshine status: {e}")

            return ServiceStatus(name="SunshineService", running=False, status="Unknown")

        except Exception as e:
            logger.error(f"Error checking Sunshine status: {e}")
            return ServiceStatus(name="SunshineService", running=False, status="Error")

    async def check_obs_running(self) -> ZwiftStatus:
        """
        Check if OBS is running via SSH.

        Returns:
            ZwiftStatus (reused model) with OBS process information if running
        """
        try:
            script = "Get-Process obs64 -ErrorAction SilentlyContinue | Select-Object Id,CPU,WorkingSet64 | ConvertTo-Json"
            stdout, stderr, return_code = await self.ssh.execute_powershell(script, timeout=10)

            if return_code == 0 and stdout:
                try:
                    data = json.loads(stdout)
                    process_id = data.get("Id")
                    cpu_usage = data.get("CPU")
                    memory_bytes = data.get("WorkingSet64")

                    return ZwiftStatus(
                        running=True,
                        process_id=process_id,
                        cpu_usage=cpu_usage,
                        memory_mb=int(memory_bytes / (1024 * 1024)) if memory_bytes else None,
                    )
                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Failed to parse OBS process info: {e}")

            return ZwiftStatus(running=False)

        except Exception as e:
            logger.error(f"Error checking OBS status: {e}")
            return ZwiftStatus(running=False)

    async def check_full_status(self) -> FullStatus:
        """
        Check comprehensive system status.

        Returns:
            FullStatus with all system information
        """
        # Always check PC online status first
        pc_status = await self.check_pc_online()

        # Only check other statuses if PC is online AND SSH is available
        zwift_status = None
        sunshine_status = None
        obs_status = None

        if pc_status.online and pc_status.ssh_available:
            try:
                zwift_status = await self.check_zwift_running()
                sunshine_status = await self.check_sunshine_status()
                obs_status = await self.check_obs_running()
            except Exception as e:
                logger.error(f"Error checking detailed status: {e}")

        return FullStatus(
            pc=pc_status,
            zwift=zwift_status,
            sunshine=sunshine_status,
            obs=obs_status,
        )
