from fastapi import APIRouter, Depends, HTTPException, Query, Response

from ...core.security import get_authenticated_user
from ..schemas.event import AnalyticsEventResponse, EventIngestRequest
from ..services.analytics_service import AnalyticsService
from ..services.event_processor import EventProcessor
from ..services.export_service import ExportService


def create_router(processor: EventProcessor, analytics_service: AnalyticsService = None):
    router = APIRouter(prefix="/analytics", tags=["analytics"])
    auth = Depends(get_authenticated_user)
    analytics_service = analytics_service or AnalyticsService(processor.repository)
    export_service = ExportService(analytics_service)

    @router.post("/events", response_model=AnalyticsEventResponse, status_code=201)
    def ingest_event(request: EventIngestRequest, current_user: str = auth):
        try:
            event = processor.process(
                event_type=request.event_type,
                source=request.source,
                user_id=current_user,
                metadata=request.metadata,
                timestamp=request.timestamp,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return AnalyticsEventResponse(
            id=event.id,
            user_id=event.user_id,
            event_type=event.event_type,
            source=event.source,
            timestamp=event.timestamp,
            metadata=event.metadata,
        )

    @router.get("/me")
    def get_overview(current_user: str = auth):
        return analytics_service.overview(current_user)

    @router.get("/me/weekly")
    def get_weekly(current_user: str = auth):
        return analytics_service.period(current_user, 7)

    @router.get("/me/monthly")
    def get_monthly(current_user: str = auth):
        return analytics_service.period(current_user, 30)

    @router.get("/me/progress")
    def get_progress(current_user: str = auth):
        return analytics_service.overview(current_user)["progress"]

    @router.get("/me/interviews")
    def get_interviews(current_user: str = auth):
        items = analytics_service.history(current_user, "INTERVIEW_")
        items.extend(analytics_service.history(current_user, "QUESTION_"))
        items.sort(key=lambda item: item["timestamp"], reverse=True)
        return {"items": items}

    @router.get("/me/executions")
    def get_executions(current_user: str = auth):
        items = analytics_service.history(current_user, "TRACE_")
        items.extend(analytics_service.history(current_user, "EXECUTION_"))
        items.sort(key=lambda item: item["timestamp"], reverse=True)
        return {"items": items}

    @router.get("/me/export")
    def export_analytics(format: str = Query(default="json"), current_user: str = auth):
        normalized = format.lower()
        if normalized == "json":
            return Response(
                content=export_service.json_bytes(current_user),
                media_type="application/json",
                headers={"Content-Disposition": 'attachment; filename="analytics-export.json"'},
            )
        if normalized == "csv":
            return Response(
                content=export_service.csv_bytes(current_user),
                media_type="text/csv",
                headers={"Content-Disposition": 'attachment; filename="analytics-export.csv"'},
            )
        raise HTTPException(status_code=400, detail="format must be csv or json")

    return router
