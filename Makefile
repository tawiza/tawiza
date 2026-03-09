.PHONY: help install dev test lint format clean docker-up docker-down migrate \
       preflight check-ports check-port health-check dev-start dev-stop dev-restart diagnose

# Variables
PYTHON := python3
PIP := $(PYTHON) -m pip
PYTEST := pytest
BLACK := black
RUFF := ruff
MYPY := mypy

# Directories
SRC_DIR := src
TEST_DIR := tests

# Default target
help:
	@echo "Tawiza Development Commands"
	@echo "=========================="
	@echo ""
	@echo "Setup:"
	@echo "  make install        Install production dependencies"
	@echo "  make dev            Install development dependencies"
	@echo "  make install-rocm   Install PyTorch with ROCm support"
	@echo ""
	@echo "Development:"
	@echo "  make run            Run the API server"
	@echo "  make format         Format code with Black"
	@echo "  make lint           Lint code with Ruff"
	@echo "  make typecheck      Type check with MyPy"
	@echo "  make test           Run tests"
	@echo "  make test-cov       Run tests with coverage"
	@echo "  make test-unit      Run unit tests only"
	@echo "  make test-integration  Run integration tests only"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up      Start all services with Docker Compose"
	@echo "  make docker-down    Stop all services"
	@echo "  make docker-logs    View Docker logs"
	@echo "  make docker-build   Build Docker images"
	@echo ""
	@echo "Database:"
	@echo "  make migrate        Run database migrations"
	@echo "  make migrate-create Create new migration"
	@echo ""
	@echo "DevOps:"
	@echo "  make preflight      Pre-start verification (ports, prereqs, config)"
	@echo "  make check-ports    Show status of all Tawiza ports"
	@echo "  make check-port PORT=8000  Check a specific port"
	@echo "  make health-check   Check health of running services"
	@echo "  make dev-start      Full startup: preflight + docker-up + instructions"
	@echo "  make dev-stop       Stop all services (Docker + local)"
	@echo "  make dev-restart    Stop + Start"
	@echo "  make diagnose       Full diagnostic (preflight + ports + health)"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean          Clean temporary files"
	@echo "  make clean-all      Clean everything including venv"

# Setup
install:
	$(PIP) install -e .

dev:
	$(PIP) install -e ".[dev]"
	pre-commit install

install-rocm:
	@echo "Installing PyTorch with ROCm support..."
	$(PIP) install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm6.2

install-ml:
	$(PIP) install -e ".[ml]"

# Development
run:
	uvicorn src.interfaces.api.main:app --reload --host 0.0.0.0 --port 8000

format:
	@echo "Formatting code with Black..."
	$(BLACK) $(SRC_DIR) $(TEST_DIR)
	@echo "Done!"

lint:
	@echo "Linting code with Ruff..."
	$(RUFF) check $(SRC_DIR) $(TEST_DIR)

lint-fix:
	@echo "Fixing linting issues..."
	$(RUFF) check --fix $(SRC_DIR) $(TEST_DIR)

typecheck:
	@echo "Type checking with MyPy..."
	$(MYPY) $(SRC_DIR)

# Testing
test:
	@echo "Running tests..."
	$(PYTEST) $(TEST_DIR) -v

test-cov:
	@echo "Running tests with coverage..."
	$(PYTEST) $(TEST_DIR) --cov=$(SRC_DIR) --cov-report=html --cov-report=term-missing -v

test-unit:
	@echo "Running unit tests..."
	$(PYTEST) $(TEST_DIR)/unit -v

test-integration:
	@echo "Running integration tests..."
	$(PYTEST) $(TEST_DIR)/integration -v

test-e2e:
	@echo "Running end-to-end tests..."
	$(PYTEST) $(TEST_DIR)/e2e -v

test-watch:
	@echo "Running tests in watch mode..."
	$(PYTEST) $(TEST_DIR) -v --looponfail

