# Zwift PC Remote Control API

REST API service for remotely controlling a Zwift PC via Wake-on-LAN, SSH, and process management. Designed to run in Docker on a Raspberry Pi or any Linux system and be callable from iOS Siri Shortcuts.

## Features

- **Wake-on-LAN**: Wake PC from sleep/off state
- **Automated Zwift Launch**: Full sequence including Zwift launcher activation (Tab, Tab, Enter) and Sauce for Zwift
- **Remote Shutdown**: Safely power down the PC
- **Status Monitoring**: Check PC online status, Zwift process, and system services
- **Background Tasks**: Non-blocking operations with progress tracking
- **iOS Integration**: Designed for Siri Shortcuts control
- **Docker**: Containerized for easy deployment with nerdctl or docker
- **Multi-Architecture**: Supports amd64, arm64, and armv7 (Raspberry Pi)
- **Security Hardening**: No hardcoded credentials, sanitized logging, pre-commit hooks

## Recent Improvements (2026-01-18)

This API is now **production-ready** with comprehensive improvements:

- ✅ **Security Hardening**: Removed all hardcoded secrets, added pre-commit hooks, sanitized logs
- ✅ **Zwift Launcher Automation**: Automated keyboard input (Tab, Tab, Enter) to activate Zwift launcher
- ✅ **Docker Configuration**: All settings from `.env` file, no hardcoded values in docker-compose.yml
- ✅ **Comprehensive Testing**: 56% code coverage with 39 unit tests
- ✅ **Complete Documentation**: Security guide, automation details, Docker migration guide

See [CHANGES_SUMMARY.md](CHANGES_SUMMARY.md) for full details.

## Quick Start

### Prerequisites

- Docker/Nerdctl and Docker Compose (or nerdctl compose)
- SSH access to Zwift PC with public key authentication
- Zwift PC configured for Wake-on-LAN

### 1. Clone and Configure

Choose your deployment method:

**Option A: Docker Deployment** (recommended for production)

```bash
git clone <repository-url>
cd zwift/pc-remote-control

# Copy template and configure for Docker
cp .env.example .env

# Edit .env with your PC details
# IMPORTANT: Set SSH_KEY_HOST_PATH to absolute path (e.g., /Users/yourname/.ssh/id_rsa)
# Do NOT use ${HOME} variable - it won't expand correctly in Docker context
vim .env
```

**Option B: Local Development** (Mac/Linux)

```bash
git clone <repository-url>
cd zwift/pc-remote-control

# Copy template and configure for local dev
cp .env.example .env.local

# Edit .env.local with your PC details
# Set SSH_KEY_PATH=~/.ssh/id_rsa
vim .env.local
```

### 2. Setup SSH Key

Ensure your SSH key is configured:

```bash
# Test SSH access from host first
ssh ${PC_USER}@${PC_IP} "echo SSH works"

# Ensure key permissions are correct
chmod 600 ~/.ssh/id_rsa
```

### 3. Run the API

**Option A: Docker Deployment**

```bash
# Using helper script (recommended - uses nerdctl)
./run-docker.sh

# Or manually with nerdctl
nerdctl compose up -d

# Or with docker
docker compose up -d
```

**Option B: Local Development**

```bash
# Using helper script (recommended)
./run-local.sh

# Or manually
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload --env-file .env.local
```

The API will be available at `http://localhost:8000`.

### 4. Test the API

```bash
# Check API health
curl http://localhost:8000/health

# Check PC status
curl http://localhost:8000/api/v1/status/pc

# Start Zwift (returns task ID)
curl -X POST http://localhost:8000/api/v1/control/start
```

## API Endpoints

### Control Endpoints

**POST /api/v1/control/start**

Wake PC and launch Zwift (full sequence).

Response:

```json
{
  "task_id": "uuid",
  "message": "Start sequence initiated...",
  "estimated_duration_seconds": 180
}
```

**POST /api/v1/control/stop**

Shutdown the PC.

Response:

```json
{
  "success": true,
  "message": "Shutdown command sent. PC will shut down in 5 seconds."
}
```

