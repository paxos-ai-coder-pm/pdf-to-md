@echo off
REM Double-click to launch the web UI (installs on first run).
python -c "import pdf2md" 2>nul || python -m pip install -e "%~dp0"
python -m pdf2md.server %*
