from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import logging
import os
from .core.config import settings
from .interview.repositories.interview_repository import InMemoryInterviewRepository, SQLiteInterviewRepository
from .interview.services.interview_service import InterviewService
from .interview.services.planner import Planner
from .interview.services.evaluator import Evaluator
from .interview.services.report_generator import ReportGenerator
from .interview.services.followup_generator import FollowupGenerator
from .interview.services.answer_coach import AnswerCoach
from .core.llm import GroqClient, LLMAuthError
from .interview.routers.interview import create_router
from .visualization.repositories.visualization_repository import VisualizationRepository
from .visualization.services.visualization_service import VisualizationService
from .visualization.services.ai_explainer import AIExplainer
from .visualization.services.summary_generator import SummaryGenerator
from .visualization.routers.visualization import create_router as create_visualization_router
from .analytics.repositories.analytics_repository import InMemoryAnalyticsRepository, SQLiteAnalyticsRepository
from .analytics.services.event_processor import EventProcessor
from .analytics.services.analytics_service import AnalyticsService
from .analytics.utils.event_publisher import EventPublisher
from .analytics.routers.analytics import create_router as create_analytics_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

repository = SQLiteInterviewRepository(settings.sqlite_path) if settings.repository.lower() == "sqlite" else InMemoryInterviewRepository()
llm = GroqClient.required_from_environment()
logger.info("AI mode: GROQ enabled model=%s", llm.model)
logger.info("Repository mode: %s", settings.repository.lower())
analytics_repository = SQLiteAnalyticsRepository(os.getenv("ANALYTICS_SQLITE_PATH", "./analytics.sqlite3")) if os.getenv("ANALYTICS_REPOSITORY", "memory").lower() == "sqlite" else InMemoryAnalyticsRepository()
analytics_event_processor = EventProcessor(analytics_repository)
analytics_event_publisher = EventPublisher(analytics_event_processor)
analytics_service = AnalyticsService(analytics_repository)
service = InterviewService(repository, planner=Planner(llm), evaluator=Evaluator(llm), followups=FollowupGenerator(llm), reports=ReportGenerator(llm), answer_coach=AnswerCoach(llm), event_publisher=analytics_event_publisher)
visualization_repository = VisualizationRepository()
visualization_service = VisualizationService(visualization_repository, explainer=AIExplainer(llm), summary=SummaryGenerator(llm), event_publisher=analytics_event_publisher)
app = FastAPI(title="Independent AI Technical Interview Engine", version="1.0.0")

@app.exception_handler(LLMAuthError)
async def groq_auth_error(request: Request, exc: LLMAuthError):
    return JSONResponse(status_code=502, content={"detail": str(exc), "provider": "groq"})

app.include_router(create_router(service))
app.include_router(create_visualization_router(visualization_service))
app.include_router(create_analytics_router(analytics_event_processor, analytics_service))

frontend_dir = Path(__file__).resolve().parent / "frontend"

@app.get("/health")
def health(): return {"status": "ok"}

app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
