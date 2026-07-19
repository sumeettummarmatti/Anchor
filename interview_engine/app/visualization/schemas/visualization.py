from pydantic import BaseModel, Field

class TraceCreate(BaseModel):
    language: str = Field(min_length=1)
    source_code: str = Field(min_length=1)

class TraceCreated(BaseModel):
    trace_id: str

class TraceSummary(BaseModel):
    trace_id: str
    algorithm_flow: str
    important_events: list[str]
    recursion_summary: str
    loop_behavior: str
    variable_evolution: dict[str, list]
    final_output: str
    execution_length: int
    provider_used: str = "fallback"
