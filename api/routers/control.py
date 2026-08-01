"""Control endpoints for starting, stopping, and waking the Zwift PC."""

import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException

from api.models import (
    StartResponse,
    StopResponse,
    SunshineResponse,
    Task,
    WakeResponse,
)
from api.services.pc_control import PCControlService
from api.services.status_checker import StatusChecker
from api.services.task_manager import task_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/control", tags=["control"])


@router.post("/start", response_model=StartResponse)
async def start_zwift(background_tasks: BackgroundTasks) -> StartResponse:
    """
    Wake PC and launch Zwift (full start sequence).

    This endpoint:
    1. Sends Wake-on-LAN packet
    2. Waits for PC to boot (~60s)
    3. Waits for SSH to become available
    4. Waits for Windows desktop to load
    5. Stops Sunshine service
    6. Launches Zwift via scheduled task
    6b. Activates Zwift launcher (Tab, Tab, Enter)
    7. Launches Sauce for Zwift
    8. Waits for Zwift to start
    9. Sets process priorities

    Returns:
        StartResponse with task ID for progress tracking
    """
    logger.info("Start Zwift request received")

    # Create task
    task = task_manager.create_task("start")

    # Run start sequence in background
    background_tasks.add_task(task_manager.run_start_sequence, task.task_id)

    return StartResponse(
        task_id=task.task_id,
        message="Start sequence initiated. Use the task ID to check progress.",
        estimated_duration_seconds=180,
    )


@router.post("/stop", response_model=StopResponse)
async def stop_pc(background_tasks: BackgroundTasks) -> StopResponse:
    """
    Shutdown the Zwift PC and cut its mains.

    This endpoint:
    1. Sends a shutdown command to the PC via SSH (skipped if the PC is already
       off the network - which is exactly what a Windows Update install on the
       way out looks like)
    2. Waits for the PC to be genuinely powered down, judged by the smart plug's
       power draw rather than by ping, which goes quiet long before Windows has
       finished installing updates
    3. Switches the smart plug off

    It runs in the background because step 2 can take tens of minutes. Poll the
    returned task ID for progress. Mains are cut only once the PC is confirmed
    down, and are left on otherwise.

    Returns:
        StopResponse with task ID for progress tracking
    """
    logger.info("Stop PC request received")

    # Create task
    task = task_manager.create_task("stop")

    # Run stop sequence in background
    background_tasks.add_task(task_manager.run_stop_sequence, task.task_id)

    return StopResponse(
        success=True,
        message="Stop sequence initiated. Mains will be cut once the PC is powered down.",
        task_id=task.task_id,
        estimated_duration_seconds=300,
    )


@router.post("/wake", response_model=WakeResponse)
async def wake_pc(background_tasks: BackgroundTasks) -> WakeResponse:
    """
    Wake PC via WoL (no Zwift launch).

    This endpoint:
    1. Sends Wake-on-LAN packet
    2. Waits for PC to boot (~60s)
    3. Waits for SSH to become available

    Useful for maintenance or manual control.

    Returns:
        WakeResponse with task ID for progress tracking
    """
    logger.info("Wake PC request received")

    # Create task
    task = task_manager.create_task("wake")

    # Run wake sequence in background
    background_tasks.add_task(task_manager.run_wake_sequence, task.task_id)

    return WakeResponse(
        task_id=task.task_id,
        message="Wake sequence initiated. PC will boot without launching Zwift.",
        estimated_duration_seconds=60,
    )


@router.get("/tasks/{task_id}", response_model=Task)
async def get_task_status(task_id: UUID) -> Task:
    """
    Get status of a background task.

    Args:
        task_id: Task UUID returned from start/wake endpoints

    Returns:
        Task object with current status and progress

    Raises:
        HTTPException: If task ID not found
    """
    task = task_manager.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found",
        )

    return task


