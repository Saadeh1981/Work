Set-Location $PSScriptRoot

# Activate venv
.\.venv\Scripts\Activate.ps1

# Sanity check: must show .venv python
python -c "import sys; print(sys.executable)"

# Start API (loads .env)
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload --env-file .env

