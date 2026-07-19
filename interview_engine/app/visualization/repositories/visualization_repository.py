import copy
from typing import Dict, Optional
from ..models.execution_trace import ExecutionTrace

class VisualizationRepository:
    def __init__(self): self.traces: Dict[str, ExecutionTrace] = {}
    def save(self, trace: ExecutionTrace): self.traces[trace.id] = copy.deepcopy(trace)
    def get(self, trace_id: str) -> Optional[ExecutionTrace]:
        trace = self.traces.get(trace_id)
        return copy.deepcopy(trace) if trace else None
