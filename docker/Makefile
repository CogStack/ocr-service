PROJECT = ocr-service
CONTAINER_NAME = $(PROJECT)
CONTAINER_NAME_TEXT = $(PROJECT)-text-only
CONTAINER_NAME_DEV = $(PROJECT)-dev
CONTAINER_NAME_TEXT_DEV = $(PROJECT)-text-only-dev
COMPOSE_BASE = docker-compose.base.yml
COMPOSE_DEV = docker-compose.dev.yml
COMPOSE_PROD = docker-compose.prod.yml

SHELL := /usr/bin/env bash
.SHELLFLAGS := -o pipefail -c

DC_START_CMD := up -d
DC_STOP_CMD := stop
DC_DOWN_CMD := down

define WITH_ENV
set -a && source ../export_env_vars.sh;
endef

.PHONY: up down restart build logs logs-dev logs-text logs-text-dev health-check \
	start start-dev start-dev-build start-prod \
	stop-all load-env show-env

# utility commands

load-env:
	$(WITH_ENV) echo "Environment variables loaded."

show-env:
	${WITH_ENV} >/dev/null 2>&1; printenv | grep -E "^(OCR|OCR_SERVICE)" | sort

logs-dev:
	docker logs -f --tail 10000 ${CONTAINER_NAME_DEV}

logs-text:
	docker logs -f --tail 10000 ${CONTAINER_NAME_TEXT}

logs-text-dev:
	docker logs -f --tail 10000 ${CONTAINER_NAME_TEXT_DEV}

logs:
	docker logs -f --tail 10000 $(CONTAINER_NAME)

health-check:
	${WITH_ENV} curl -fsSL http://localhost:${OCR_SERVICE_EXTERNAL_PORT:-8090}/api/health

# start/stop services

start-dev:
	$(WITH_ENV) docker compose -f $(COMPOSE_DEV) $(DC_START_CMD)

start-dev-build:
	$(WITH_ENV) docker compose -f $(COMPOSE_DEV) ${DC_START_CMD} --build

start:
	$(WITH_ENV) docker compose -f $(COMPOSE_BASE) -f docker-compose.yml $(DC_START_CMD)

start-prod:
	$(WITH_ENV) docker compose -f $(COMPOSE_BASE) -f $(COMPOSE_PROD) $(DC_START_CMD)

stop-all:
	$(WITH_ENV) docker compose -f $(COMPOSE_BASE) -f $(COMPOSE_DEV) -f $(COMPOSE_PROD) -f docker-compose.yml ${DC_DOWN_CMD}
