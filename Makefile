# Simple developer conveniences for GödelOS

SHELL := /bin/zsh
PY := source godelos_venv/bin/activate && python
PYTEST := source godelos_venv/bin/activate && pytest

.PHONY: help start front-only test-spec test-results test-viewer unified-runner

help:
	@echo "Targets:"
	@echo "  start           - start backend+frontend (dev)"
	@echo "  front-only      - start Svelte frontend only"
	@echo "  test-spec       - run spec-aligned tests"
	@echo "  test-results    - generate JSON test results"
	@echo "  test-viewer     - serve test results viewer"
	@echo "  unified-runner  - run unified test runner (SUITE=<name>)"

start:
	./start-godelos.sh --dev

front-only:
	cd svelte-frontend && npm run dev


# Spec-aligned tests (marked)
test-spec:
	$(PYTEST) -m spec_aligned -v

# Create test-output/ JSON using our script
test-results:
	$(PY) scripts/generate_test_results.py

# Serve a lightweight HTML viewer for test-output/
test-viewer:
	$(PY) scripts/serve_test_viewer.py

# Run unified test runner with a specific suite
# Usage: make unified-runner SUITE=spec-aligned
unified-runner:
	$(PY) scripts/unified_test_runner.py --suite $(SUITE)
