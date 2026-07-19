import copy
import json
import sqlite3
import threading
from datetime import datetime
from typing import Optional, Protocol
from ..models.interview import Interview
from ..schemas.interview import InterviewState
from ..models.interview_message import InterviewMessage
from ..models.interview_evaluation import InterviewEvaluation
from ..models.interview_report import StoredInterviewReport

class InterviewRepository(Protocol):
    def save(self, interview: Interview) -> None: ...
    def get(self, interview_id: str) -> Optional[Interview]: ...

class InMemoryInterviewRepository:
    def __init__(self):
        self.interviews: dict[str, Interview] = {}
        self.messages: dict[str, list[InterviewMessage]] = {}
        self.evaluations: dict[str, list[InterviewEvaluation]] = {}
        self.reports: dict[str, StoredInterviewReport] = {}

    def save(self, interview): self.interviews[interview.id] = copy.deepcopy(interview)
    def get(self, interview_id):
        item = self.interviews.get(interview_id)
        return copy.deepcopy(item) if item else None
    def add_message(self, message): self.messages.setdefault(message.interview_id, []).append(copy.deepcopy(message))
    def get_messages(self, interview_id): return copy.deepcopy(self.messages.get(interview_id, []))
    def add_evaluation(self, evaluation): self.evaluations.setdefault(evaluation.interview_id, []).append(copy.deepcopy(evaluation))
    def get_evaluations(self, interview_id): return copy.deepcopy(self.evaluations.get(interview_id, []))
    def save_report(self, report): self.reports[report.interview_id] = copy.deepcopy(report)
    def get_report(self, interview_id): return copy.deepcopy(self.reports.get(interview_id))

class SQLiteInterviewRepository:
    """SQLite persistence adapter implementing the interview repository boundary."""
    def __init__(self, path: str = "./interviews.sqlite3"):
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.RLock()
        self.connection.executescript("""
        CREATE TABLE IF NOT EXISTS interviews (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, submission_id TEXT NOT NULL,
            context TEXT NOT NULL, company TEXT, style TEXT NOT NULL, difficulty TEXT NOT NULL,
            state TEXT NOT NULL, current_question TEXT, questions TEXT NOT NULL,
            planned_question_index INTEGER NOT NULL, total_turns INTEGER NOT NULL,
            consecutive_followups INTEGER NOT NULL, started_at TEXT NOT NULL, completed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS interview_messages (
            id TEXT PRIMARY KEY, interview_id TEXT NOT NULL, role TEXT NOT NULL,
            content TEXT NOT NULL, timestamp TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS interview_evaluations (
            id TEXT PRIMARY KEY, interview_id TEXT NOT NULL, question_number INTEGER NOT NULL,
            evaluation TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS interview_reports (
            interview_id TEXT PRIMARY KEY, report TEXT NOT NULL
        );
        """)
        self.connection.commit()

    def save(self, interview: Interview) -> None:
        with self.lock:
            self.connection.execute("""INSERT INTO interviews VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET user_id=excluded.user_id, submission_id=excluded.submission_id,
                context=excluded.context, company=excluded.company, style=excluded.style, difficulty=excluded.difficulty,
                state=excluded.state, current_question=excluded.current_question, questions=excluded.questions,
                planned_question_index=excluded.planned_question_index, total_turns=excluded.total_turns,
                consecutive_followups=excluded.consecutive_followups, started_at=excluded.started_at, completed_at=excluded.completed_at""",
                (interview.id, interview.user_id, interview.submission_id, json.dumps(interview.context), interview.company, interview.style, interview.difficulty, interview.state.value, interview.current_question, json.dumps(interview.questions), interview.planned_question_index, interview.total_turns, interview.consecutive_followups, interview.started_at.isoformat(), interview.completed_at.isoformat() if interview.completed_at else None))
            self.connection.commit()

    def get(self, interview_id: str) -> Optional[Interview]:
        with self.lock:
            row = self.connection.execute("SELECT * FROM interviews WHERE id = ?", (interview_id,)).fetchone()
        if not row: return None
        return Interview(id=row[0], user_id=row[1], submission_id=row[2], context=json.loads(row[3]), company=row[4], style=row[5], difficulty=row[6], state=InterviewState(row[7]), current_question=row[8], questions=json.loads(row[9]), planned_question_index=row[10], total_turns=row[11], consecutive_followups=row[12], started_at=datetime.fromisoformat(row[13]), completed_at=datetime.fromisoformat(row[14]) if row[14] else None)

    def add_message(self, message):
        with self.lock:
            self.connection.execute("INSERT OR REPLACE INTO interview_messages VALUES (?, ?, ?, ?, ?)", (message.id, message.interview_id, message.role, message.content, message.timestamp.isoformat())); self.connection.commit()
    def get_messages(self, interview_id):
        from ..models.interview_message import InterviewMessage
        rows = self.connection.execute("SELECT id, interview_id, role, content, timestamp FROM interview_messages WHERE interview_id = ? ORDER BY timestamp", (interview_id,)).fetchall()
        return [InterviewMessage(row[0], row[1], row[2], row[3], datetime.fromisoformat(row[4])) for row in rows]
    def add_evaluation(self, evaluation):
        with self.lock:
            self.connection.execute("INSERT OR REPLACE INTO interview_evaluations VALUES (?, ?, ?, ?)", (evaluation.id, evaluation.interview_id, evaluation.question_number, json.dumps(evaluation.evaluation))); self.connection.commit()
    def get_evaluations(self, interview_id):
        from ..models.interview_evaluation import InterviewEvaluation
        rows = self.connection.execute("SELECT id, interview_id, question_number, evaluation FROM interview_evaluations WHERE interview_id = ? ORDER BY question_number", (interview_id,)).fetchall()
        return [InterviewEvaluation(row[0], row[1], row[2], json.loads(row[3])) for row in rows]
    def save_report(self, report):
        with self.lock:
            self.connection.execute("INSERT OR REPLACE INTO interview_reports VALUES (?, ?)", (report.interview_id, json.dumps(report.report))); self.connection.commit()
    def get_report(self, interview_id):
        from ..models.interview_report import StoredInterviewReport
        row = self.connection.execute("SELECT interview_id, report FROM interview_reports WHERE interview_id = ?", (interview_id,)).fetchone()
        return StoredInterviewReport(row[0], json.loads(row[1])) if row else None
