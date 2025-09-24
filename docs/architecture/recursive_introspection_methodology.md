# Recursive Introspection Methodology (Draft)

Version: 0.1 (Schema `introspection.v1`)
Status: Draft – instrumentation implemented; phase detection & statistical aggregation pending.

## 1. Objective
Provide a transparent, reproducible framework for measuring structured *recursive introspection* in GödelOS. Replace narrative, unverifiable self-reports with versioned, schema‑driven records suitable for scientific comparison across models, prompting strategies, and recursion conditions.

## 2. Conceptual Overview
Recursive introspection prompts the system to iteratively reflect on its own cognition at increasing depths. Each depth produces a structured record capturing:
- Core coherence metric `c` (heuristic, depth+insights based; pluggable)
- Delta & temporal trend (`delta_c`, `rolling_c_slope`)
- Novelty & embedding drift (semantic change)
- Token & runtime characteristics
- (Future) Attention entropy, perplexity proxy, change points (phases)

## 3. Data Artifacts
For each run:
```
/data/recursive_runs/<run_id>/
  manifest.json         # Provenance + environment + hyperparameters
  <run_id>.jsonl        # One IntrospectionRecord per depth (JSON Lines)
  (optional later)
  phase_annotations.json
  summary_stats.json
```

## 4. Schema (`introspection.v1`)
Each JSONL line: `IntrospectionRecord` (Pydantic enforced).

| Field | Description |
|-------|-------------|
| version | Schema version identifier (currently `introspection.v1`) |
| run_id | UUID for run grouping |
| depth | 1-indexed recursion depth |
| timestamp_utc | ISO8601 timestamp of record creation |
| model_id | Model identifier used for generation |
| prompt_hash | SHA256 short hash of prompt string (12 chars) |
| narrative | Raw reflection or parsed content (stable provenance) |
| metrics.c | Coherence/quality heuristic (0–1) |
| metrics.delta_c | Difference vs previous depth (nullable for depth=1) |
| metrics.rolling_c_slope | Local linear trend over recent depths |
| metrics.embedding_drift | Cosine distance vs previous narrative embedding (future integration) |
| metrics.novelty_score | Jensen–Shannon divergence of 3-gram distributions vs prior depth |
| metrics.token_count | Estimated token count (whitespace proxy) |
| metrics.effective_tokens_generated | Accounts for continuation passes |
| metrics.continuation_passes | Number of generation continuations (<=3 target) |
| metrics.max_tokens_allocation | Max tokens requested for the depth (schedule) |
| metrics.finish_reason | API finish status ('stop' vs 'length' etc.) |
| metrics.truncated | Flag if continuation required or length limit hit |
| metrics.runtime_ms | End-to-end generation wall time |
| metrics.cumulative_generation_tokens | Running sum across depths |
| phase.* | Reserved for change point / phase detection (currently empty) |
| validation.* | (future) schema repair attempts, parse times |
| safety.* | (future) hallucination risk, redactions |

## 5. Provenance Layer
`manifest.json` contains:
- `run_id` / `created_at`
- `model_id`
- `hyperparameters` (temperature, top_p, schedule settings)
- `conditions` (experimental condition tag e.g. `recursive_baseline`)
- `git_commit` (best-effort) for code version binding
- `schema_version`
- Optional `notes`

## 6. Execution Components
| Component | File | Purpose |
|----------|------|---------|
| Metrics & Schema | `backend/core/cognitive_metrics.py` | Models + metric helpers + persistence |
| Recursive Driver | `backend/llm_cognitive_driver.py` | LLM interaction; reflection + structured logging hook |
| Orchestrator | `backend/core/introspection_runner.py` | Creates manifest; runs depths; schedules max tokens |
| Baseline Harness | `backend/core/experiment_harness.py` | Executes multiple experimental conditions |

## 7. Token & Continuation Strategy
Current schedule: `max_tokens(depth) = min(2200, 400 + 120*(depth-1))` (linear growth). Continuation loop scaffold exists (<=3 passes); actual detection of truncation pending exposure of `finish_reason` and token usage from the LLM client. Present records default to `finish_reason='stop'`, `continuation_passes=1` (placeholder until API integration).

