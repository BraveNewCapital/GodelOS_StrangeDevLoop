# Examples

This folder contains small demos and runnable examples that showcase different parts of GödelOS.

## Highlights
- demo_tui.py — interactive TUI demo
- simple_example.py — minimal usage
- godelos_nlp_demo_extended.py — NLP pipeline demo
- test_runner_demo.py — example flows for the test runner
- godel_os_example.py — end-to-end example wiring

Some examples rely on the backend server. Start it first if needed:

```bash
source godelos_venv/bin/activate
./start-godelos.sh --dev
```

## Run

```bash
# TUI demo
python examples/demo_tui.py

# Simple example
python examples/simple_example.py

# Spec-aligned test runner demo
python examples/test_runner_demo.py
```

See individual files and notebooks for details.
