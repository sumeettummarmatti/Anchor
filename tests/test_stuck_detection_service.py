import uuid
from datetime import UTC, datetime

from httpx import AsyncClient

from app.models.execution import ExecutionRun
from app.models.hint_event import HintEvent
from app.services.stuck_detection_service import compute_stuck_score
from tests.test_projects import token_for


def test_compute_stuck_score_pure():
    now = datetime.now(UTC)
    
    # 1. No events -> not stuck
    score = compute_stuck_score([], [], [], now)
    assert not score.is_stuck
    assert score.score == 0.0

    # 2. 3 consecutive failed runs -> score is 0.25 -> stuck!
    runs = [
        ExecutionRun(id=uuid.uuid4(), status="failed", created_at=now) for _ in range(3)
    ]
    # Inactivity = 0, hints = 0, repeated edits = 0
    # Average = 0.25 >= 0.25 (Threshold lowered)
    score = compute_stuck_score([{"typing_pause_ms": 0}], runs, [], now)
    assert score.is_stuck
    assert score.signals["consecutive_failures"] == 1.0
    
    # 3. 3 failed runs + inactivity
    score = compute_stuck_score([{"typing_pause_ms": 65_000}], runs, [], now)
    assert score.is_stuck  # (1.0 + 1.0)/4 = 0.5 >= 0.4
    
    # 4. Repeated edits + 1 failed run
    runs = [ExecutionRun(id=uuid.uuid4(), status="failed", created_at=now)]
    events = [
        {"current_function": "main", "open_file": "app.py", "typing_pause_ms": 1000}
        for _ in range(5)
    ]
    score = compute_stuck_score(events, runs, [], now)
    # Failures = 0.33, Edits = 1.0, Inactivity = 1000/60000 -> 0.016. Avg = ~1.34/4 = 0.33 >= 0.25
    assert score.is_stuck
    assert score.signals["repeated_edits"] == 1.0
    assert score.signals["consecutive_failures"] == 0.333
    
    # 5. Hints + Inactivity + Failures
    runs = [ExecutionRun(id=uuid.uuid4(), status="failed", created_at=now)]
    hints = [HintEvent(id=uuid.uuid4(), session_id=uuid.uuid4(), created_at=now)]
    # Hint rate = 1.0, failures = 0.333, inactivity = 1.0
    # Avg = 2.333 / 4 = 0.58
    score = compute_stuck_score([{"typing_pause_ms": 70_000}], runs, hints, now)
    assert score.is_stuck


async def test_get_stuck_score_endpoint(client: AsyncClient) -> None:
    tokens = await token_for(client, "stuck@example.com")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    
    project = await client.post(
        "/projects", headers=headers, json={"name": "Stuck Check", "language": "python"}
    )
    assert project.status_code == 201
    project_id = project.json()["id"]

    session = await client.post(
        "/sessions", headers=headers, json={"project_id": project_id}
    )
    assert session.status_code == 201
    session_id = session.json()["id"]

    # At start, score should be 0 and not stuck
    res = await client.get(f"/sessions/{session_id}/stuck-score", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["is_stuck"] is False
    assert data["score"] == 0.0

    # Submit a batch of events with huge pause to simulate inactivity
    events = [{"typing_pause_ms": 120_000, "file_switches": 0, "current_code": "x"}]
    res = await client.post(
        f"/sessions/{session_id}/events", headers=headers, json={"events": events}
    )
    assert res.status_code == 200

    # Also record some failures via execution
    run_req = {
        "language": "python", 
        "code": "def foo(): pass", 
        "session_id": session_id, 
        "version": "3.10.0"
    }
    for _ in range(4):
        await client.post("/execution/run", headers=headers, json=run_req)

    # Re-fetch score
    res = await client.get(f"/sessions/{session_id}/stuck-score", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "score" in data
    assert "is_stuck" in data
    # Inactivity signal should be 1.0 (120,000 / 60,000) -> min(2.0, 1.0) = 1.0
    # Average = 1.0 / 4 = 0.25 -> is_stuck = False
    assert data["signals"]["inactivity"] == 1.0
