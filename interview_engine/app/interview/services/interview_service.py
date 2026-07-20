from datetime import datetime, timezone
import threading
from uuid import uuid4
from ..models.interview import Interview
from ..models.interview_message import InterviewMessage
from ..models.interview_evaluation import InterviewEvaluation
from ..models.interview_report import StoredInterviewReport
from ..schemas.interview import InterviewState
from ..schemas.evaluation import Evaluation
from .context_builder import build_context
from .planner import Planner
from .interviewer import Interviewer
from .evaluator import Evaluator
from .followup_generator import FollowupGenerator
from .report_generator import ReportGenerator
from ...analytics.utils.event_publisher import NullEventPublisher

TRANSITIONS = {
    InterviewState.CREATED: {InterviewState.PLANNING}, InterviewState.PLANNING: {InterviewState.READY},
    InterviewState.READY: {InterviewState.QUESTIONING}, InterviewState.QUESTIONING: {InterviewState.WAITING_FOR_ANSWER},
    InterviewState.WAITING_FOR_ANSWER: {InterviewState.FOLLOW_UP, InterviewState.QUESTIONING, InterviewState.COMPLETED},
    InterviewState.FOLLOW_UP: {InterviewState.WAITING_FOR_ANSWER, InterviewState.COMPLETED},
    InterviewState.COMPLETED: {InterviewState.REPORT_GENERATED}, InterviewState.REPORT_GENERATED: set(),
}

