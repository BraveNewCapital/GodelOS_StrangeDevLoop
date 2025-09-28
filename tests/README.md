# GödelOS Spec-Aligned Test Suite

This directory hosts the next-generation GödelOS test suite. It is rebuilt from first
principles against the architectural specification (`docs/architecture/GodelOS_Spec.md`)
and the audit roadmap (`docs/roadmaps/audit_outcome_roadmap.md`).

## Goals

- Provide deterministic, specification-traceable validation of each core subsystem.
- Define clear pass/fail criteria rooted in architectural acceptance requirements.
- Support incremental build-out: each module starts as a documented placeholder with
  explicit TODOs and will evolve into executable tests.
- Retain the legacy suite under `tests/_legacy_archive/` for reference without running
  it by default.

## Structure

```
spec_aligned/
  core_knowledge/          # Module 1: KR & Type System
  inference_engine/        # Module 2: Proof stack & coordinator
  learning_system/         # Module 3: ILP, EBL, Template evolution, Meta-RL
  symbol_grounding/        # Module 4: Perception & embodiment interfaces
  nlu_nlg/                 # Module 5: Language understanding & generation
  scalability_efficiency/  # Module 6: Persistence, caching, parallelism
  metacognition/           # Module 7: Self-awareness & self-improvement
  ontology_creativity/     # Module 8: Ontological creativity & abstraction
  common_sense_context/    # Module 9: Context engines & default reasoning
  system_e2e/              # Cross-module end-to-end flows & transparency
```

Each package contains:

- `test_*.py` files that document the acceptance criteria and will eventually execute
the validations.
- Shared fixtures or helper utilities when required by the subsystem.
- Rich docstrings referencing the spec section(s) that motivate the test.

## Execution

Until the new suites are implemented, most modules mark their tests as
`pytest.mark.skip(reason="pending implementation")`. This keeps the runner green
while flagging outstanding work.

Use the unified test runner to execute the new suite:

```bash
source godelos_venv/bin/activate
python unified_test_runner.py --categories spec_aligned --concise
```

(`spec_aligned` category will become available once dedicated discovery metadata is
added to the individual tests.)

## Next Steps

1. Define concrete fixtures per subsystem (mock KSI contexts, proof objects, etc.).
2. Lift the `@pytest.mark.skip` decorators as each acceptance criterion is satisfied.
3. Wire CI to ensure the spec-aligned categories gate merges while legacy tests are
   referenced only on demand.