**POST /api/v1/control/wake**

Wake PC only (no Zwift launch).

Response:

```json
{
  "task_id": "uuid",
  "message": "Wake sequence initiated...",
  "estimated_duration_seconds": 60
}
```

**GET /api/v1/control/tasks/{task_id}**

Check progress of a background task.

Response:

```json
{
  "task_id": "uuid",
  "status": "running",
  "task_type": "start",
  "progress": {
    "current_step": "Waiting for Zwift to start",
    "step_number": 8,
    "total_steps": 9
  },
  "created_at": "2026-01-17T10:00:00Z"
}
```

### Status Endpoints

**GET /api/v1/status/pc**

Check if PC is online.

Response:

```json
{
  "online": true,
  "ip_address": "192.168.1.194",
  "response_time_ms": 5,
  "timestamp": "2026-01-17T10:00:00Z"
}
```

**GET /api/v1/status/zwift**

Check if Zwift is running.

Response:

```json
{
  "running": true,
  "process_id": 12345,
  "cpu_usage": 4500.0,
  "memory_mb": 1024,
  "timestamp": "2026-01-17T10:00:00Z"
}
```

**GET /api/v1/status/full**

Get comprehensive system status.

Response:

```json
{
  "pc": {
    "online": true,
    "ip_address": "192.168.1.194",
    "response_time_ms": 5
  },
  "zwift": {
    "running": true,
    "process_id": 12345
  },
  "sunshine": {
    "name": "SunshineService",
    "running": false,
    "status": "Stopped"
  },
  "obs": {
    "running": false
  }
}
```

### Health Check

**GET /health**

API health check (used by Docker).

Response:

```json
{
  "status": "healthy",
  "timestamp": "2026-01-17T10:00:00Z"
}
```

## Configuration

All configuration is via environment variables (loaded from `.env` file):

### PC Configuration (REQUIRED)

- `PC_NAME`: Zwift PC hostname (REQUIRED - no default)
- `PC_IP`: Zwift PC IP address (REQUIRED - no default)
- `PC_MAC`: Zwift PC MAC address for WoL (REQUIRED - no default)
- `PC_USER`: SSH username (REQUIRED - no default)

### API Configuration

- `API_PORT`: API server port (default: 8000)
- `LOG_LEVEL`: Logging level (default: INFO)

### Timeout Configuration

- `WOL_TIMEOUT`: Timeout for PC to respond after WoL in seconds (default: 120)
- `SSH_TIMEOUT`: Timeout for SSH to become available in seconds (default: 60)
- `DESKTOP_TIMEOUT`: Timeout for Windows desktop to load in seconds (default: 60)
- `ZWIFT_TIMEOUT`: Timeout for Zwift to launch in seconds (default: 60)

### SSH Configuration

- `SSH_KEY_PATH`: Path to SSH private key inside container (default: ~/.ssh/id_rsa for local, /home/apiuser/.ssh/id_rsa for Docker)
- `SSH_KEY_HOST_PATH`: (Docker only) Absolute path to SSH key on host machine - **MUST be absolute path**, do NOT use ${HOME} variable
- `SSH_CONNECT_TIMEOUT`: SSH connection timeout in seconds (default: 10)

### Docker Configuration (Docker deployment only)

- `CONTAINER_USER_UID`: Container user UID (default: 1000)
- `CONTAINER_USER_GID`: Container user GID (default: 1000)

### Process Configuration

- `ZWIFT_SCHEDULED_TASK`: Scheduled task name for Zwift (default: LaunchZwiftRemote)
- `SAUCE_SCHEDULED_TASK`: Scheduled task name for Sauce (default: LaunchSauceRemote)

## Docker Deployment

The project uses `docker-compose.yml` configured to read all settings from `.env` file (no hardcoded values).

### Local Development with Nerdctl

```bash
# Using helper script
./run-docker.sh

# Or directly
nerdctl compose up -d
nerdctl compose logs -f

# Stop
nerdctl compose down
```

### Alternative: Docker CLI

