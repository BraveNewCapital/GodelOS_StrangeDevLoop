# Running Tests

## Current Test Suite Status

| Metric | Value |
|--------|-------|
| Total collectible | 1299 |
| Collection errors | 0 |
| Passing (baseline) | 925 |
| Failing (pre-existing) | 167 → 0 in progress (PR #74) |
| Skipped | 139 |

## Running Tests

```bash
# Full suite
pytest tests/ -v

# Quick — skip slow tests
pytest tests/ -v -m "not slow"

# Specific category
pytest tests/ -m "unit"
pytest tests/ -m "integration"
pytest tests/ -m "e2e"

# Single file
pytest tests/test_knowledge_store.py -v

# With coverage
pytest tests/ --cov=backend --cov=godelOS --cov-report=term-missing

# Stop on first failure
pytest tests/ -x
```

## Test Marks

| Mark | Meaning |
|------|---------|
| `@pytest.mark.unit` | Fast, isolated, no I/O |
| `@pytest.mark.integration` | Requires module wiring |
| `@pytest.mark.e2e` | Requires running backend on localhost:8000 |
| `@pytest.mark.slow` | Takes > 5 seconds |
| `@pytest.mark.requires_backend` | Backend must be running |

## Frontend Tests

```bash
cd svelte-frontend
npm test          # Playwright E2E
npm run test:unit # Unit tests
```

## Hard Rules

- **Never delete tests** to make the suite pass
- **Never weaken assertions** (don't change `assertEqual` to `assertIn` to avoid failures)
- **Never mock away real behaviour** to force a pass
- If source is broken, fix the source
