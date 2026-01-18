#!/bin/bash
# Run API locally (on Mac) using .env.local configuration

set -e

echo "=== Running Zwift Control API Locally ==="

# Check if .env.local exists
if [ ! -f .env.local ]; then
    echo "❌ Error: .env.local not found"
    echo "Copy .env.example to .env.local and configure with Mac paths"
    exit 1
fi

# Use .env.local for local development
export ENV_FILE=.env.local

echo "Using configuration: .env.local (SSH key: ~/.ssh/id_rsa)"
echo ""

# Run with uvicorn
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload --env-file .env.local
