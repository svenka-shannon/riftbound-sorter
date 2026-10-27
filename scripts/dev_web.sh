#!/bin/bash
# Run web UI only in development mode (no hardware required)
# Uses MOCK_HARDWARE=1 to stub all GPIO/camera/servo calls
export MOCK_HARDWARE=1
cd "$(dirname "$0")/.."
source venv/bin/activate 2>/dev/null || true
python main.py --web-only "$@"
