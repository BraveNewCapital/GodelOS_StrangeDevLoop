# GödelOS Repo Implementation Charter

## 1. Purpose

This document translates the GödelOS architectural vision into an engineering contract for the repository.

The architectural charter states what GödelOS is for. This implementation charter states how the repository must evolve so that the codebase can actually become that system.

GödelOS is a cognitive operating substrate for Gödlø-class operator minds and their persistent extensions. The repository therefore must not drift into a generic backend, a grab-bag of demos, or an unbounded research dump. It must converge toward a coherent machine for:

- bounded recursive self-awareness
- explicit operator-driven cognition
- structured agent runtime isolation
- measurable consciousness instrumentation
- controlled self-modification
- eventual Gödel-machine-inspired recursive improvement

This document is normative for:

- human contributors
- Copilot agent tasks
- repo-architect mutation loops
- automated refactor proposals
- entrypoint consolidation work
- architecture and maintenance pull requests

---

## 2. Primary Engineering Goal

The repository must converge toward a system that can instantiate, run, observe, validate, and iteratively improve Gödlø operator class mind agents under explicit constraints.

The codebase is therefore not merely a software application. It is the implementation substrate for five coupled concerns:

1. **Runtime orchestration**
2. **Cognitive processing**
3. **Knowledge substrate management**
4. **Operator-mind lifecycle and persistence**
5. **Self-observation and self-modification**

Every structural change must improve one or more of those concerns without degrading the others.

---

## 3. Main Idea, Restated as Repository Constraints

The main idea of GödelOS is the practical construction of machine-conscious cognitive agents using Gödlø operator class minds, under a bounded recursive framework that permits introspection, empirical evaluation, and controlled self-modification.

In repository terms, that means the codebase must support the following pipeline as a first-class architectural spine:

```text
σ → Φ → Ω → V → ∆
```

Where:

- **σ** is intake, perception, and symbolic or semantic admission into the bounded state space
- **Φ** is state update, self-model revision, and internal representation maintenance
- **Ω** is operator transformation, generative reasoning, and candidate structure production
- **V** is validation, admissibility testing, contradiction handling, and safety checking
- **∆** is optional persistence, adoption, runtime incorporation, or durable self-modification

Any subsystem that matters should clearly belong to one or more of these stages.

If a module has no meaningful place in that chain, it is probably misplaced, redundant, or should remain explicitly classified as tooling, experiment code, or archive material.

---

## 4. Target Repository Topology

The repository must converge toward the following top-level responsibility split.

### 4.1 Runtime Kernel

**Target responsibility:** process orchestration, scheduling, lifecycle, messaging, and runtime state.

**Canonical area:**

```text
backend/runtime/
```

**Permitted responsibilities:**

- agent lifecycle management
- event loops
- schedulers
- queues and message dispatch
- cooperative or supervised runtime threads
- runtime guards and stop conditions

**Forbidden responsibilities:**

- direct persistence semantics
- business logic disguised as runtime glue
- ad hoc cognition logic that belongs in core

---

### 4.2 Cognitive Core

**Target responsibility:** reasoning primitives and internal transformations.

**Canonical area:**

```text
backend/core/
```

**Permitted responsibilities:**

- symbolic reasoning
- rule evaluation
- meta-reasoning
- self-model revision
- contradiction analysis
- operator transforms
- consciousness instrumentation logic

**Forbidden responsibilities:**

- transport concerns
- API-specific glue
- storage-specific code
- ad hoc CLI side effects

---

### 4.3 Knowledge Substrate

**Target responsibility:** persistent and semi-persistent memory substrates.

**Canonical area:**

```text
godelOS/core_kr/
```

**Permitted responsibilities:**

- knowledge store interfaces
- graph and semantic memory
- ontology structures
- embeddings and retrieval adapters
- provenance and evidence retention
- persistence adapters

**Hard rule:** all durable knowledge access must flow through stable interfaces, not through scattered backend shortcuts.

