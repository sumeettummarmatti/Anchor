import pytest
from interview_engine.app.interview.repositories.interview_repository import InMemoryInterviewRepository
from interview_engine.app.interview.services.interview_service import InterviewService
from interview_engine.app.interview.schemas.interview import InterviewCreate, AnswerRequest, InterviewState
from interview_engine.app.interview.schemas.submission_context import SubmissionContext
from interview_engine.app.interview.schemas.evaluation import Evaluation
from interview_engine.app.interview.services.context_builder import build_context
from interview_engine.app.interview.services.planner import Planner
from interview_engine.app.interview.services.evaluator import Evaluator
from interview_engine.app.interview.services.followup_generator import FollowupGenerator
from interview_engine.app.interview.services.report_generator import ReportGenerator
from interview_engine.app.core.llm import LLMAuthError

def request():
    return InterviewCreate(context=SubmissionContext(submission_id="s1", user_id="u1", problem_title="Two Sum", problem_description="Find two numbers", language="python", code="return []", execution_result="passed", hint_count=0, attempt_count=1, difficulty="Easy"))

def test_creation_and_transitions():
    service = InterviewService(InMemoryInterviewRepository())
    interview = service.start(request())
    assert interview.state == InterviewState.WAITING_FOR_ANSWER
    assert interview.current_question
    with pytest.raises(ValueError, match="Invalid transition"):
        service.transition(interview, InterviewState.CREATED)

def test_answer_and_report_generation():
    service = InterviewService(InMemoryInterviewRepository())
    interview = service.start(request())
    evaluation, question = service.answer(interview.id, "I use a hash map. The time complexity is O(n) and space is O(n). Empty inputs and duplicates are handled.")
    assert evaluation.technical_accuracy >= 0
    assert question is not None
    while service.require(interview.id).state == InterviewState.WAITING_FOR_ANSWER:
        service.answer(interview.id, "The approach is linear, with O(n) time and O(n) space. I handle empty, null, duplicate, and boundary cases.")
    report = service.finish(interview.id)
    assert report.interview_id == interview.id
    assert service.require(interview.id).state == InterviewState.REPORT_GENERATED

def test_repository_operations_are_copy_safe():
    repository = InMemoryInterviewRepository(); service = InterviewService(repository)
    item = service.start(request()); fetched = repository.get(item.id); fetched.current_question = "changed"
    assert repository.get(item.id).current_question != "changed"

class FollowupOnce:
    def __init__(self): self.called = False
    def generate(self, question, answer, score, context=None):
        if not self.called:
            self.called = True
            return "Follow up on question one"
        return None

class AlwaysFollowup:
    def generate(self, question, answer, score, context=None): return "Deeper follow-up"

class LowEvaluator:
    def evaluate(self, question, answer, context):
        return Evaluation(technical_accuracy=1, communication=1, complexity_understanding=1, edge_case_reasoning=1, confidence=1, feedback="low")


class AuthFailLLM:
    def complete_json(self, system, user):
        raise LLMAuthError("simulated provider authentication failure")

class ThreeQuestionPlanner:
    def create_plan(self, context, company=None, style="Friendly"): return ["Planned Q1", "Planned Q2", "Planned Q3"]

def test_followup_does_not_skip_next_planned_question():
    service = InterviewService(InMemoryInterviewRepository(), planner=ThreeQuestionPlanner(), followups=FollowupOnce())
    interview = service.start(request())
    assert interview.current_question == "Planned Q1"
    _, followup = service.answer(interview.id, "weak first answer")
    assert followup == "Follow up on question one"
    _, next_question = service.answer(interview.id, "clarified answer")
    assert next_question == "Planned Q2"
    saved = service.require(interview.id)
    assert saved.planned_question_index == 1
    assert saved.total_turns == 2

def test_followups_are_capped_per_planned_question():
    service = InterviewService(InMemoryInterviewRepository(), planner=ThreeQuestionPlanner(), evaluator=LowEvaluator(), followups=AlwaysFollowup())
    interview = service.start(request())
    service.answer(interview.id, "weak")
    service.answer(interview.id, "still weak")
    _, next_question = service.answer(interview.id, "still weak")
    assert next_question == "Planned Q2"
    saved = service.require(interview.id)
    assert saved.consecutive_followups == 0
    assert saved.total_turns == 3


def test_interview_answer_uses_fallbacks_when_the_model_is_unavailable():
    llm = AuthFailLLM()
    service = InterviewService(
        InMemoryInterviewRepository(),
        planner=Planner(llm), evaluator=Evaluator(llm), followups=FollowupGenerator(llm), reports=ReportGenerator(llm),
    )
    interview = service.start(request())
    evaluation, _ = service.answer(interview.id, "I would use a hash map and explain the lookup trade-off.")
    assert evaluation.technical_accuracy > 0

def test_followup_fallback_uses_different_context_templates():
    from interview_engine.app.interview.services.followup_generator import FollowupGenerator
    generator = FollowupGenerator()
    vague = generator.generate("Explain your approach", "I used a map.", 3)
    complexity_blind = generator.generate("Analyze complexity", "I scan the array and return the answer after checking every value carefully.", 3)
    assert vague != complexity_blind
    assert "example" in vague.lower()
    assert "complex" in complexity_blind.lower()

def test_context_builder_derives_execution_and_struggle_signals():
    context = build_context(request().context)
    assert context["execution_status"] == "passed"
    assert context["execution_passed"] is True
    assert context["struggle_level"] == "low"
    assert context["code_line_count"] == 1
    struggled = request().context.model_copy(update={"hint_count": 1, "attempt_count": 2, "execution_result": "failed"})
    enriched = build_context(struggled)
    assert enriched["execution_status"] == "not_passed"
    assert enriched["struggle_level"] == "high"


def test_fallback_questions_reference_the_submitted_code():
    questions = Planner().create_plan({"problem_title": "Two Sum", "problem_description": "Find a pair", "difficulty": "Easy", "code": "def locate_pair(nums):\n    return nums"})
    assert all("`locate_pair`" in question for question in questions)


def test_answer_coach_fallback_uses_the_submitted_code():
    from interview_engine.app.interview.services.answer_coach import AnswerCoach
    answer, provider = AnswerCoach().generate("Explain the code", {"code": "def locate_pair(nums):\n    return nums"})
    assert "`locate_pair`" in answer
    assert provider == "fallback"


def test_answer_example_is_available_for_the_current_question():
    service = InterviewService(InMemoryInterviewRepository())
    interview = service.start(request())
    answer, provider = service.answer_example(interview.id)
    assert answer
    assert provider == "fallback"


def test_next_question_skips_without_creating_an_evaluation():
    service = InterviewService(InMemoryInterviewRepository(), planner=ThreeQuestionPlanner())
    interview = service.start(request())
    next_question = service.next_question(interview.id)
    assert next_question == "Planned Q2"
    assert service.require(interview.id).total_turns == 0
