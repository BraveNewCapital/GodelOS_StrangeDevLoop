from fastapi import FastAPI, WebSocket, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import asyncio
import uuid
import numpy as np
import os
from MVP.core.recursive_observer import RecursiveObserver
from MVP.core.surprise_calculator import SurpriseCalculator
from MVP.core.phase_detector import PhaseDetector
from MVP.core.ood_generator import OODGenerator
from MVP.core.behavioral_emergence_tracker import BehavioralEmergenceTracker
from MVP.core.llm_client import LLMClient
from MVP.persistence.db import ChromaDB
from .models import SimulationConfig, RunResponse, MetricsResponse, StateSchema, StreamMessage

app = FastAPI(title="GödelOS MVP API")

db = ChromaDB()
llm_client = LLMClient()
sim_runs = {}

@app.post("/api/simulate", response_model=RunResponse)
async def simulate(config: SimulationConfig):
    run_id = str(uuid.uuid4())
    # Initial prompt for LLM to get s0
    prompt = "Initial cognitive state for consciousness simulation."
    s0_text = llm_client.generate_cognitive_state(prompt)
    s0 = llm_client.embed_state_text(s0_text)
    observer = RecursiveObserver(state_dim=config.state_dim)
    states_phi = observer.observe(s0)
    states = [s.numpy() for s, _ in states_phi]
    phi_list = [p for _, p in states_phi]

    # Surprise
    calc = SurpriseCalculator(config.state_dim)
    p_n_dict = calc.calculate_p_n(states)

    # Phase
    metrics = {'c_n': np.random.random(len(phi_list)), 'phi_n': phi_list, 'g_n': [0.5] * len(phi_list)}  # Placeholder c_n
    phase = PhaseDetector()
    phase_results = phase.detect_phases(metrics)

    # OOD
    gen = OODGenerator(config.state_dim)
    ood_scenarios = gen.generate_scenarios(5, "meta_adaptation")

    # Behavioral (placeholder logs)
    beh_tracker = BehavioralEmergenceTracker()
    beh_results = beh_tracker.track_emergence(states_phi, [], [], [], [], g_prior=np.zeros(512))

    # Store in DB
    metadatas = [{"run_id": run_id, "level": i, "type": "state"} for i in range(len(states))]
    db.store_states(states, metadatas)
    metrics_list = [{'phi_n': phi, 'p_n': p_n_dict['p_n'], 'c_n': metrics['c_n'][i]} for i, phi in enumerate(phi_list)]
    sim_runs[run_id] = {
        'states': states,
        'metrics': metrics_list,
        'transitions': [5] if phase_results['significant_transition'] else [],
        'ood_scenarios': ood_scenarios,
        'behavioral': beh_results
    }

    return RunResponse(run_id=run_id)

@app.get("/api/metrics/{run_id}", response_model=MetricsResponse)
async def get_metrics(run_id: str):
    if run_id not in sim_runs:
        raise HTTPException(status_code=404, detail="Run not found")
    sim = sim_runs[run_id]
    return MetricsResponse(run_id=run_id, metrics=sim['metrics'], transitions=sim['transitions'])

@app.websocket("/ws/stream/{run_id}")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    # Demo stream
    for i in range(10):
        state = StateSchema(id=i, embedding=np.random.randn(512).tolist(), recursion_level=i, timestamp=datetime.now())
        msg = StreamMessage(run_id="demo", timestamp=datetime.now(), state=state, metrics={'c_n': 0.6})
        await websocket.send_json(msg.dict())
        await asyncio.sleep(0.2)
    await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