@router.post("/sunshine/stop", response_model=SunshineResponse)
async def stop_sunshine() -> SunshineResponse:
    """
    Stop Sunshine game streaming service.

    This endpoint stops the Sunshine service to free NVENC encoder resources
    (~11% encoder + 2-3% CPU). Useful before starting Zwift for large events.

    Returns:
        SunshineResponse with success status and service status

    Raises:
        HTTPException: If PC is offline or SSH unavailable
    """
    logger.info("Stop Sunshine request received")

    # Check PC status
    status_checker = StatusChecker()
    pc_status = await status_checker.check_pc_online()

    if not pc_status.online:
        raise HTTPException(
            status_code=503,
            detail="PC is offline. Cannot stop Sunshine service.",
        )

    if not pc_status.ssh_available:
        raise HTTPException(
            status_code=503,
            detail="SSH connection not available. Cannot stop Sunshine service.",
        )

    # Stop Sunshine
    pc_control = PCControlService()
    success = await pc_control.stop_sunshine()

    if not success:
        return SunshineResponse(
            success=False,
            message="Failed to stop Sunshine service. Service may not be installed or already stopped.",
        )

    # Get current service status
    service_status = await status_checker.check_sunshine_status()

    return SunshineResponse(
        success=True,
        message="Sunshine service stopped successfully.",
        service_status=service_status,
    )


@router.post("/sunshine/start", response_model=SunshineResponse)
async def start_sunshine() -> SunshineResponse:
    """
    Start Sunshine game streaming service.

    This endpoint starts the Sunshine service for remote game streaming.

    Note: Sunshine consumes ~11% NVENC encoder + 2-3% CPU.

    Returns:
        SunshineResponse with success status and service status

    Raises:
        HTTPException: If PC is offline or SSH unavailable
    """
    logger.info("Start Sunshine request received")

    # Check PC status
    status_checker = StatusChecker()
    pc_status = await status_checker.check_pc_online()

    if not pc_status.online:
        raise HTTPException(
            status_code=503,
            detail="PC is offline. Cannot start Sunshine service.",
        )

    if not pc_status.ssh_available:
        raise HTTPException(
            status_code=503,
            detail="SSH connection not available. Cannot start Sunshine service.",
        )

    # Start Sunshine
    pc_control = PCControlService()
    success = await pc_control.start_sunshine()

    if not success:
        return SunshineResponse(
            success=False,
            message="Failed to start Sunshine service. Service may not be installed or process did not start properly.",
        )

    # Get current service status
    service_status = await status_checker.check_sunshine_status()

    return SunshineResponse(
        success=True,
        message="Sunshine service started successfully.",
        service_status=service_status,
    )


@router.post("/sunshine/toggle", response_model=SunshineResponse)
async def toggle_sunshine() -> SunshineResponse:
    """
    Toggle Sunshine game streaming service (start if stopped, stop if running).

    This endpoint checks the current state of Sunshine and toggles it:
    - If running: stops the service to free NVENC encoder (~11% encoder + 2-3% CPU)
    - If stopped: starts the service for remote game streaming

    Returns:
        SunshineResponse with success status and service status

    Raises:
        HTTPException: If PC is offline or SSH unavailable
    """
    logger.info("Toggle Sunshine request received")

    # Check PC status
    status_checker = StatusChecker()
    pc_status = await status_checker.check_pc_online()

    if not pc_status.online:
        raise HTTPException(
            status_code=503,
            detail="PC is offline. Cannot toggle Sunshine service.",
        )

    if not pc_status.ssh_available:
        raise HTTPException(
            status_code=503,
            detail="SSH connection not available. Cannot toggle Sunshine service.",
        )

    # Check current Sunshine status
    service_status = await status_checker.check_sunshine_status()
    pc_control = PCControlService()

    # Toggle based on current state
    if service_status.running:
        logger.info("Sunshine is running, stopping it...")
        success = await pc_control.stop_sunshine()
        action = "stopped"
    else:
        logger.info("Sunshine is stopped, starting it...")
        success = await pc_control.start_sunshine()
        action = "started"

    if not success:
        return SunshineResponse(
            success=False,
            message=f"Failed to {action[:-2]} Sunshine service. Service may not be installed or already in desired state.",
        )

    # Get updated service status
    service_status = await status_checker.check_sunshine_status()

    return SunshineResponse(
        success=True,
        message=f"Sunshine service {action} successfully.",
        service_status=service_status,
    )
