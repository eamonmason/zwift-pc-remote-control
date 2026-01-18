"""Task manager for tracking and executing background tasks."""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from api.models import Task, TaskProgress, TaskStatus
from api.services.pc_control import PCControlService

logger = logging.getLogger(__name__)


class TaskManager:
    """Manager for background task execution and tracking."""

    def __init__(self):
        """Initialize task manager with in-memory task store."""
        self.tasks: dict[UUID, Task] = {}
        self.pc_control = PCControlService()

    def create_task(self, task_type: str) -> Task:
        """
        Create a new task.

        Args:
            task_type: Type of task (start, wake, etc.)

        Returns:
            Created task object
        """
        task_id = uuid4()
        task = Task(
            task_id=task_id,
            status=TaskStatus.PENDING,
            task_type=task_type,
        )
        self.tasks[task_id] = task
        logger.info(f"Created task {task_id} ({task_type})")
        return task

    def get_task(self, task_id: UUID) -> Optional[Task]:
        """
        Get task by ID.

        Args:
            task_id: Task UUID

        Returns:
            Task object if found, None otherwise
        """
        return self.tasks.get(task_id)

    def update_task_progress(
        self,
        task_id: UUID,
        step: str,
        step_number: int,
        total_steps: int,
        details: Optional[str] = None,
    ) -> None:
        """
        Update task progress.

        Args:
            task_id: Task UUID
            step: Current step description
            step_number: Current step number
            total_steps: Total number of steps
            details: Optional additional details
        """
        task = self.tasks.get(task_id)
        if task:
            task.progress = TaskProgress(
                current_step=step,
                step_number=step_number,
                total_steps=total_steps,
                details=details,
            )
            logger.debug(f"Task {task_id} progress: {step} ({step_number}/{total_steps})")

    def mark_task_running(self, task_id: UUID) -> None:
        """Mark task as running."""
        task = self.tasks.get(task_id)
        if task:
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.utcnow()
            logger.info(f"Task {task_id} started")

    def mark_task_completed(self, task_id: UUID) -> None:
        """Mark task as completed."""
        task = self.tasks.get(task_id)
        if task:
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            logger.info(f"Task {task_id} completed")

    def mark_task_failed(self, task_id: UUID, error: str) -> None:
        """Mark task as failed with error message."""
        task = self.tasks.get(task_id)
        if task:
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.utcnow()
            task.error = error
            logger.error(f"Task {task_id} failed: {error}")

    async def run_start_sequence(self, task_id: UUID) -> None:
        """
        Run the full start sequence (wake + launch Zwift).

        Args:
            task_id: Task UUID to track progress

        This method runs in the background and updates task progress.
        """
        try:
            self.mark_task_running(task_id)

            # Step 1: Send WoL packet
            self.update_task_progress(task_id, "Sending Wake-on-LAN packet", 1, 9)
            wol_sent = await self.pc_control.wake_pc()
            if not wol_sent:
                self.mark_task_failed(task_id, "Failed to send WoL packet")
                return

            # Step 2: Wait for network
            self.update_task_progress(task_id, "Waiting for PC to respond to network", 2, 9)
            network_available = await self.pc_control.wait_for_network()
            if not network_available:
                self.mark_task_failed(task_id, "PC did not respond to network")
                return

            # Step 3: Wait for SSH
            self.update_task_progress(task_id, "Waiting for SSH to become available", 3, 9)
            ssh_available = await self.pc_control.wait_for_ssh()
            if not ssh_available:
                self.mark_task_failed(task_id, "SSH did not become available")
                return

            # Step 4: Wait for desktop
            self.update_task_progress(task_id, "Waiting for Windows desktop to load", 4, 9)
            desktop_loaded = await self.pc_control.wait_for_desktop()
            if not desktop_loaded:
                self.mark_task_failed(task_id, "Windows desktop did not load")
                return

            # Step 5: Stop Sunshine
            self.update_task_progress(task_id, "Stopping Sunshine service", 5, 9)
            await self.pc_control.stop_sunshine()

            # Step 6: Launch Zwift
            self.update_task_progress(task_id, "Launching Zwift application", 6, 9)
            zwift_launched = await self.pc_control.launch_zwift()
            if not zwift_launched:
                self.mark_task_failed(task_id, "Failed to launch Zwift")
                return

            # Step 6b: Activate Zwift launcher (Tab, Tab, Enter)
            self.update_task_progress(task_id, "Activating Zwift launcher", 6, 9)
            await self.pc_control.activate_zwift_launcher()

            # Step 7: Launch Sauce
            self.update_task_progress(task_id, "Launching Sauce for Zwift", 7, 9)
            await self.pc_control.launch_sauce()

            # Step 8: Wait for Zwift to start
            self.update_task_progress(task_id, "Waiting for Zwift to start", 8, 9)
            zwift_running = await self.pc_control.wait_for_zwift()
            if not zwift_running:
                self.mark_task_failed(task_id, "Zwift did not start")
                return

            # Step 9: Set process priorities
            self.update_task_progress(task_id, "Setting process priorities", 9, 9)
            await self.pc_control.set_process_priorities()

            # All steps completed
            self.mark_task_completed(task_id)

        except Exception as e:
            logger.exception(f"Unexpected error in start sequence: {e}")
            self.mark_task_failed(task_id, f"Unexpected error: {str(e)}")

    async def run_wake_sequence(self, task_id: UUID) -> None:
        """
        Run the wake-only sequence (no Zwift launch).

        Args:
            task_id: Task UUID to track progress
        """
        try:
            self.mark_task_running(task_id)

            # Step 1: Send WoL packet
            self.update_task_progress(task_id, "Sending Wake-on-LAN packet", 1, 3)
            wol_sent = await self.pc_control.wake_pc()
            if not wol_sent:
                self.mark_task_failed(task_id, "Failed to send WoL packet")
                return

            # Step 2: Wait for network
            self.update_task_progress(task_id, "Waiting for PC to respond to network", 2, 3)
            network_available = await self.pc_control.wait_for_network()
            if not network_available:
                self.mark_task_failed(task_id, "PC did not respond to network")
                return

            # Step 3: Wait for SSH
            self.update_task_progress(task_id, "Waiting for SSH to become available", 3, 3)
            ssh_available = await self.pc_control.wait_for_ssh()
            if not ssh_available:
                self.mark_task_failed(task_id, "SSH did not become available")
                return

            # All steps completed
            self.mark_task_completed(task_id)

        except Exception as e:
            logger.exception(f"Unexpected error in wake sequence: {e}")
            self.mark_task_failed(task_id, f"Unexpected error: {str(e)}")


# Global task manager instance
task_manager = TaskManager()
