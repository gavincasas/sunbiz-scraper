#!/bin/bash

# Install Playwright without requiring root access
python -m playwright install --with-deps firefox

# Create necessary directories
mkdir -p /opt/render/.cache/ms-playwright

# Set environment variable to disable sandbox (required for non-root)
echo "export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1" >> $HOME/.bashrc
echo "export PLAYWRIGHT_BROWSERS_PATH=/opt/render/.cache/ms-playwright" >> $HOME/.bashrc