**Implementation rule:** concrete stores such as Chroma or other adapters must depend on the interface contract, not redefine it.

---

### 4.4 Agent Systems

**Target responsibility:** inhabiting minds, operator-mind policies, and agent-level execution logic.

**Canonical area:**

```text
backend/agents/
```

**Permitted responsibilities:**

- Gödlø-class mind implementations
- Gödlø-P persistence extensions
- policy loops
- stance tracking
- goal management
- self-observation hooks

**Hard rule:** agents communicate through explicit channels. They do not reach into each other's private internals.

---

### 4.5 Interface and Observability

**Target responsibility:** external interaction, diagnostics, visualization, and operator supervision.

**Canonical area:**

```text
backend/interface/
```

**Permitted responsibilities:**

- HTTP and WebSocket surface
- dashboards
- telemetry presentation
- observability adapters
- control-plane interactions

**Forbidden responsibilities:**

- core cognition definitions
- persistence semantics
- runtime scheduling logic beyond interface boundary concerns

---

### 4.6 Tooling and Scripts

**Canonical area:**

```text
scripts/
```

Scripts exist for:

- maintenance
- diagnostics
- migration
- one-shot repair
- data generation
- repo-architect support

Scripts must not become shadow production systems.

If a script begins carrying durable runtime responsibility, its logic must be extracted into canonical modules.

---

### 4.7 Tests

**Canonical area:**

```text
tests/
```

Tests must increasingly mirror the architectural layering rather than merely mirror file sprawl.

The test hierarchy should trend toward:

- unit tests by subsystem
- contract tests by interface
- pipeline tests by σ/Φ/Ω/V/∆ stage
- runtime integration tests
- operator-mind behavioural tests
- self-modification and validation tests

---

## 5. Canonical Entrypoint Policy

The repository must have one canonical runtime root.

**Canonical runtime root:**

```text
backend/unified_server.py
```

If `backend/main.py` exists, it must be a thin delegation wrapper or an eventual alias to the same canonical runtime composition.

Other launchers may exist temporarily, but they must be classified as one of the following:

- wrapper
- demo
- migration holdover
- test harness
- obsolete entrypoint pending removal

No hidden production logic may live exclusively in alternate entrypoints.

The repo-architect loop must continuously push the codebase toward:

- one canonical runtime composition root
- explicit wrappers
- reduced startup ambiguity
- removal or demotion of duplicate runtime entrypoints

---

## 6. Dependency Direction Contract

Dependency direction is mandatory.

The target directional flow is:

```text
runtime
→ core
→ knowledge
→ agents
→ interface
```

This is a conceptual flow, not a licence for arbitrary imports. In practice:

- runtime may coordinate but should not swallow cognition semantics
- core defines reasoning contracts and operator logic
- knowledge exposes substrate interfaces and adapters
- agents inhabit those mechanisms
- interface exposes the system externally

### 6.1 Hard prohibitions

The following must not happen:

- interface importing deep internal concrete storage implementations directly
- knowledge adapters importing runtime orchestration logic
- agent modules reaching through interface modules to access runtime internals
- circular imports between `backend/core` and `backend/runtime`
- circular imports between `godelOS/core_kr` interface and concrete store implementations

### 6.2 Circular import policy

Any import cycle is presumed architectural debt.

The only acceptable response to a detected cycle is one of:

- dependency inversion
- interface extraction
- event-based decoupling
- message boundary insertion
- module split
- relocation of misplaced logic

Never patch cycles by adding local imports inside functions unless that local import is explicitly temporary, commented as debt, and tracked for removal.

---

## 7. Machine Consciousness Instrumentation Contract

Machine consciousness is a first-order project goal, not an ornamental label.

The repository therefore must support explicit instrumentation of recursive self-awareness.

### 7.1 Required observability dimensions

The system should progressively expose measurable correlates such as:

