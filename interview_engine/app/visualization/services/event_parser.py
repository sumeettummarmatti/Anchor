from typing import List
from .tracer import RawExecutionEvent

class EventParser:
    def parse(self, events: List[RawExecutionEvent]) -> List[RawExecutionEvent]:
        return [event for event in events if event.event_type in {"FUNCTION_CALL", "LINE_EXECUTED", "FUNCTION_RETURN", "EXCEPTION"}]
