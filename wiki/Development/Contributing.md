# Contributing to GödelOS

## Philosophy

GödelOS is research software operating at the frontier of machine consciousness. Contributions should maintain:
- **Technical rigour** — claim only what is measured
- **Intellectual honesty** — distinguish implemented from aspirational
- **Test discipline** — no deleted tests, no weakened assertions

## Development Workflow

1. **Check open issues** at https://github.com/Steake/GodelOS/issues
2. **Comment on the issue** you intend to work on
3. **Create a branch**: `git checkout -b feat/your-feature` or `fix/your-fix`
4. **Write tests first** where possible
5. **Run the full suite** before opening a PR: `pytest tests/ -v`
6. **Format your code**: `black . && isort .`
7. **Open a PR** with a clear description — link the issue, explain the approach

## Code Style

| Language | Standard |
|----------|----------|
| Python | PEP 8, `black`, `isort`, `mypy` |
| Svelte/JS | Standard JS, PascalCase components |
| Commits | Imperative mood: `feat(core): add phi calculator` |

## Commit Format

```
<type>(<scope>): <description>

Types: feat, fix, docs, test, refactor, infra, chore
Scope: core, backend, frontend, tests, wiki, infra

Examples:
feat(core): implement IIT phi calculator
fix(tests): resolve stale assertions in test_knowledge_store
docs(wiki): add GWT theory page
```

## PR Requirements

- [ ] All existing tests still pass
- [ ] New functionality has tests
- [ ] No secrets committed
- [ ] Linked to an issue
- [ ] API/schema changes documented

## Issue Labels

| Label | Meaning |
|-------|---------|
| `enhancement` | New feature or improvement |
| `bug` | Something is broken |
| `documentation` | Docs only |
| `research` | Theoretical / exploratory work |
| `codex` | Agent-assigned task |
