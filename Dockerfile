# Stage 1: Builder
FROM python:3.13-slim AS builder

WORKDIR /build

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml ./

# Install dependencies using uv
RUN uv pip install --system --no-cache-dir -e .

# Stage 2: Runtime
FROM python:3.13-slim

# Install only essential system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wakeonlan \
    openssh-client \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && rm -rf /tmp/* /var/tmp/*

# Copy Python packages from builder (only site-packages)
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages

# Copy only necessary binaries from builder
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

# Create non-root user with specific UID for volume mounting
RUN useradd -m -u 1000 apiuser && \
    mkdir -p /home/apiuser/.ssh && \
    chown -R apiuser:apiuser /home/apiuser/.ssh && \
    chmod 700 /home/apiuser/.ssh

# Create SSH config to disable strict host key checking (local network)
RUN echo "Host *\n\
    StrictHostKeyChecking no\n\
    UserKnownHostsFile=/dev/null\n\
    LogLevel ERROR" > /home/apiuser/.ssh/config && \
    chown apiuser:apiuser /home/apiuser/.ssh/config && \
    chmod 600 /home/apiuser/.ssh/config

# Set working directory
WORKDIR /app

# Copy application code
COPY api/ ./api/

# Create logs directory and clean up
RUN mkdir -p /app/logs && chown -R apiuser:apiuser /app/logs && \
    find /usr/local/lib/python3.13 -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.13 -type f -name '*.pyc' -delete && \
    find /usr/local/lib/python3.13 -type f -name '*.pyo' -delete

# Switch to non-root user
USER apiuser

# Expose API port
EXPOSE 8000

# Health check using Python instead of wget
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=5)" || exit 1

# Run the application
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
