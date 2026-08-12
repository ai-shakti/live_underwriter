# Live Underwriter — root convenience commands
# Run the backend API and frontend dev server from the repo root.

.PHONY: backend frontend api test install

## Start the FastAPI backend (http://localhost:8000)
api:
	cd backend && uv run live-underwriter-api

## Start the Vite frontend dev server (http://localhost:5173)
frontend:
	cd frontend && npm run dev

## Install backend + frontend dependencies
install:
	cd backend && uv sync --extra dev
	cd frontend && npm install

## Run backend tests
test:
	cd backend && uv run python -m pytest
