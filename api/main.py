"""FastAPI application for Zwift PC remote control."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.models import HealthResponse
from api.routers import control, status

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="Zwift Control API",
    description="REST API for remote control of Zwift PC via Wake-on-LAN and SSH",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
# NOTE: Wildcard origins required for iOS Shortcuts (dynamic LAN IPs)
# See SECURITY.md for security implications - LOCAL NETWORK ONLY
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Local network only - see SECURITY.md
    allow_credentials=False,  # No credentials used (no authentication)
    allow_methods=["GET", "POST"],  # Explicit methods only
    allow_headers=["Content-Type"],  # Explicit headers only
)

# Include routers
app.include_router(control.router)
app.include_router(status.router)


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint for Docker healthcheck.

    Returns:
        HealthResponse indicating API is healthy
    """
    return HealthResponse(status="healthy")


@app.on_event("startup")
async def startup_event():
    """Log startup information (sanitized to protect sensitive data)."""
    logger.info("=" * 60)
    logger.info("Zwift Control API starting...")
    # Sanitize sensitive data in logs
    logger.info(f"PC Name: {settings.pc_name[:4]}***")
    logger.info(f"PC IP: {settings.pc_ip.rsplit('.', 1)[0]}.**")
    logger.info(f"PC MAC: **:**:**:**:{settings.pc_mac[-5:]}")
    logger.info(f"Log Level: {settings.log_level}")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Log shutdown information."""
    logger.info("Zwift Control API shutting down...")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=settings.api_port,
        log_level=settings.log_level.lower(),
    )