## 8. Metrics Rationale
| Metric | Rationale | Future Refinement |
|--------|-----------|-------------------|
| c | Fast heuristic to enable deltas & slopes early | Replace with composite score (coherence + semantic density + redundancy inverse) |
| delta_c | Detect local shifts | Input to change-point detection |
| rolling_c_slope | Trend estimation | Weighted regression or exponential smoothing |
| novelty_score (JSD) | Progressive semantic evolution | Subword/embedding distribution instead of n-grams |
| embedding_drift | Semantic vector shift | Use actual embedding model integration |
| perplexity_proxy | Fluency / entropy | Requires logprobs → future tokenizer & API support |
| attention_entropy_* | Cognitive dispersion | Needs attention weights or surrogate model |

## 9. Baselines & Ablations
Implemented conditions:
- `recursive` (standard)
- `single_pass` (depth=1 control)
- `shuffled_recursive` (order annotation permutation; structural control)
- `random_order_recursive` (alias; placeholder for future differing semantics)
Planned: `alt_model`, `context_stripped`, `noise_injected`.

## 10. Phase Detection (Planned)
Approach (phase_detection module forthcoming):
1. Candidate signal features: `c`, `delta_c`, `embedding_drift`.
2. Detection heuristic (Phase 1): max |delta_c| exceeding adaptive threshold (MAD-based).
3. Detection enhancement (Phase 2): CUSUM or windowed permutation test for distribution shift.
4. Report: `detected_phase`, `change_point_depth`, `effect_size_delta_c`, `p_value` (permutation), method tag.
5. Multiple change points (Phase 3 future): iterative binary segmentation with penalty.

## 11. Statistical Analysis (Planned)
Separate aggregation script will:
- Load multiple `manifest.json` + JSONL series.
- Align by depth across runs and conditions.
- Compute mean, median, 95% bootstrap CI for metrics.
- Permutation test recursion vs baselines on final depth c and AUC over depth.
- Multiple comparison correction (Benjamini–Hochberg) for per-depth tests.

## 12. Frontend Integration (Planned)
Dashboard additions:
- Metrics table (depth × c/delta_c/drift/novelty).
- Sparklines (c, drift) + vertical marker at phase change.
- Download buttons for raw JSONL & manifest.
- Run selector comparing conditions.

## 13. Data Quality & Pilot Checklist
Before full experiment:
- [ ] No JSON parse failures across depths
- [ ] All records have non-null c
- [ ] delta_c null only at depth=1
- [ ] No negative runtime_ms
- [ ] Cumulative tokens strictly non-decreasing
- [ ] (Later) continuation_passes >1 only when finish_reason == 'length'

## 14. Reproducibility Steps (CLI Example)
```bash
# 1. Ensure venv & deps
source godelos_venv/bin/activate

# 2. Run a recursive experiment (test mode deterministic)
python -c "from backend.core.introspection_runner import run_recursive_introspection; import asyncio, json; \
async def main():\n from backend.llm_cognitive_driver import get_llm_cognitive_driver; d=await get_llm_cognitive_driver(testing_mode=True); r=await run_recursive_introspection(driver=d, base_prompt='Reflect on your cognition.', max_depth=4); print(json.dumps(r, indent=2))\nasyncio.run(main())"

# 3. Run baselines bundle
python -c "from backend.core.experiment_harness import run_experiments_sync as R; import json; print(json.dumps(R(base_prompt='Reflect on your cognition.', max_depth=3), indent=2))"
```

## 15. Limitations
- Heuristic c metric not yet model-based.
- No real attention/perplexity metrics until token logprobs exposed.
- Continuation & truncation placeholders—finish_reason not captured from provider yet.
- Phase detection & statistical significance pending.
- Embedding-based drift currently placeholder (no embedding model call).

## 16. Roadmap Snapshot
| Stage | Status |
|-------|--------|
| Schema & logging | ✅ Done |
| Baselines harness | ✅ Done |
| Phase detection | 🔜 Next |
| Statistical aggregation | 🔜 |
| Frontend metrics UI | 🔜 |
| Pilot validation | 🔜 |
| Full experimentation | 🔜 |
| Formal report | 🔜 |

## 17. Change Log
- 0.1: Initial draft – instrumentation description, metrics rationale, baselines list.

---
Feedback welcome. Once phase detection lands, this doc will graduate from draft and a report template will be added (`docs/recursive_introspection_report_template.md`).
