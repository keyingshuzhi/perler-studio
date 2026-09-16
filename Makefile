.DEFAULT_GOAL := help

.PHONY: help backend-install frontend-install test backend-test frontend-test build up down logs

help:
	@echo "make backend-install   安装后端依赖"
	@echo "make frontend-install  安装前端依赖"
	@echo "make test              运行全部测试"
	@echo "make build             构建前端生产产物"
	@echo "make up|down|logs      管理 Docker Compose 服务"

backend-install:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

frontend-install:
	cd frontend && npm ci

backend-test:
	cd backend && .venv/bin/ruff format --check app tests && .venv/bin/ruff check app tests && .venv/bin/pytest -q

frontend-test:
	cd frontend && npm test

test: backend-test frontend-test

build:
	cd frontend && npm run build

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f
