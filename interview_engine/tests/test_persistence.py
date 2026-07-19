import os
import tempfile
from interview_engine.app.interview.repositories.interview_repository import SQLiteInterviewRepository
from interview_engine.app.interview.services.interview_service import InterviewService
from interview_engine.app.interview.schemas.interview import InterviewCreate
from interview_engine.app.interview.schemas.submission_context import SubmissionContext

def test_sqlite_repository_survives_repository_recreation():
    fd, path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    try:
        request = InterviewCreate(context=SubmissionContext(submission_id="persist-s", user_id="persist-u", problem_title="Persist", problem_description="Persist data", language="python", code="x = 1", execution_result="passed", hint_count=0, attempt_count=1, difficulty="Easy"))
        first = InterviewService(SQLiteInterviewRepository(path))
        created = first.start(request)
        second = SQLiteInterviewRepository(path)
        loaded = second.get(created.id)
        assert loaded is not None
        assert loaded.user_id == "persist-u"
        assert loaded.current_question == created.current_question
    finally:
        os.remove(path)
