from typing import List
from ..models.execution_trace import ExecutionStep
from .tracer import RawExecutionEvent
from .variable_tracker import VariableTracker

class TimelineBuilder:
    def __init__(self, tracker=None): self.tracker = tracker or VariableTracker()

    def build(self, trace_id: str, events: List[RawExecutionEvent]) -> List[ExecutionStep]:
        histories = self.tracker.histories([event.locals for event in events])
        return [ExecutionStep(trace_id, index, event.line_number, event.code, event.event_type, event.locals, event.globals, event.call_stack, event.stdout, event.error, histories[index - 1]) for index, event in enumerate(events, 1)]
