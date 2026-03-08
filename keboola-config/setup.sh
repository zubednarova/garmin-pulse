#!/bin/bash
set -Eeuo pipefail
echo "Installing Python dependencies..."
cd /app && uv sync
echo "Setup complete."
