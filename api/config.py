"""Configuration management for Zwift Control API using Pydantic settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # PC Configuration (REQUIRED - no defaults for security)
    pc_name: str = Field(description="Zwift PC hostname (REQUIRED - no default for security)")
    pc_ip: str = Field(description="Zwift PC IP address (REQUIRED - no default for security)")
    pc_mac: str = Field(
        description="Zwift PC MAC address for WoL (REQUIRED - no default for security)"
    )
    pc_user: str = Field(description="SSH username for PC (REQUIRED - no default for security)")

    # Smart Plug Configuration
    # The Shelly Gen2 plug carrying mains for the PC. Optional: an empty IP
    # disables plug control entirely, so the API behaves exactly as it did
    # before the plug was fitted.
    zwift_plug_ip: str = Field(
        default="", description="Shelly plug IP address (empty disables plug control)"
    )

    # API Configuration
    api_port: int = Field(default=8000, description="API server port")
    log_level: str = Field(default="INFO", description="Logging level")

    # Timeout Configuration (in seconds)
    wol_timeout: int = Field(default=120, description="Timeout for PC to respond after WoL")
    ssh_timeout: int = Field(default=60, description="Timeout for SSH to become available")
    desktop_timeout: int = Field(default=60, description="Timeout for Windows desktop to load")
    zwift_timeout: int = Field(default=60, description="Timeout for Zwift to launch")

    # Plug Timing Configuration
    plug_switch_timeout: int = Field(
        default=30, description="Timeout for the plug to confirm a new switch state"
    )
    plug_settle_seconds: int = Field(
        default=10, description="Delay after energising the plug before sending WoL"
    )
    plug_poll_interval: int = Field(
        default=10, description="Interval between power-draw readings during shutdown"
    )
    plug_idle_watts: float = Field(
        default=10.0, description="Power draw at or below which the PC counts as off"
    )
    plug_idle_samples: int = Field(
        default=3, description="Consecutive idle power readings required before cutting mains"
    )
    shutdown_timeout: int = Field(
        default=1800,
        description="Cap on waiting for the PC to power down, sized for a Windows Update install",
    )

    # SSH Configuration
    ssh_key_path: str = Field(default="~/.ssh/id_rsa", description="Path to SSH private key")
    ssh_connect_timeout: int = Field(default=10, description="SSH connection timeout in seconds")

    # Process Configuration
    zwift_scheduled_task: str = Field(
        default="LaunchZwiftRemote", description="Scheduled task name for Zwift"
    )
    zwift_launcher_keys_task: str = Field(
        default="ZwiftLauncherKeys", description="Scheduled task name for Zwift launcher automation"
    )
    sauce_scheduled_task: str = Field(
        default="LaunchSauceRemote", description="Scheduled task name for Sauce"
    )


# Global settings instance
settings = Settings()
