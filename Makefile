.PHONY: help install install-dev install-test test test-unit test-bdd test-coverage test-watch clean

help:
	@echo "Library Vault Management Tools - Make Commands"
	@echo ""
	@echo "Installation:"
	@echo "  make install        Install package in development mode"
	@echo "  make install-dev    Install with all development dependencies"
	@echo "  make install-test   Install with test dependencies only"
	@echo ""
	@echo "Testing:"
	@echo "  make test           Run all tests"
	@echo "  make test-unit      Run unit tests only"
	@echo "  make test-bdd       Run BDD tests only"
	@echo "  make test-coverage  Run tests with coverage report (HTML)"
	@echo "  make test-watch     Run tests in watch mode (requires pytest-watch)"
	@echo ""
	@echo "Quality:"
	@echo "  make lint           Run code linting (requires pylint/flake8)"
	@echo "  make format         Format code (requires black)"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean          Remove test artifacts and caches"

# Installation targets (pyproject.toml is in parent directory)
install:
	cd .. && pip install -e .

install-dev:
	cd .. && pip install -e ".[dev]"

install-test:
	cd .. && pip install -e ".[test]"

# Test targets (run from Library directory)
test:
	pytest -v

test-unit:
	pytest -v -m unit

test-bdd:
	pytest -v -m bdd

test-coverage:
	pytest --cov=. --cov-report=html --cov-report=term-missing
	@echo ""
	@echo "Coverage report generated in htmlcov/index.html"

test-watch:
	pytest-watch

test-quick:
	pytest -x --ff -m "not slow"

# Quality targets
lint:
	@echo "Running linting (install pylint/flake8 if needed)..."
	-pylint .
	-flake8 .

format:
	@echo "Formatting code with black..."
	black .

# Cleanup targets
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
	rm -rf *.egg-info
	@echo "Cleaned up test artifacts and caches"
