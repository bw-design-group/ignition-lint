# Makefile for ignition-lint development
# Simple, essential commands for productive development

.DEFAULT_GOAL := help

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
BLUE := \033[0;34m
NC := \033[0m # No Color

# Python and Poetry
PYTHON := python3
POETRY := poetry
POETRY_RUN := poetry run

# Directories
SRC_DIR := src
TESTS_DIR := tests
SCRIPTS_DIR := scripts

.PHONY: help
help: ## Show this help message
	@echo "$(BLUE)ignition-lint - Development Commands$(NC)"
	@echo ""
	@echo "$(YELLOW)General Workflow:$(NC)"
	@echo "  1. make setup          - First time setup"
	@echo "  2. make test-unit      - Quick testing while developing"
	@echo "  3. make format         - Format code before committing"
	@echo "  4. make check          - Validate before pushing"
	@echo "  5. make ci             - Full CI test before pushing"
	@echo ""
	@echo "$(YELLOW)Available Commands:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'

.PHONY: install
install: ## Install dependencies with Poetry
	@echo "$(BLUE)Installing dependencies...$(NC)"
	$(POETRY) install

.PHONY: setup
setup: install ## Complete first-time setup (install + pre-commit hooks)
	@echo "$(BLUE)Setting up pre-commit hooks...$(NC)"
	$(POETRY_RUN) pre-commit install
	@echo "$(GREEN)✓ Setup complete!$(NC)"
	@echo ""
	@echo "$(YELLOW)Next steps:$(NC)"
	@echo "  - Run 'make test' to verify installation"
	@echo "  - Run 'make help' to see available commands"

.PHONY: test
test: ## Run all tests (unit + integration)
	@echo "$(BLUE)Running all tests...$(NC)"
	cd $(TESTS_DIR) && $(PYTHON) test_runner.py --run-all

.PHONY: test-unit
test-unit: ## Run unit tests only (fastest)
	@echo "$(BLUE)Running unit tests...$(NC)"
	cd $(TESTS_DIR) && $(PYTHON) test_runner.py --run-unit

.PHONY: lint
lint: ## Run pylint on all code
	@echo "$(BLUE)Running pylint...$(NC)"
	$(POETRY_RUN) pylint $(SRC_DIR)/ $(TESTS_DIR)/ $(SCRIPTS_DIR)/

.PHONY: format
format: ## Format code with yapf
	@echo "$(BLUE)Formatting code...$(NC)"
	$(POETRY_RUN) yapf -ir $(SRC_DIR)/ $(TESTS_DIR)/ $(SCRIPTS_DIR)/
	@echo "$(GREEN)✓ Code formatted$(NC)"

.PHONY: format-check
format-check: ## Check code formatting without changes
	@echo "$(BLUE)Checking code formatting...$(NC)"
	$(POETRY_RUN) yapf -dr $(SRC_DIR)/ $(TESTS_DIR)/ $(SCRIPTS_DIR)/

.PHONY: check
check: lint format-check ## Run all checks (lint + format-check)
	@echo "$(GREEN)✓ All checks passed!$(NC)"

.PHONY: debug
debug: ## Generate debug files for test cases
	@echo "$(BLUE)Generating debug files...$(NC)"
	$(PYTHON) $(SCRIPTS_DIR)/generate_debug_files.py

.PHONY: debug-clean
debug-clean: ## Clean all debug directories
	@echo "$(BLUE)Cleaning debug files...$(NC)"
	$(PYTHON) $(SCRIPTS_DIR)/generate_debug_files.py --clean

.PHONY: clean
clean: ## Clean build artifacts and cache files
	@echo "$(BLUE)Cleaning build artifacts...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "build" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Cleaned$(NC)"

.PHONY: ci
ci: ## Test CI workflow locally with act
	@echo "$(BLUE)Testing CI workflow locally...$(NC)"
	@if ! command -v act &> /dev/null; then \
		echo "$(RED)Error: act is not installed$(NC)"; \
		echo "Install with: curl -q https://raw.githubusercontent.com/nektos/act/master/install.sh | bash"; \
		exit 1; \
	fi
	@if ! docker info > /dev/null 2>&1; then \
		echo "$(RED)Error: Docker is not running$(NC)"; \
		exit 1; \
	fi
	$(SCRIPTS_DIR)/test-actions.sh ci

.PHONY: precommit
precommit: ## Run pre-commit hooks on all files
	@echo "$(BLUE)Running pre-commit hooks...$(NC)"
	$(POETRY_RUN) pre-commit run --all-files

.PHONY: info
info: ## Show project information
	@echo "$(BLUE)Project Information:$(NC)"
	@echo "  Name:        ignition-lint"
	@echo "  Python:      $$($(PYTHON) --version)"
	@echo "  Poetry:      $$($(POETRY) --version 2>/dev/null || echo 'Not installed')"
	@echo "  Location:    $$(pwd)"
	@echo ""
	@echo "$(BLUE)Directory Structure:$(NC)"
	@echo "  Source:      $(SRC_DIR)/"
	@echo "  Tests:       $(TESTS_DIR)/"
	@echo "  Scripts:     $(SCRIPTS_DIR)/"
