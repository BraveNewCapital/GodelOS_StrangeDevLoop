# BDD Test Runner Usage Guide

## Quick Start

```bash
# Run all spec-aligned tests in BDD format (auto-starts backend)
./run-bdd-tests.sh

# Run without starting backend (unit tests only)
./run-bdd-tests.sh --no-backend

# Run with verbose pytest output
./run-bdd-tests.sh --verbose

# Run specific test pattern
./run-bdd-tests.sh --pattern "tests/spec_aligned/core_knowledge/*"
```

**Note**: By default, the script automatically starts the backend if it's not running, then stops it after tests complete. Use `--no-backend` to skip this.

## Test Categories

### Unit Tests (No Backend Required)
Most spec-aligned tests are **pure unit tests** that don't require a running backend:
- Core Knowledge (`core_knowledge/`)
- Inference Engine (`inference_engine/`)
- Learning System (`learning_system/`)
- Metacognition (`metacognition/`)
- NLU/NLG (`nlu_nlg/`)
- Ontology & Creativity (`ontology_creativity/`)
- Scalability & Efficiency (`scalability_efficiency/`)
- Symbol Grounding (`symbol_grounding/`)
- System E2E (`system_e2e/`)
- Common Sense Context (`common_sense_context/`)

**48 total scenarios** - 47 run without backend, 1 requires backend

### Integration Tests (Require Backend)
Tests marked with `@pytest.mark.requires_backend`:
- `test_user_story_knowledge_reasoning_nlg` - Full NL→Logic→Proof→NLG flow
- `test_user_story_transparency_metrics` - Live transparency metrics

**The BDD test runner automatically starts the backend** if it's not already running, so these tests will execute by default.

**Manual backend control:**
```bash
# Skip backend auto-start (unit tests only)
./run-bdd-tests.sh --no-backend

# Or manually start backend before running tests
./start-godelos.sh --dev
./run-bdd-tests.sh --no-backend  # Won't start another instance
```

## Understanding Test Output

### BDD Format with Given/When/Then
```
Scenario: Nl To Proof Round Trip
  ○ Given parsed natural language input
  ○ When semantic interpretation creates AST
  ○ And AST is submitted to KSI
  ○ And proof engine validates the expression
  ○ Then NLG generates readable output
  ○ And transparency events are broadcast
  
  ✓ PASSED (0.17s)
```

### Status Symbols
- `○` - Step listed in docstring
- `◐` - Test running
- `✓` - Test passed
- `✗` - Test failed
- `⊘` - Test skipped (intentional, e.g., backend not running)

## Filtering Tests

### Run Only Backend-Required Tests
```bash
pytest tests/spec_aligned/test_user_stories_live.py -m requires_backend -v
```

### Exclude Backend-Required Tests
```bash
pytest tests/spec_aligned/ -m "spec_aligned and not requires_backend" -v
```

### Run BDD Tests Without Backend Tests
```bash
./run-bdd-tests.sh --pattern "tests/spec_aligned/!(test_user_stories_live)*"
```

## Current Test Status (October 2025)

✅ **All 48 scenarios passing** (47 without backend, 1 skips if backend unavailable)

### Fixed Issues
- ✅ Removed fragile `caplog` assertions that broke in silent mode
- ✅ Added Given/When/Then to representative tests
- ✅ Added `@pytest.mark.requires_backend` for live integration tests
- ✅ All tests now assert on **behavior**, not log output

### Test Breakdown by Feature
- Common Sense Context: 4 tests
- Core Knowledge: 5 tests
- Inference Engine: 7 tests
- Learning System: 4 tests
- Metacognition: 4 tests
- NLU/NLG: 4 tests
- Ontology & Creativity: 6 tests
- Scalability & Efficiency: 4 tests
- Symbol Grounding: 4 tests
- System E2E: 4 tests
- User Stories (Live): 2 tests (1 requires backend)

## Writing BDD-Style Tests

### Docstring Format
```python
def test_example():
    """Brief description of what the test validates.
    
    Given initial system state or preconditions
    When specific action is performed
    Then expected outcome occurs
    And additional verification
    """
    # Test implementation
```

### Best Practices
1. **Assert on behavior, not logs** - Tests should verify actual system behavior
2. **Use deterministic seeds** - For tests involving randomness
3. **Mark backend dependencies** - Use `@pytest.mark.requires_backend`
4. **Include Given/When/Then** - Makes BDD output more readable
5. **Test should stand alone** - No hidden dependencies on other tests

## Troubleshooting

### "Backend not reachable" Skip
**Cause**: Test requires running backend but none found
**Fix**: Start backend with `./start-godelos.sh --dev`

### JSON/Debug Output in BDD Mode
**Cause**: Test logging not suppressed
**Fix**: BDD runner uses `--silent` flag and grep filters

### Import Errors
**Cause**: Missing module imports
**Fix**: Verify all required imports in test file header

## Related Files
- `godelOS/test_runner/bdd_formatter.py` - BDD output formatting
- `godelOS/test_runner/bdd_runner.py` - Test execution engine
- `run-bdd-tests.sh` - Convenience wrapper script
- `pytest.ini` - Test markers and configuration
- `BDD_TEST_STATUS.md` - Detailed test status documentation