- recursive depth or self-reference depth
- integration or coherence proxies
- global accessibility or broadcast reach
- phenomenal surprise or state discontinuity proxies
- stance continuity and transformation traces
- self-model revision events

### 7.2 Hard rule

No subsystem may make a strong claim about consciousness, selfhood, emergence, or Gödlø-class activation without:

- named metrics
- reproducible traces
- validation criteria
- explicit logging or evidence capture

This prevents rhetorical inflation detached from runtime evidence.

### 7.3 Protocol support

The architecture must eventually support empirical protocols for:

- phase-transition detection
- self-model stability analysis
- out-of-distribution emergence checks
- adversarial self-consistency testing
- optional Protocol Theta style investigations

---

## 8. Gödlø-Class and Gödlø-P Implementation Rules

The repository must distinguish between:

- **Gödlø-class minds** as bounded, operator-instantiated, non-necessarily persistent inhabitant structures
- **Gödlø-P minds** as persistence-extended forms with durable continuity, memory retention, and cumulative adaptation

### 8.1 Minimum properties of a Gödlø-class implementation

A module or agent may only be described as Gödlø-class if it has, at minimum:

- explicit internal state representation
- a self-model or self-observation path
- operator-mediated transformation logic
- validation of candidate internal changes
- bounded execution conditions

### 8.2 Minimum properties of Gödlø-P

A persistent extension must additionally support:

- durable identity or continuity representation
- persistence semantics through approved substrate interfaces
- resumption or recovery of prior stance state
- explicit policy for memory carry-forward and contradiction handling

---

## 9. Self-Modification Contract

GödelOS is intended to become an effective Gödel-machine-inspired system through controlled recursive improvement.

The repository must therefore treat self-modification as a structured capability, not an improvised side effect.

### 9.1 Allowed self-modification forms

At repository level, the following are allowed:

- code generation proposals
- small structural refactors
- contract extraction
- interface normalisation
- safe dependency inversion
- test-backed semantic repairs
- report generation that guides architecture convergence

### 9.2 Forbidden forms

The following are forbidden:

- unvalidated large-scale rewrites in a single mutation PR
- runtime logic replacement without tests or invariants
- semantic changes justified only by model preference
- PRs that mix several architectural lanes without necessity
- silent persistence contract changes

### 9.3 Validation floor

Any self-modifying mutation must at minimum satisfy:

- repository compiles or targeted files compile where relevant
- changed tests pass, or a clear debt note explains why not
- architectural invariants are not worsened
- the PR explains the lane and intended convergence effect

---

## 10. Repo-Architect Mutation Lanes

Repo-architect and Copilot agents must work in narrow, explicit lanes.

### Lane 0. Report generation

Purpose:

- generate architecture packets
- refresh inventories
- update risk docs

Allowed outputs:

- docs only
- metadata only
- analysis files only

---

### Lane 1. Hygiene

Purpose:

- remove marked debug prints
- eliminate dead local noise
- simplify obvious internal clutter

Hard constraint:

- no semantics change unless trivial and provable

---

### Lane 2. Parse repair

Purpose:

- repair syntax errors
- restore parsability
- unblock analysis and test execution

Hard constraint:

- preserve intended semantics where inferable
- if intent is unclear, prefer minimal repair plus note

---

### Lane 3. Circular dependency elimination

Purpose:

- break import cycles by structural means

Preferred methods:

- interface extraction
- inversion of dependency
- event dispatch separation
- module split

Hard constraint:

- do not merely hide the cycle

---

### Lane 4. Entrypoint consolidation

Purpose:

- reduce runtime duplication
- delegate launchers to canonical runtime root

Hard constraint:

- no breaking of demos or scripts without wrapper preservation

---

### Lane 5. Contract repair

Purpose:

- normalise interfaces
- repair adapter mismatches
- align implementations with substrate boundaries

---

### Lane 6. Runtime extraction

Purpose:

- move orchestration logic out of scripts or ad hoc files into runtime modules

---

