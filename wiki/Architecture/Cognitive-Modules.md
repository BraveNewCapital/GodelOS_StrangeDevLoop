# Cognitive Modules

GödelOS's cognitive capabilities live in the `godelOS/` package. Modules are categorised as **Active** (wired into the live system) or **Dormant** (implemented but not yet connected — see Issue #83).

## Active Modules

| Module | Path | Function |
|--------|------|----------|
| Knowledge Store | `godelOS/knowledge_store/` | Persistent symbolic knowledge graph |
| Inference Engine | `godelOS/inference/` | Multi-strategy symbolic reasoning |
| Learning System | `godelOS/learning/` | Knowledge assimilation and retention |
| Metacognition Core | `godelOS/metacognition/` | Self-reflection, confidence estimation |
| Unified Agent Core | `godelOS/agent/` | Goal-directed action execution |

## Dormant Modules (Issue #83)

| Module | Path | Capability |
|--------|------|------------|
| Symbol Grounding Associator | `godelOS/symbol_grounding/` | Grounds abstract symbols in perceptual experience |
| Perceptual Categoriser | `godelOS/perception/` | Categorises perceptual inputs into symbolic concepts |
| Simulated Environment | `godelOS/environment/` | Internal world model for reasoning about scenarios |
| ILP Engine | `godelOS/learning/ilp/` | Inductive Logic Programming — learns rules from examples |
| Modal Tableau Prover | `godelOS/inference/modal/` | Modal logic (necessity, possibility) reasoning |
| Enhanced Modal Prover | `godelOS/inference/modal/enhanced/` | Extended modal operators |
| CLP Module | `godelOS/inference/clp/` | Constraint Logic Programming |
| Explanation-Based Learner | `godelOS/learning/ebl/` | Generalises from single examples via causal explanation |
| Meta-Control RL Module | `godelOS/metacognition/rl/` | Reinforcement learning over cognitive strategies |

## Consciousness Engine Layer

Separate from `godelOS/`, the consciousness engine components in `backend/core/`:

| Component | Status |
|-----------|--------|
| `RecursiveConsciousnessEngine` | ✅ Active |
| `PhenomenalExperienceGenerator` | ✅ Active |
| `CognitiveStateInjector` | ✅ Active |
| `MetacognitiveReflectionEngine` | ✅ Active (partial) |
| `ConsciousnessEmergenceDetector` | ⏳ Stub — Issue #82 |
| `InformationIntegrationTheory` | ⏳ Stub — Issue #80 |
| `GlobalWorkspace` | ⏳ Stub — Issue #80 |
| `AutonomousGoalGenerator` | ⏳ Not built — Issue #81 |
| `CreativeSynthesisEngine` | ⏳ Not built — Issue #81 |
