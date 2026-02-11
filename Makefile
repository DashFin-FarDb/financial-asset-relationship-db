.PHONY: help install install-dev test lint format type-check clean run pre-commit docker-build docker-run docker-stop docker-clean

help:  ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install production dependencies
	pip install -r requirements.txt

install-dev:  ## Install development dependencies
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

test:  ## Run tests with coverage
	pytest --cov=src --cov-report=html --cov-report=term-missing -v

test-fast:  ## Run tests without coverage
	pytest -v

lint:  ## Run all linters
	flake8 src/ tests/
	pylint src/

format:  ## Format code with black and ruff
	black src/ tests/ app.py
	ruff check --fix --select I src/ tests/ app.py

format-check:  ## Check code formatting without making changes
	black --check --diff src/ tests/ app.py
	ruff check --select I src/ tests/ app.py

type-check:  ## Run type checking with mypy
	mypy src/ --ignore-missing-imports

pre-commit:  ## Install pre-commit hooks
	pre-commit install

pre-commit-run:  ## Run pre-commit hooks on all files
	pre-commit run --all-files

clean:  ## Clean up generated files
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

run:  ## Run the application
	python app.py

check:  ## Run all checks (format, lint, type, test)
	@echo "Running format check..."
	@make format-check
	@echo ""
	@echo "Running linters..."
	@make lint
	@echo ""
	@echo "Running type checker..."
	@make type-check
	@echo ""
	@echo "Running tests..."
	@make test
	@echo ""
	@echo "All checks passed! ✅"

# Docker commands
docker-build:  ## Build Docker image
	docker build -t financial-asset-db:latest .

docker-run:  ## Run Docker container
	docker run -d -p 7860:7860 --name financial-asset-db financial-asset-db:latest

docker-stop:  ## Stop Docker container
	docker stop financial-asset-db || true
	docker rm financial-asset-db || true

docker-clean:  ## Remove Docker image and container
	@make docker-stop
	docker rmi financial-asset-db:latest || true

docker-compose-up:  ## Start with docker-compose
	docker-compose up --build

docker-compose-down:  ## Stop docker-compose services
	docker-compose down

docker-compose-logs:  ## View docker-compose logs
	docker-compose logs -f

docker-shell:  ## Open shell in running container
	docker exec -it financial-asset-db /bin/bash

docker-dev:  ## Run in development mode with volumes
	docker-compose up
