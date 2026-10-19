.PHONY: install migrate seed test api web
install:
	python -m pip install -e '.[dev]'
	cd frontend && npm ci
migrate:
	alembic upgrade head
seed:
	python scripts/seed.py
test:
	pytest -q
	ruff check backend scripts migrations
	cd frontend && npm run typecheck && npm run build
api:
	uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
web:
	cd frontend && npm run dev
