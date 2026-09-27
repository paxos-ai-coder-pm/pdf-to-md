#!/usr/bin/env sh
# Launch the web UI (installs on first run).
cd "$(dirname "$0")"
python3 -c "import pdf2md" 2>/dev/null || python3 -m pip install -e .
exec python3 -m pdf2md.server "$@"