# Pre-commit
pre-commit:
	pre-commit run --all-files

# Docker
docker-up:
	@echo "Starting Docker services..."
	docker-compose up -d

docker-down:
	@echo "Stopping Docker services..."
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-build:
	@echo "Building Docker images..."
	docker-compose build

docker-restart:
	@echo "Restarting Docker services..."
	docker-compose restart

docker-clean:
	@echo "Cleaning Docker resources..."
	docker-compose down -v
	docker system prune -f

# Database
migrate:
	@echo "Running database migrations..."
	alembic upgrade head

migrate-create:
	@echo "Creating new migration..."
	@read -p "Migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

migrate-rollback:
	@echo "Rolling back last migration..."
	alembic downgrade -1

# Cleanup
clean:
	@echo "Cleaning temporary files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	@echo "Done!"

clean-all: clean
	@echo "Cleaning everything including virtual environment..."
	rm -rf venv env .venv
	rm -rf build dist
	@echo "Done!"

# Quality checks (run all checks)
check: format lint typecheck test
	@echo "All checks passed!"

# CI pipeline
ci: lint typecheck test-cov
	@echo "CI checks passed!"

# Documentation
docs-serve:
	@echo "Serving documentation..."
	@echo "Not implemented yet"

# Init development environment
init: dev docker-up migrate
	@echo ""
	@echo "Development environment initialized!"
	@echo "=================================="
	@echo ""
	@echo "Services running:"
	@echo "  - API: http://localhost:8000"
	@echo "  - API Docs: http://localhost:8000/docs"
	@echo "  - Grafana: http://localhost:3003"
	@echo ""
	@echo "Run 'make help' for more commands"

# Development server with hot reload
dev-server:
	uvicorn src.interfaces.api.main:app --reload --host 0.0.0.0 --port 8000 --log-level debug

# =============================================================================
# DevOps - Verification & Lifecycle
# =============================================================================

# Pre-start verification
preflight:
	@./scripts/preflight-check.sh

# Check all Tawiza ports
check-ports:
	@./scripts/check-ports.sh --all

# Check a specific port
check-port:
	@./scripts/check-ports.sh $(PORT)

# Health check of running services
health-check:
	@./scripts/health-check.sh

# Full startup sequence
dev-start: preflight docker-up
	@echo ""
	@echo "==========================================="
	@echo " Tawiza Infrastructure Started"
	@echo "==========================================="
	@echo ""
	@echo "Services starting up (may take 30-60s)..."
	@echo ""
	@echo "Next steps:"
	@echo "  1. source .venv/bin/activate"
	@echo "  2. make run              # Start FastAPI backend"
	@echo "  3. cd frontend && npm run dev  # Start Next.js"
	@echo "  4. make health-check     # Verify everything"
	@echo ""
	@echo "Quick URLs:"
	@echo "  API:        http://localhost:8000/docs"
	@echo "  Frontend:   http://localhost:3000"
	@echo "  Grafana:    http://localhost:3003"

# Stop all services
dev-stop:
	@echo "Stopping Docker services..."
	docker-compose down 2>/dev/null || true
	@echo ""
	@echo "Checking for local processes on Tawiza ports..."
	@for port in 8000 3000; do \
		pid=$$(lsof -t -i :$$port -sTCP:LISTEN 2>/dev/null || true); \
		if [ -n "$$pid" ]; then \
			echo "  Port $$port: PID $$pid still running (kill manually if needed)"; \
		fi; \
	done
	@echo "Done."

# Restart everything
dev-restart: dev-stop dev-start

# Full diagnostic
diagnose:
	@echo "==========================================="
	@echo " Tawiza Full Diagnostic"
	@echo "==========================================="
	@./scripts/preflight-check.sh || true
	@echo ""
	@./scripts/check-ports.sh --conflicts
	@echo ""
	@./scripts/health-check.sh || true

