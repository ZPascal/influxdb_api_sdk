.PHONY: help test-unit test-integration test-all lint clean

PYTHONPATH ?= $(PWD)
INFLUXDB_HOST ?= localhost
INFLUXDB_PORT ?= 8086

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

test-unit: ## Run unit tests only
	PYTHONPATH=$(PYTHONPATH) uv run pytest tests/unittests -v --tb=short

test-integration: ## Start InfluxDB via Docker Compose and run integration tests
	@echo "Starting InfluxDB..."
	docker compose up -d
	@echo "Waiting for InfluxDB to be healthy..."
	@until docker compose ps influxdb | grep -q "healthy"; do \
		echo "  ... still waiting"; \
		sleep 2; \
	done
	@echo "InfluxDB is ready. Running integration tests..."
	PYTHONPATH=$(PYTHONPATH) \
	INFLUXDB_HOST=$(INFLUXDB_HOST) \
	INFLUXDB_PORT=$(INFLUXDB_PORT) \
	uv run pytest -m integration tests/integrationtests -v --tb=short; \
	EXIT_CODE=$$?; \
	echo "Stopping InfluxDB..."; \
	docker compose down; \
	exit $$EXIT_CODE

test-integration-keep: ## Run integration tests without stopping InfluxDB afterwards
	@echo "Starting InfluxDB (if not running)..."
	docker compose up -d
	@echo "Waiting for InfluxDB to be healthy..."
	@until docker compose ps influxdb | grep -q "healthy"; do \
		echo "  ... still waiting"; \
		sleep 2; \
	done
	@echo "InfluxDB is ready. Running integration tests..."
	PYTHONPATH=$(PYTHONPATH) \
	INFLUXDB_HOST=$(INFLUXDB_HOST) \
	INFLUXDB_PORT=$(INFLUXDB_PORT) \
	uv run pytest -m integration tests/integrationtests -v --tb=short

test-all: test-unit test-integration ## Run unit tests and integration tests

lint: ## Run linter
	uv run ruff check influxdb/ tests/

clean: ## Remove Docker containers and volumes
	docker compose down -v

