.PHONY: api web dev validate

api:
	uv run workflowtwin serve

web:
	npm --prefix apps/web run dev

dev:
	docker compose up --build

validate:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy src tests alembic scripts
	uv run pytest --cov
	npm --prefix apps/web run lint
	npm --prefix apps/web run typecheck
	npm --prefix apps/web run test
	npm --prefix apps/web run build
