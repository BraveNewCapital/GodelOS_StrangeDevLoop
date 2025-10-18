# BDD Tests - Quick Reference

## TL;DR
```bash
./run-bdd-tests.sh              # ✅ Best option: Auto-starts backend, runs all 48 tests
./run-bdd-tests.sh --no-backend # ⚡ Fast: Unit tests only (47 tests, skips 1)
```

## What It Does

### Default Behavior (Recommended)
1. ✅ Checks if backend is running on `http://localhost:8000`
2. 🚀 If not, starts it automatically
3. 🧪 Runs all 48 tests (47 unit + 1 integration)
4. 🛑 Stops backend when done

**Result**: All tests pass, including live integration tests

### With `--no-backend`
1. 🧪 Runs only unit tests (47 tests)
2. ⊘ Skips 1 integration test (gracefully)
3. ⚡ Faster (no backend startup time)

**Result**: 47 pass, 1 skip

## Flags

| Flag | Purpose |
|------|---------|
| `--no-backend` | Skip backend auto-start (unit tests only) |
| `--verbose` | Show detailed pytest output |
| `--pattern "path/*"` | Run specific test pattern |

## Examples

```bash
# Full test suite with backend (default)
./run-bdd-tests.sh

# Quick unit tests only
./run-bdd-tests.sh --no-backend

# Test specific feature
./run-bdd-tests.sh --pattern "tests/spec_aligned/system_e2e/*"

# Unit tests for specific feature
./run-bdd-tests.sh --no-backend --pattern "tests/spec_aligned/core_knowledge/*"

# Verbose output for debugging
./run-bdd-tests.sh --verbose
```

## Output Format

### Clean BDD Style
```
Scenario: Nl To Proof Round Trip
  ○ Given parsed natural language input
  ○ When semantic interpretation creates AST
  ○ Then NLG generates readable output
  
  ✓ PASSED (0.17s)
```

### Status Symbols
- `○` = BDD step from docstring
- `◐` = Test running  
- `✓` = Passed
- `✗` = Failed
- `⊘` = Skipped

## Test Breakdown

- **47 Unit Tests** - Pure logic, no dependencies
- **1 Integration Test** - Requires backend (`test_user_story_knowledge_reasoning_nlg`)

## Troubleshooting

### Backend Won't Start
```bash
# Check logs
tail -f /tmp/godelos-backend.log

# Manually start backend
./start-godelos.sh --dev

# Then run tests without auto-start
./run-bdd-tests.sh --no-backend
```

### Port Already in Use
```bash
# Kill existing backend
pkill -f "uvicorn.*unified_server"

# Run tests (will start fresh backend)
./run-bdd-tests.sh
```

### Tests Fail
```bash
# Run with verbose output to see details
./run-bdd-tests.sh --verbose

# Check specific test file
pytest tests/spec_aligned/path/to/test.py -v
```

## Performance

| Mode | Tests | Duration | Backend |
|------|-------|----------|---------|
| Default | 48 | ~30-70s | Auto-started |
| `--no-backend` | 47 | ~18-40s | Not started |

*Duration varies by system performance*

## Files

- `run-bdd-tests.sh` - Main wrapper script
- `godelOS/test_runner/bdd_runner.py` - Test execution engine
- `godelOS/test_runner/bdd_formatter.py` - BDD output formatting
- `BDD_TEST_USAGE.md` - Full documentation
- `BDD_IMPLEMENTATION_SUMMARY.md` - Implementation details

---

**Remember**: By default, the script handles everything automatically. Just run `./run-bdd-tests.sh` and you're good! 🚀
