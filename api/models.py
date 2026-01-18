"""Pydantic models for request/response schemas."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Status of a background task."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PCStatus(BaseModel):
    """PC online status response."""

    online: bool = Field(description="Whether the PC is reachable via ping")
    ssh_available: bool = Field(default=False, description="Whether SSH connection is available")
    ip_address: str = Field(description="PC IP address")
    response_time_ms: Optional[int] = Field(
        default=None, description="Ping response time in milliseconds"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp of status check"
    )


class ZwiftStatus(BaseModel):
    """Zwift process status response."""

    running: bool = Field(description="Whether Zwift is running")
    process_id: Optional[int] = Field(default=None, description="Zwift process ID if running")
    cpu_usage: Optional[float] = Field(
        default=None, description="CPU usage in seconds (cumulative)"
    )
    memory_mb: Optional[int] = Field(default=None, description="Memory usage in megabytes")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp of status check"
    )


class ServiceStatus(BaseModel):
    """Windows service status."""

    name: str = Field(description="Service name")
    running: bool = Field(description="Whether the service is running")
    status: Optional[str] = Field(default=None, description="Service status string")


class FullStatus(BaseModel):
    """Comprehensive system status."""

    pc: PCStatus = Field(description="PC online status")
    zwift: Optional[ZwiftStatus] = Field(
        default=None, description="Zwift status (null if PC offline)"
    )
    sunshine: Optional[ServiceStatus] = Field(default=None, description="Sunshine service status")
    obs: Optional[ZwiftStatus] = Field(default=None, description="OBS status")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Timestamp of status check"
    )


class TaskProgress(BaseModel):
    """Progress information for a background task."""

    current_step: str = Field(description="Current step being executed")
    step_number: int = Field(description="Current step number")
    total_steps: int = Field(description="Total number of steps")
    details: Optional[str] = Field(default=None, description="Additional details")


class Task(BaseModel):
    """Background task tracking."""

    task_id: UUID = Field(description="Unique task identifier")
    status: TaskStatus = Field(description="Task status")
    task_type: str = Field(description="Type of task (start, wake, etc.)")
    progress: Optional[TaskProgress] = Field(default=None, description="Task progress information")
    error: Optional[str] = Field(default=None, description="Error message if task failed")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Task creation timestamp"
    )
    started_at: Optional[datetime] = Field(default=None, description="Task start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Task completion timestamp")


class StartResponse(BaseModel):
    """Response from start endpoint."""

    task_id: UUID = Field(description="Task ID for tracking progress")
    message: str = Field(description="Informational message")
    estimated_duration_seconds: int = Field(default=180, description="Estimated time to completion")


class StopResponse(BaseModel):
    """Response from stop endpoint."""

    success: bool = Field(description="Whether shutdown command was sent successfully")
    message: str = Field(description="Informational message")


class WakeResponse(BaseModel):
    """Response from wake endpoint."""

    task_id: UUID = Field(description="Task ID for tracking progress")
    message: str = Field(description="Informational message")
    estimated_duration_seconds: int = Field(default=60, description="Estimated time for PC to boot")


class SunshineResponse(BaseModel):
    """Response from Sunshine control endpoints."""

    success: bool = Field(description="Whether the operation was successful")
    message: str = Field(description="Informational message")
    service_status: Optional[ServiceStatus] = Field(
        default=None, description="Current service status after operation"
    )


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(default="healthy", description="API health status")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Health check timestamp"
    )
