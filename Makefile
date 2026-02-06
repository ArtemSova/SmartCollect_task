#  ===== Переменные =====
PYTHON          ?= python
MANAGE          := $(PYTHON) manage.py
POETRY          ?= poetry
CELERY          ?= celery

DOCKER_COMPOSE   ?= docker compose
ENV_FILE         ?= .env

#  ===== help =====
help:                       ## help – показать список доступных команд
	@echo ""
	@echo "=== Локальные (host) команды ==="
	@echo "  make install        – установить зависимости через Poetry"
	@echo "  make venv           – открыть интерактивный Poetry‑shell"
	@echo "  make migrate        – makemigrations + migrate"
	@echo "  make run            – запустить Django dev‑server"
	@echo "  make test           – запустить тесты"
	@echo "  make worker         – запустить Celery‑worker (solo‑mode)"
	@echo "  make shell          – открыть Django shell"
	@echo "  make lint           – pylint для приложения payouts"
	@echo "  make format         – black для приложения payouts"
	@echo "  make clean          – удалить __pycache__, миграции, SQLite"
	@echo ""
	@echo "=== Docker (контейнер) команды ==="
	@echo "  make docker-build   – собрать Docker‑образы"
	@echo "  make docker-up      – поднять стек (detached)"
	@echo "  make docker-stop    – остановить контейнеры"
	@echo "  make docker-start   – возобновить работу контейнеров"
	@echo "  make docker-down    – остановить и удалить контейнеры + volumes"
	@echo "  make docker-logs    – следить за логами всех сервисов"
	@echo "  make docker-restart – перезапустить весь стек"
	@echo "  make docker-worker  – запустить Celery‑worker внутри контейнера"
	@echo "  make docker-test    – запустить тесты внутри контейнера web"
	@echo "  make docker-shell   – открыть bash‑shell в контейнере web"
	@echo "  make docker-clean   – удалить Docker‑volumes и локальные кеши"

#  ===== PHONY‑цели (защита от выполнения одноименных файлов) =====
.PHONY: help \
        install venv migrate run test worker shell lint format clean \
        docker-build docker-up docker-down docker-logs docker-restart \
        docker-worker docker-test docker-shell docker-clean

#  ====== Локальная (host) часть ======
install:                     ## install – установить зависимости через Poetry
	$(POETRY) config virtualenvs.in-project true
	$(POETRY) install

venv:                       ## venv – открыть интерактивный Poetry‑shell
	$(POETRY) shell

migrate:                    ## migrate – makemigrations + migrate
	$(MANAGE) makemigrations
	$(MANAGE) migrate

run:                        ## run – запустить Django‑dev‑сервер
	$(MANAGE) runserver 127.0.0.1:8000

test:                       ## test – запустить тестовый набор
	$(MANAGE) test

worker:                     ## worker – запустить Celery‑worker (solo‑mode, Windows‑friendly)
	$(CELERY) -A SmartCollect_task worker -l info -P solo

shell:                      ## shell – открыть Django‑shell
	$(MANAGE) shell

lint:                       ## lint – проверка кода (pylint) только в приложении payouts
	pylint ./payouts

format:                     ## format – автоформатирование (black) только в payouts
	black ./payouts

clean:                      ## clean – удалить __pycache__, миграции и SQLite‑файл
	@echo "Removing __pycache__ and migration artefacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -path "*/migrations/*.pyc" -delete
	find . -path "*/migrations/*.py" ! -name "__init__.py" -delete
	@echo "Removing SQLite DB (if any)…"
	- rm -f db.sqlite3
	@echo "Done."

#  ====== Docker‑часть ======
docker-build:               ## docker-build – собрать Docker‑образы без кэша
	$(DOCKER_COMPOSE) build --no-cache

docker-up:                  ## docker-up – поднять весь стек в фоне
	$(DOCKER_COMPOSE) up -d

docker-stop:                  ## docker-stop – остановить работу контейнеров (без очистки)
	$(DOCKER_COMPOSE) stop

docker-start:                  ## docker-start – восстановить работу контейнеров
	$(DOCKER_COMPOSE) start

docker-down:                ## docker-down – остановить и удалить контейнеры + volumes
	$(DOCKER_COMPOSE) down -v

docker-logs:                ## docker-logs – следить за логами всех сервисов
	$(DOCKER_COMPOSE) logs -f

docker-restart: docker-down docker-up   ## docker-restart – перезапустить стек

docker-worker:              ## docker-worker – Celery‑worker внутри контейнера
	$(DOCKER_COMPOSE) exec worker \
		$(POETRY) run $(CELERY) -A SmartCollect_task worker -l info -P solo

docker-test:                ## docker-test – запустить тесты внутри контейнера web
	$(DOCKER_COMPOSE) exec web \
		$(POETRY) run $(MANAGE) test

docker-shell:               ## docker-shell – открыть bash‑shell внутри контейнера web
	$(DOCKER_COMPOSE) exec -it web bash

docker-clean:               ## docker-clean – удалить Docker‑volumes + локальные кеши
	@echo "Removing Docker volumes..."
	$(DOCKER_COMPOSE) down -v
	@echo "Cleaning local artefacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	@echo "Done."
