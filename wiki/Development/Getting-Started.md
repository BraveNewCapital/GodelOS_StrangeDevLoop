# Getting Started

## Prerequisites

| Requirement | Version |
|-------------|----------|
| Python | 3.8+ |
| Node.js | 18+ |
| Git | Any recent |
| RAM | 8GB minimum, 16GB recommended |

## Setup

```bash
# 1. Clone
git clone https://github.com/Steake/GodelOS.git
cd GodelOS

# 2. Python environment
./scripts/setup_venv.sh
source godelos_venv/bin/activate
pip install -r requirements.txt

# 3. Environment config
cp backend/.env.example backend/.env
# Edit backend/.env — add your LLM API key (OpenAI or local)

# 4. Start backend
./scripts/start-unified-server.sh
# Or: python backend/unified_server.py
# Runs on http://localhost:8000

# 5. Start frontend (separate terminal)
cd svelte-frontend
npm install
npm run dev
# Runs on http://localhost:5173
```

## One-Command Dev Start

```bash
./start-godelos.sh --dev
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | For LLM | OpenAI API key for consciousness assessment |
| `GODELOS_HOST` | No | Backend host (default: localhost) |
| `GODELOS_PORT` | No | Backend port (default: 8000) |
| `CONSCIOUSNESS_THRESHOLD` | No | Emergence score threshold (default: 0.8) |

## Verifying Your Install

```bash
# Check backend is running
curl http://localhost:8000/api/health

# Check cognitive loop
curl http://localhost:8000/api/v1/cognitive/loop

# Run test suite
pytest tests/ -v --tb=short -q
```
