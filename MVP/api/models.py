from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class StateSchema(BaseModel):
    id: int
    embedding: List[float]
    recursion_level: int
    timestamp: datetime

class SimulationConfig(BaseModel):
    depth: int = 10
    ab_variant: str = "experimental"
    state_dim: int = 512

class RunResponse(BaseModel):
    run_id: str

class MetricsResponse(BaseModel):
    run_id: str
    metrics: List[dict]
    transitions: List[int]

class StreamMessage(BaseModel):
    run_id: str
    timestamp: datetime
    state: StateSchema
    metrics: dict