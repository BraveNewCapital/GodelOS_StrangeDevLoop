# System Overview

## High-Level Architecture

```mermaid
graph TB
    User[User / Researcher]
    UI[Svelte Frontend\nDashboard]
    WS[WebSocket Manager\nReal-time streaming]
    US[unified_server.py\nFastAPI]
    RCE[Recursive Consciousness\nEngine]
    CS[Cognitive State\nExtractor]
    GW[Global Workspace\nBroadcaster]
    IIT[IIT φ Calculator]
    PE[Phenomenal Experience\nGenerator]
    MC[Metacognitive\nReflection Engine]
    KS[Knowledge Store]
    INF[Inference Engine\n+ Provers]
    LRN[Learning System]

    User --> UI
    UI <-->|WS| WS
    WS <--> US
    US --> RCE
    RCE --> CS
    CS --> IIT
    CS --> GW
    GW --> PE
    PE --> MC
    MC --> RCE
    US --> KS
    US --> INF
    US --> LRN
    KS <--> INF
    INF <--> LRN
```

## Directory Structure

| Path | Purpose |
|------|---------|
| `backend/` | FastAPI backend, unified server, WebSocket manager |
| `backend/core/` | Consciousness engine, phenomenal experience, metacognition |
| `svelte-frontend/` | Svelte UI, real-time dashboard |
| `godelOS/` | Core Python cognitive modules |
| `tests/` | Pytest backend + Playwright E2E |
| `docs/` | Architecture specs, whitepapers, analysis |
| `wiki/` | This wiki |

## Key Entry Points

| File | Role |
|------|------|
| `backend/unified_server.py` | FastAPI app, all routes, startup wiring |
| `backend/core/unified_consciousness_engine.py` | Master consciousness loop |
| `backend/core/phenomenal_experience.py` | Qualia generation |
| `svelte-frontend/src/App.svelte` | Root UI component |
| `godelOS/` | Symbolic reasoning, knowledge, learning subsystems |

## Runtime Ports

| Service | Port |
|---------|------|
| FastAPI backend | 8000 |
| WebSocket endpoint | 8000/ws |
| Svelte dev server | 5173 |
| Prometheus metrics | 8000/metrics |
