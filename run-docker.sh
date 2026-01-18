#!/bin/bash
# Run API in Docker using .env configuration

set -e

echo "=== Running Zwift Control API in Docker ==="

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env not found"
    echo "Copy .env.example to .env and configure with Docker paths"
    exit 1
fi

echo "Using configuration: .env (SSH key: /home/apiuser/.ssh/id_rsa)"
echo ""

# Run nerdctl compose
nerdctl compose up -d

echo ""
echo "✅ API started in Docker"
echo "Check logs: nerdctl compose logs -f"
echo "Stop: nerdctl compose down"
