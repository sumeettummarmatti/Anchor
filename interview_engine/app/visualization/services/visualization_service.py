from uuid import uuid4
from ..models.execution_trace import ExecutionTrace
from .tracer import BaseTracer, PythonTracer
from .event_parser import EventParser
from .timeline_builder import TimelineBuilder
from .ai_explainer import AIExplainer
from .summary_generator import SummaryGenerator
from ...analytics.utils.event_publisher import NullEventPublisher

class VisualizationService:
    def __init__(self, repository, tracer: BaseTracer = None, parser=None, timeline=None, explainer=None, summary=None, *, event_publisher=None):
        self.repository = repository
        self.tracer = tracer or PythonTracer()
        self.parser = parser or EventParser()
        self.timeline = timeline or TimelineBuilder()
        self.explainer = explainer or AIExplainer()
        self.summary_generator = summary or SummaryGenerator()
        self.event_publisher = event_publisher or NullEventPublisher()

    def create_trace(self, language: str, source_code: str, user_id: str = "system", llm=None) -> ExecutionTrace:
        if language.lower() != "python":
            raise ValueError("Only Python tracing is supported in this phase")
        trace_id = str(uuid4())
        raw_events = self.parser.parse(self.tracer.trace(source_code))
        steps = self.timeline.build(trace_id, raw_events)
        trace = ExecutionTrace(trace_id, language, source_code, steps=steps)
        summary_generator = SummaryGenerator(llm) if llm is not None else self.summary_generator
        trace.summary = summary_generator.generate(trace_id, source_code, steps).model_dump()
        self.repository.save(trace)
        metadata = {
            "trace_id": trace.id,
            "language": language,
            "step_count": len(steps),
            "provider_used": trace.summary.get("provider_used", "fallback"),
        }
        self.event_publisher.publish(event_type="TRACE_CREATED", source="visualization", user_id=user_id, metadata=metadata)
        self.event_publisher.publish(event_type="TRACE_COMPLETED", source="visualization", user_id=user_id, metadata=metadata)
        self.event_publisher.publish(event_type="EXECUTION_COMPLETED", source="visualization", user_id=user_id, metadata=metadata)
        return trace

    def get(self, trace_id):
        trace = self.repository.get(trace_id)
        if not trace: raise KeyError("Execution trace not found")
        return trace

    def explain_step(self, trace_id, step_number, llm=None):
        trace = self.get(trace_id)
        step = next((item for item in trace.steps if item.step_number == step_number), None)
        if not step: raise KeyError("Execution step not found")
        annotation = trace.annotations.get(step_number)
        if annotation is None:
            explainer = AIExplainer(llm) if llm is not None else self.explainer
            annotation = explainer.explain(trace_id, step)
            trace.annotations[step_number] = annotation
            self.repository.save(trace)
        return step, annotation
