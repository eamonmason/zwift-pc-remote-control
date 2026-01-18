"""Status endpoints for checking PC, Zwift, and system status."""

import logging

from fastapi import APIRouter, HTTPException

from api.models import FullStatus, PCStatus, ZwiftStatus
from api.services.status_checker import StatusChecker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/status", tags=["status"])

# Initialize status checker
status_checker = StatusChecker()


@router.get("/pc", response_model=PCStatus)
async def get_pc_status() -> PCStatus:
    """
    Check if PC is online via ping and SSH connectivity.

    Returns:
        PCStatus with online status, SSH availability, and response time
    """
    logger.info("PC status check requested")
    return await status_checker.check_pc_online()


@router.get("/zwift", response_model=ZwiftStatus)
async def get_zwift_status() -> ZwiftStatus:
    """
    Check if Zwift is running via SSH.

    Requires PC to be online with SSH available.

    Returns:
        ZwiftStatus with process information if running
    """
    logger.info("Zwift status check requested")

    # Check PC online and SSH availability first
    pc_status = await status_checker.check_pc_online()
    if not pc_status.online:
        logger.warning("PC is offline, cannot check Zwift status")
        raise HTTPException(
            status_code=503,
            detail="PC is offline. Cannot check Zwift status.",
        )

    if not pc_status.ssh_available:
        logger.warning("SSH not available, cannot check Zwift status")
        raise HTTPException(
            status_code=503,
            detail="SSH connection not available. Cannot check Zwift status.",
        )

    return await status_checker.check_zwift_running()


@router.get("/full", response_model=FullStatus)
async def get_full_status() -> FullStatus:
    """
    Get comprehensive system status.

    Includes:
    - PC online status
    - Zwift process status (if PC online)
    - Sunshine service status (if PC online)
    - OBS process status (if PC online)

    Returns:
        FullStatus with all system information
    """
    logger.info("Full status check requested")
    return await status_checker.check_full_status()
