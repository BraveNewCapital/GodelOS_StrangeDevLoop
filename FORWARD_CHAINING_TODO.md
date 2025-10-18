# Forward-Chaining Inference Implementation TODO

## Current Status
✅ **XFAIL reporting fixed** - BDD runner now correctly shows `⚠ XFAIL` instead of `⊘ SKIPPED`

⚠️ **Forward-chaining not implemented** - Test `test_user_story_knowledge_reasoning_nlg` is marked as expected fail

## The Problem

**Test scenario:**
1. Assert rule: `forall ?x. (Human(?x) => Mortal(?x))`
2. Assert fact: `Human(Socrates)`
3. Prove goal: `Mortal(Socrates)`

**Current behavior:**
- ❌ Proof fails because engine only does:
  - Direct existence check (is `Mortal(Socrates)` in KB?)
  - Pattern query (does it match a stored pattern?)
- ❌ Does NOT apply the rule to derive new facts

**Expected behavior:**
- ✅ Should apply forward chaining:
  - Match `Human(Socrates)` to antecedent `Human(?x)`
  - Bind `?x = Socrates`
  - Derive `Mortal(Socrates)` from consequent
  - Prove goal succeeds

## Implementation Plan

### Phase 1: Basic Forward Chaining (Required for test to pass)

**File**: `backend/core/nl_semantic_parser.py` - InferenceEngine class

**Add to `prove()` method** after Step 2 (pattern query):

```python
# Step 3: Forward chaining from rules
if not success:
    await self._proof_step(steps, "Attempting forward chaining from rules", True, rule="forward-chain")
    
    # Get all rules from contexts (formulas with => implication)
    rules = await self._ksi.get_rules(context_ids=ctxs)
    
    for rule in rules:
        # Check if rule is universal quantification with implication
        if isinstance(rule, Forall) and isinstance(rule.body, Implies):
            antecedent = rule.body.antecedent
            consequent = rule.body.consequent
            
            # Try to unify goal with consequent
            substitution = self._unify(goal_ast, consequent)
            
            if substitution:
                # Apply substitution to antecedent
                grounded_antecedent = self._apply_substitution(antecedent, substitution)
                
                # Check if grounded antecedent exists in KB
                if await self._ksi.statement_exists(grounded_antecedent, context_ids=ctxs):
                    await self._proof_step(
                        steps,
                        f"Applied rule: {rule} with bindings {substitution}",
                        True,
                        rule="forward-chain",
                        bindings=substitution
                    )
                    success = True
                    break
```

**Required helper methods:**

```python
def _unify(self, term1: AST_Node, term2: AST_Node) -> Optional[Dict[str, AST_Node]]:
    """Simple unification for forward chaining."""
    # Implementation based on existing UnificationEngine
    # or simple pattern matching for basic cases
    pass

def _apply_substitution(self, term: AST_Node, subst: Dict[str, AST_Node]) -> AST_Node:
    """Apply variable substitution to term."""
    pass
```

### Phase 2: Integration with Existing Inference Components

**Option A: Use existing UnificationEngine**
- File: `backend/core/unification_engine.py`
- Already has `unify()` method
- Need to integrate with InferenceEngine

**Option B: Use InferenceCoordinator**
- File: `backend/core/inference_coordinator.py`
- More sophisticated multi-strategy prover
- Supports resolution, tableau, etc.
- May be overkill for simple forward chaining

### Phase 3: Advanced Features (Post-MVP)

1. **Backward chaining** - Goal-directed reasoning
2. **Multi-step chaining** - Chains multiple rules
3. **Cycle detection** - Prevent infinite loops
4. **Resource limits** - Timeout and max depth
5. **Proof explanation** - Human-readable proof traces

## Files to Modify

1. ✅ **`godelOS/test_runner/bdd_runner.py`** - DONE (xfail reporting fixed)
2. ⚠️ **`backend/core/nl_semantic_parser.py`** - TODO (add forward chaining)
3. 📋 **`backend/core/ksi_adapter.py`** - May need `get_rules()` method
4. 📋 **`tests/spec_aligned/test_user_stories_live.py`** - Remove xfail once implemented

## Testing Strategy

### Unit Tests
```python
def test_forward_chaining_simple():
    """Test: Rule + Fact → Derived Fact"""
    # Assert: Human(x) => Mortal(x)
    # Assert: Human(Socrates)
    # Prove: Mortal(Socrates) → Should succeed
    pass

def test_forward_chaining_multiple_rules():
    """Test: Multiple rules with same consequent"""
    pass

def test_forward_chaining_no_match():
    """Test: Rule exists but antecedent not satisfied"""
    # Assert: Human(x) => Mortal(x)
    # Assert: Cat(Felix)
    # Prove: Mortal(Felix) → Should fail
    pass
```

### Integration Test
The existing `test_user_story_knowledge_reasoning_nlg` will validate:
- NL → AST parsing
- KSI assertion
- Forward chaining inference
- NLG realization

## Estimated Effort

- **Phase 1 (Basic forward chaining)**: 2-4 hours
  - Implement unification
  - Add rule retrieval
  - Add forward chaining logic
  - Test with simple cases

- **Phase 2 (Integration)**: 1-2 hours
  - Hook into existing components
  - Add error handling
  - Update docs

- **Phase 3 (Advanced features)**: 4-8 hours
  - Backward chaining
  - Multi-step reasoning
  - Optimization

## Current Workaround

The test is marked as `pytest.xfail()` with message:
```
"Basic inference engine did not prove the goal (no forward-chaining)"
```

This is **correct behavior** - the test validates that the system:
1. ✅ Parses NL correctly
2. ✅ Stores rules and facts in KSI
3. ✅ Queries successfully
4. ⚠️ **Needs forward chaining to complete proof**

Once forward chaining is implemented, remove the xfail and the test will pass!

## Related Spec Requirements

From `docs/SPECIFICATION.md`:

> **§3.2 Inference Engine Requirements**
> - The system SHALL support forward chaining inference
> - The system SHALL apply rules to derive new facts
> - The system SHALL provide proof traces for transparency

This implementation directly addresses these requirements.

---

**Next Actions:**
1. ✅ Implement Phase 1 (basic forward chaining)
2. ✅ Test with `test_user_story_knowledge_reasoning_nlg`
3. ✅ Remove xfail from test
4. ✅ Run full BDD suite - should see 48/48 passing