class InterviewService:
    MAX_CONSECUTIVE_FOLLOWUPS = 2
    def __init__(self, repository, planner=None, interviewer=None, evaluator=None, followups=None, reports=None, *, event_publisher=None):
        self.repository = repository; self.planner = planner or Planner(); self.interviewer = interviewer or Interviewer()
        self.evaluator = evaluator or Evaluator(); self.followups = followups or FollowupGenerator(); self.reports = reports or ReportGenerator()
        self.event_publisher = event_publisher or NullEventPublisher()
        self._mutation_locks = {}
        self._mutation_locks_guard = threading.Lock()

    def _mutation_lock(self, interview_id):
        with self._mutation_locks_guard:
            return self._mutation_locks.setdefault(interview_id, threading.Lock())

    def transition(self, interview, target):
        if target not in TRANSITIONS[interview.state]: raise ValueError(f"Invalid transition: {interview.state} -> {target}")
        interview.state = target; self.repository.save(interview)

    def start(self, request, llm=None):
        context = build_context(request.context)
        interview = Interview(str(uuid4()), request.context.user_id, request.context.submission_id, context, request.company, request.style, request.context.difficulty)
        self.repository.save(interview); self.transition(interview, InterviewState.PLANNING)
        planner = Planner(llm) if llm is not None else self.planner
        interview.questions = planner.create_plan(context, request.company, request.style); self.repository.save(interview)
        self.transition(interview, InterviewState.READY); self.transition(interview, InterviewState.QUESTIONING)
        interview.current_question = self.interviewer.first_question(interview.questions); self.repository.save(interview)
        self.repository.add_message(InterviewMessage(str(uuid4()), interview.id, "AI", interview.current_question))
        self.transition(interview, InterviewState.WAITING_FOR_ANSWER)
        self.event_publisher.publish(
            event_type="INTERVIEW_STARTED",
            source="interview",
            user_id=interview.user_id,
            metadata={
                "interview_id": interview.id,
                "problem_title": request.context.problem_title,
                "difficulty": interview.difficulty,
                "language": request.context.language,
            },
        )
        return interview

    def answer(self, interview_id, answer, llm=None):
        lock = self._mutation_lock(interview_id)
        if not lock.acquire(blocking=False):
            raise ValueError("Interview mutation already in progress")
        try:
            return self._answer_locked(interview_id, answer, llm)
        finally:
            lock.release()

    def _answer_locked(self, interview_id, answer, llm=None):
        interview = self.require(interview_id)
        if interview.state != InterviewState.WAITING_FOR_ANSWER: raise ValueError("Interview is not accepting an answer")
        self.repository.add_message(InterviewMessage(str(uuid4()), interview.id, "USER", answer))
        evaluator = Evaluator(llm) if llm is not None else self.evaluator
        followups = FollowupGenerator(llm) if llm is not None else self.followups
        evaluation = evaluator.evaluate(interview.current_question or "", answer, interview.context)
        interview.total_turns += 1
        self.repository.add_evaluation(InterviewEvaluation(str(uuid4()), interview.id, interview.total_turns, evaluation.model_dump()))
        score = round(sum((evaluation.technical_accuracy, evaluation.communication, evaluation.complexity_understanding, evaluation.edge_case_reasoning, evaluation.confidence)) / 5, 2)
        self.event_publisher.publish(
            event_type="QUESTION_ANSWERED",
            source="interview",
            user_id=interview.user_id,
            metadata={
                "interview_id": interview.id,
                "question_number": interview.total_turns,
                "score": score,
                "provider_used": evaluation.provider_used,
            },
        )
        followup = None
        if interview.consecutive_followups < self.MAX_CONSECUTIVE_FOLLOWUPS:
            followup = followups.generate(interview.current_question or "", answer, min(evaluation.technical_accuracy, evaluation.communication))
        if followup:
            interview.consecutive_followups += 1
            self.transition(interview, InterviewState.FOLLOW_UP); interview.current_question = followup; self.repository.save(interview)
            self.repository.add_message(InterviewMessage(str(uuid4()), interview.id, "AI", followup)); self.transition(interview, InterviewState.WAITING_FOR_ANSWER)
        else:
            interview.planned_question_index += 1
            interview.consecutive_followups = 0
            next_q = self.interviewer.next_question(interview.questions, interview.planned_question_index)
            if next_q:
                self.transition(interview, InterviewState.QUESTIONING); interview.current_question = next_q; self.repository.save(interview)
                self.repository.add_message(InterviewMessage(str(uuid4()), interview.id, "AI", next_q)); self.transition(interview, InterviewState.WAITING_FOR_ANSWER)
            else:
                interview.current_question = None; interview.completed_at = datetime.now(timezone.utc); self.repository.save(interview); self.transition(interview, InterviewState.COMPLETED)
        return evaluation, self.require(interview_id).current_question

    def finish(self, interview_id, llm=None):
        lock = self._mutation_lock(interview_id)
        if not lock.acquire(blocking=False):
            raise ValueError("Interview mutation already in progress")
        try:
            return self._finish_locked(interview_id, llm)
        finally:
            lock.release()

    def _finish_locked(self, interview_id, llm=None):
        interview = self.require(interview_id)
        if interview.state not in (InterviewState.COMPLETED, InterviewState.WAITING_FOR_ANSWER, InterviewState.FOLLOW_UP): raise ValueError("Interview cannot be finished in its current state")
        interview.completed_at = interview.completed_at or datetime.now(timezone.utc); interview.state = InterviewState.COMPLETED; self.repository.save(interview)
        reports = ReportGenerator(llm) if llm is not None else self.reports
        report = reports.generate(interview.id, [x.evaluation for x in self.repository.get_evaluations(interview.id)], interview.context)
        self.repository.save_report(StoredInterviewReport(interview.id, report.model_dump())); self.transition(interview, InterviewState.REPORT_GENERATED)
        self.event_publisher.publish(
            event_type="INTERVIEW_COMPLETED",
            source="interview",
            user_id=interview.user_id,
            metadata={
                "interview_id": interview.id,
                "score": report.overall_score,
                "duration_seconds": max(0, (interview.completed_at - interview.started_at).total_seconds()),
                "difficulty": interview.difficulty,
                "provider_used": report.provider_used,
            },
        )
        return report

    def require(self, interview_id):
        item = self.repository.get(interview_id)
        if not item: raise KeyError("Interview not found")
        return item
