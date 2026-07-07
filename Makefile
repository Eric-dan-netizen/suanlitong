# ============================================================
# 算力通 · Makefile
# ============================================================
.PHONY: help setup dev lint test ppt clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

# ── Environment ────────────────────────────────────────
setup: ## Create virtualenv + install deps
	python3 -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt
	@echo "✅ Setup complete. Run: source .venv/bin/activate"

install: ## Install production deps only
	pip install -r requirements.txt

# ── Development ────────────────────────────────────────
lint: ## Lint Python code
	ruff check scripts/ src/

format: ## Auto-format Python code
	ruff format scripts/ src/

# ── Testing ────────────────────────────────────────────
test: ## Run tests
	pytest -v

test-cov: ## Run tests with coverage
	pytest --cov=src --cov-report=html

# ── Documents ──────────────────────────────────────────
ppt: ## Generate Pitch Deck PPTX from Markdown
	python scripts/generate_pptx.py

ppt-v3: ## Generate V3 Pitch Deck
	python scripts/generate_pptx.py --version v3

# ── Git ────────────────────────────────────────────────
commit: ## Commit with pre-commit checks
	pre-commit run --all-files
	git add -A
	git commit

# ── Cleanup ────────────────────────────────────────────
clean: ## Remove build artifacts
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache dist build *.egg-info

clean-all: clean ## Also remove virtualenv
	rm -rf .venv