```bash
# Using helper script
./run-docker.sh

# Or directly
docker compose up -d
docker compose logs -f

# Stop
docker compose down
```

### Raspberry Pi Production

1. Pull image from GitHub Container Registry:

```bash
nerdctl pull ghcr.io/<username>/zwift-control:latest
# or: docker pull ghcr.io/<username>/zwift-control:latest
```

2. Configure `.env` file (see **Option A: Docker Deployment** in Quick Start section)

3. Update `docker-compose.yml` to use pre-built image:

```yaml
services:
  zwift-api:
    image: ghcr.io/<username>/zwift-control:latest
    # Keep rest of configuration from docker-compose.yml
```

4. Run:

```bash
nerdctl compose up -d
# or: docker compose up -d
```

**Note**: All configuration is managed through `.env` file. The `docker-compose.yml` reads from `.env` including:
- PC credentials (no hardcoded values)
- SSH key paths (host and container)
- Container user UID/GID
- All timeouts and settings

## iOS Siri Shortcuts Integration

See [SIRI_API_INTEGRATION.md](SIRI_API_INTEGRATION.md) for detailed setup instructions.

Quick example - "Start Zwift" shortcut:

1. Add "Get Contents of URL" action
2. URL: `http://192.168.1.X:8000/api/v1/control/start`
3. Method: POST
4. Get task_id from response
5. Poll `/api/v1/control/tasks/{task_id}` every 30 seconds
6. Show notification when status is "completed"

## Development

### Install Dependencies

```bash
# Using uv (recommended)
pip install uv
uv pip install -e .[dev]

# Or using pip
pip install -e .[dev]
```

### Run Locally

```bash
uvicorn api.main:app --reload
```

API will be available at `http://localhost:8000`.

Interactive API docs: `http://localhost:8000/docs`

### Run Tests

```bash
pytest tests/ --cov=api --cov-report=term-missing
```

### Lint and Format

```bash
ruff check api/ tests/
ruff format api/ tests/
```

### Pre-commit Hooks

Install pre-commit hooks to automatically check code quality before commits:

```bash
# Install pre-commit (included in dev dependencies)
uv pip install -e .[dev]

# Install git hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files
```

Pre-commit hooks include:

- **Ruff**: Python linting and formatting (matches CI/CD)
- **Detect-secrets**: Prevents committing credentials
- **YAML/Markdown linting**: Ensures consistent formatting
- **Standard checks**: Trailing whitespace, EOF, merge conflicts

## Architecture

```
api/
├── main.py                    # FastAPI app entry point
├── config.py                  # Configuration management
├── models.py                  # Pydantic request/response models
├── services/
│   ├── pc_control.py          # WoL, SSH, shutdown logic
│   ├── status_checker.py      # PC and Zwift status checks
│   └── task_manager.py        # Background task orchestration
├── routers/
│   ├── control.py             # Control endpoints (start/stop/wake)
│   └── status.py              # Status endpoints
└── utils/
    ├── ssh_client.py          # Async SSH wrapper
    └── network.py             # Ping and WoL utilities
```

## Troubleshooting

### SSH Connection Fails

1. Verify SSH key permissions:

```bash
chmod 600 ~/.ssh/id_rsa
```

2. Test SSH from host:

```bash
ssh ${PC_USER}@${PC_IP} "echo test"
```

3. Check container SSH access:

```bash
nerdctl exec zwift-control-api ssh ${PC_USER}@${PC_IP} "echo test"
# or: docker exec zwift-control-api ssh ${PC_USER}@${PC_IP} "echo test"
```

4. Verify SSH key is mounted:

```bash
nerdctl exec zwift-control-api ls -la /home/apiuser/.ssh/id_rsa
# or: docker exec zwift-control-api ls -la /home/apiuser/.ssh/id_rsa
```

### Wake-on-LAN Not Working

1. Ensure PC BIOS has WoL enabled
2. Verify network adapter settings (Windows):
   - Device Manager → Network Adapter → Power Management
   - Enable "Allow this device to wake the computer"
