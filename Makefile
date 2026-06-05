.PHONY: install migrate dev stop typecheck

install:
	uv venv && uv pip install -r requirements.txt

migrate:
	.venv/bin/python migrate.py

dev:
	.venv/bin/uvicorn app.main:app --reload --port 8000

stop:
	@lsof -ti :8000 | xargs kill -9 2>/dev/null && echo "Stopped" || echo "Nothing running on :8000"

typecheck:
	.venv/bin/python -m mypy app/
