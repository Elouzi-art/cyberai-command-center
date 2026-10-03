.PHONY: up down test lint backend-test frontend-test schemas
up: ; docker compose up --build
down: ; docker compose down
lint: ; cd backend && ruff check . && ruff format --check . && mypy app ; cd frontend && npm run lint && npm run typecheck
test: backend-test frontend-test
backend-test: ; cd backend && pytest
frontend-test: ; cd frontend && npm test
