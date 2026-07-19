import threading
import time
from interview_engine.app.interview.repositories.interview_repository import InMemoryInterviewRepository
from interview_engine.app.interview.services.interview_service import InterviewService
from interview_engine.app.interview.schemas.interview import InterviewCreate
from interview_engine.app.interview.schemas.submission_context import SubmissionContext
from interview_engine.app.interview.schemas.evaluation import Evaluation

def request():
    return InterviewCreate(context=SubmissionContext(submission_id="lock-s", user_id="lock-u", problem_title="p", problem_description="d", language="python", code="x=1", execution_result="passed", hint_count=0, attempt_count=1, difficulty="Easy"))

class SlowEvaluator:
    def evaluate(self, *args):
        time.sleep(0.1)
        return Evaluation(technical_accuracy=8, communication=8, complexity_understanding=8, edge_case_reasoning=8, confidence=8, feedback="ok")

def test_concurrent_answer_mutation_rejects_overlap():
    service = InterviewService(InMemoryInterviewRepository(), evaluator=SlowEvaluator())
    interview = service.start(request())
    results = []
    def submit():
        try: results.append(service.answer(interview.id, "answer"))
        except ValueError as exc: results.append(exc)
    first = threading.Thread(target=submit); second = threading.Thread(target=submit)
    first.start(); time.sleep(0.02); second.start(); first.join(); second.join()
    assert sum(isinstance(result, ValueError) for result in results) == 1