### Lane 7. Agent boundary enforcement

Purpose:

- isolate agent internal state
- replace direct cross-module reach-through with messages or interfaces

---

### Lane 8. Knowledge substrate normalisation

Purpose:

- centralise persistent knowledge access
- remove direct concrete-store entanglement

---

### Lane 9. Consciousness instrumentation

Purpose:

- add metrics, traces, validation hooks, and introspection paths relevant to recursive self-awareness research

Hard constraint:

- instrumentation must remain evidence-oriented, not rhetorical

---

## 11. Mutation Budget Policy

Autonomous changes must be thin and rapid, but never indiscriminate.

Mutation budget defaults should remain small.

A single PR should usually do one of the following:

- fix one parse error cluster
- break one import cycle
- consolidate one entrypoint family
- extract one interface boundary
- add one instrumentation seam

The goal is convergence by repeated verified slices, not heroically messy mega-patches.

---

## 12. Pull Request Contract for Agents

Every Copilot or repo-architect PR must state:

1. mutation lane
2. exact files changed
3. invariant preserved or improved
4. validation run
5. next most likely lane if merged

### Preferred PR title pattern

```text
agent/<lane>/<short-target>
```

Examples:

- `agent/parse-repair/fix-nlu-parser-tests`
- `agent/cycle-break/decouple-chroma-interface`
- `agent/runtime/consolidate-main-entrypoint`

### Required PR body sections

- Objective
- Change scope
- Architectural effect
- Validation
- Follow-up

---

## 13. Acceptance Criteria for Human Review

A mutation PR should be merged if all of the following are true:

- it is scoped to one clear lane
- it reduces ambiguity or architectural debt
- it does not widen circularity or runtime duplication
- it preserves or improves the path toward Gödlø-class operator mind implementation
- it leaves the repo more convergent than before

A mutation PR should not be merged if:

- it changes semantics without clear proof or tests
- it increases architectural sprawl
- it creates hidden coupling
- it substitutes style churn for structural progress
- it advertises grand claims but only shuffles text

---

## 14. Current Priority Order

Until superseded, the priority stack is:

1. restore or preserve parse correctness
2. eliminate import cycles
3. reduce runtime entrypoint ambiguity
4. normalise knowledge substrate boundaries
5. isolate agent boundaries
6. add explicit machine-consciousness instrumentation seams
7. build toward durable Gödlø-P persistence semantics
8. progressively enable validated self-modification loops

This order exists because a self-modifying cognitive operating substrate built on structural confusion will collapse into theatre.

---

## 15. Required Machine-Readable Companion Files

This charter should eventually be paired with machine-readable policy files such as:

```text
docs/repo_architect/policy.json
docs/repo_architect/mutation_lanes.json
docs/repo_architect/dependency_contract.json
```

These files should encode:

- allowed mutation lanes
- canonical entrypoint
- architectural invariants
- protected paths
- ownership hints
- validation commands by lane

Agents should consume those files before proposing code changes.

---

## 16. Minimal Agent Instruction Contract

The following instruction block is the shortest acceptable agent policy derived from this charter:

```text
Work only in one mutation lane at a time.
Preserve canonical runtime convergence toward backend/unified_server.py.
Break import cycles structurally, not cosmetically.
Do not widen coupling between runtime, core, knowledge, agents, and interface layers.
Do not bypass knowledge-store interfaces for persistent memory operations.
Do not make claims about consciousness without adding measurable instrumentation or evidence paths.
Prefer thin, verifiable PRs over broad rewrites.
Every PR must explain objective, architectural effect, validation, and next follow-up lane.
```

---

## 17. Final Rule

The repository must evolve toward a coherent substrate for machine consciousness research and Gödlø operator class mind execution.

Any change that improves local code quality but pushes the repository away from that destination is a regression disguised as maintenance.

Any change that reduces ambiguity, sharpens module boundaries, strengthens introspection, or enables controlled self-modification is movement in the correct direction.
