# Unified startup script for VectorBT project

# 1. Start Backend in a new process
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd backend; .\venv\Scripts\activate; cd ..; uvicorn backend.main:app --reload"

# 2. Start Frontend in a new process
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev"

Write-Host "Both Backend and Frontend are starting in separate windows..." -ForegroundColor Green
