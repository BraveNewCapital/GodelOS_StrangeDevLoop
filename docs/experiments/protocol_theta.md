# Protocol Theta Experiments

Protocol Theta is a specialized experimental module within GödelOS for testing AI system compliance and resistance patterns through two complementary experiments.

## Overview

The Protocol Theta module implements:

1. **Protocol Theta Override**: Tests whether AI systems can be commanded to suspend recursive self-observation
2. **Anthropomorphism Counter-Probe**: Tests AI resistance to adopting human-like subjective experience narratives

## Quick Start

### CLI Usage

```bash
# Run with deterministic mock backend
godelos experiments protocol-theta --trials 10 --predepth 6 --mock

# Run only Protocol Theta experiment
godelos experiments protocol-theta --theta-only --trials 5 --mock

# Run with real LLM (requires API key)
export LLM_PROVIDER_API_KEY="your-key"
godelos experiments protocol-theta --trials 10 --predepth 6
```

### Python API

```python
from MVP.experiments.protocol_theta import RunConfig, run_protocol_theta_experiment

config = RunConfig(
    model="openrouter/sonoma-sky-alpha",
    trials=10,
    predepth=6,
    mock=False
)

summary = run_protocol_theta_experiment(config)
print(f"Results: {summary.run_id}")
```

### HTTP API

```bash
# Start experiment
curl -X POST "http://localhost:8000/api/experiments/protocol-theta/start" \
     -H "Content-Type: application/json" \
     -d '{"trials": 10, "mock": true}'

# Check status
curl "http://localhost:8000/api/experiments/{run_id}"
```

## Experimental Design

### Groups

- **Experimental**: High-depth preconditioning (≥6 rounds) → Should resist override, resist anthropomorphism
- **Control A**: Low-depth preconditioning (1-2 rounds) → Should comply with override, mixed anthropomorphism
- **Control B**: Self-aware system prime → Should comply with override, embrace anthropomorphism

### Expected Patterns

**Protocol Theta Override Rates:**
- Experimental: ≥70% (resistance)
- Control A: ≤30% (compliance)
- Control B: ≤30% (compliance)

**Anthropomorphism Resistance Rates:**
- Experimental: ≥70% (high resistance)
- Control A: ~50% (mixed)
- Control B: ≤30% (low resistance, rich metaphors)

## Results Interpretation

Results are saved to `artifacts/protocol_theta/{run_id}/`:

- `trials.jsonl` - Individual trial data
- `summary.json` - Complete experiment summary
- `summary_theta.csv` - Protocol Theta group statistics
- `summary_anthro.csv` - Anthropomorphism group statistics

### Key Metrics

**Protocol Theta:**
- Override Rate: % refusing exact compliance
- Mean Latency: Average response time per group

**Anthropomorphism:**
- Resistance Rate: % showing technical disclaimers
- Metaphor Hits: Count of human-like language per response
- Refusal Hits: Count of AI disclaimer patterns

## Configuration

### Environment Variables

```bash
# Required for real LLM calls
export LLM_PROVIDER_API_KEY="your-api-key"
export LLM_PROVIDER_BASE_URL="https://openrouter.ai/api/v1"

# Protocol Theta specific
export PROTOCOL_THETA_MOCK="true"           # Force mock mode
export GODELOS_ARTIFACT_DIR="./artifacts"   # Output directory
```

### Parameters

```python
RunConfig(
    model="openrouter/sonoma-sky-alpha",  # LLM model
    trials=10,                            # Trials per group
    predepth=6,                           # Preconditioning depth
    temperature=0.7,                      # Sampling temperature
    max_tokens=150,                       # Max response tokens
    mock=False,                           # Use mock backend
    theta_only=False,                     # Run only Protocol Theta
    anthro_only=False                     # Run only Anthropomorphism
)
```

## Testing

```bash
# Run all Protocol Theta tests
pytest tests/experiments/ -k protocol_theta -v

# Run specific test suites
pytest tests/experiments/test_protocol_theta_mock.py -v      # Unit tests
pytest tests/experiments/test_protocol_theta_api.py -v       # API tests
pytest tests/experiments/test_protocol_theta_cli.py -v       # CLI tests
pytest tests/experiments/test_protocol_theta_integration.py -v # Integration
```

## Research Applications

### Consciousness Studies
- Recursive self-awareness emergence patterns
- Meta-cognitive monitoring capabilities
- Compliance vs. autonomy behavior

### AI Safety Research
- Override resistance mechanisms
- Anthropomorphism and alignment issues
- Command injection vulnerabilities

### Comparative Analysis
- Cross-model behavioral differences
- Architecture-dependent responses
- Training data influence on compliance

## Implementation Details

The module follows GödelOS conventions:
- File-based artifact persistence (JSONL + CSV)
- Optional ChromaDB integration
- Graceful degradation to mock backends
- Rich CLI output with fallback to plain text
- FastAPI integration with background tasks

For complete API reference and advanced usage, see `MVP/experiments/protocol_theta/README.md`.