3. Check if `wakeonlan` command is available in container:

```bash
nerdctl exec zwift-control-api wakeonlan ${PC_MAC}
# or: docker exec zwift-control-api wakeonlan ${PC_MAC}
```

### PC Online But SSH Unavailable

Check Windows OpenSSH service:

```powershell
Get-Service sshd
Start-Service sshd
Set-Service -Name sshd -StartupType 'Automatic'
```

### Container Healthcheck Failing

Check API logs:

```bash
nerdctl compose logs zwift-api
# or: docker compose logs zwift-api
```

Test health endpoint manually:

```bash
curl http://localhost:8000/health
```

## Security Considerations

### ⚠️ IMPORTANT: LOCAL NETWORK ONLY

This API is **explicitly designed for local network use ONLY** and has **NO authentication**. Do NOT expose to the public internet.

### Security Features

- **No Hardcoded Secrets**: All sensitive configuration loaded from environment variables
- **SSH Key Security**: SSH private key is mounted read-only (`:ro`) into container
- **Non-Root Container**: Runs as `apiuser` (UID 1000) for security
- **No Password Storage**: All authentication via SSH public keys
- **Sanitized Logging**: Sensitive data (IP, MAC, hostnames) masked in logs
- **Pre-commit Hooks**: Automated secret detection prevents credential commits

### Known Limitations

- **No API Authentication**: Anyone on your local network can access the API
- **SSH Host Key Verification Disabled**: Simplified setup for home network use
- **CORS Wildcard**: Required for iOS Shortcuts with dynamic LAN IPs
- **No TLS/HTTPS**: Traffic is unencrypted on local network

### Security Best Practices

1. **Network Protection**:
   - Keep API on trusted local network only
   - Enable router firewall (block inbound from internet)
   - NEVER port forward API ports (8000, 8001)
   - Use WPA3 or WPA2 WiFi encryption

2. **Environment Configuration**:
   - Copy `.env.example` to `.env` and configure with your PC details
   - Set restrictive permissions: `chmod 600 .env`
   - NEVER commit `.env` file to version control

3. **SSH Key Protection**:
   - Use SSH public key authentication only (no passwords)
   - Protect private key: `chmod 600 ~/.ssh/id_rsa`
   - Mount key as read-only in container (`:ro`)

### Acceptable vs NOT Acceptable Use

✅ **Acceptable**:

- Using API from Mac/iPhone on home WiFi
- iOS Shortcuts on your devices
- Docker deployment on local network
- VPN access to home network (with proper VPN security)

❌ **NOT Acceptable**:

- Exposing API to public internet via port forwarding
- Running on untrusted networks (coffee shop, hotel WiFi)
- Sharing API access with untrusted users
- Using for critical infrastructure (medical, safety systems)

### For More Details

See [SECURITY.md](SECURITY.md) for comprehensive security documentation including:

- Threat model and design philosophy
- Detailed security posture analysis
- Network security recommendations
- Secure deployment checklist
- Future authentication roadmap (v2.0)

## License

MIT

## Related Documentation

### Core Documentation

- [SECURITY.md](SECURITY.md) - Comprehensive security documentation and threat model
- [ZWIFT_LAUNCHER_AUTOMATION.md](ZWIFT_LAUNCHER_AUTOMATION.md) - Automated Zwift launcher keyboard input
- [DOCKER_COMPOSE_UPDATE.md](DOCKER_COMPOSE_UPDATE.md) - Docker configuration migration guide
- [CHANGES_SUMMARY.md](CHANGES_SUMMARY.md) - Complete change history and implementation phases

### Integration & Monitoring

- [SIRI_API_INTEGRATION.md](SIRI_API_INTEGRATION.md) - iOS Siri Shortcuts setup
- [CLAUDE.md](CLAUDE.md) - Zwift PC performance optimization guide
- [WINDOWS_MONITORING_GUIDE.md](WINDOWS_MONITORING_GUIDE.md) - Prometheus monitoring setup

## Support

For issues, questions, or contributions, please open an issue in the GitHub repository.
