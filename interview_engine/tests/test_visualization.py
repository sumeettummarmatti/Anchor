from fastapi.testclient import TestClient
from interview_engine.app.main import app

client = TestClient(app)
HEADERS = {"X-API-Key": "dev-api-key", "X-User-ID": "viz-user"}

def test_visualization_api_end_to_end():
    response = client.post("/visualization/trace", json={"language": "python", "source_code": "x = 1\nprint(x)"}, headers=HEADERS)
    assert response.status_code == 200
    trace_id = response.json()["trace_id"]
    trace = client.get(f"/visualization/{trace_id}", headers=HEADERS)
    assert trace.status_code == 200
    assert trace.json()["steps"]
    assert client.get(f"/visualization/{trace_id}/steps", headers=HEADERS).status_code == 200
    assert client.get(f"/visualization/{trace_id}/summary", headers=HEADERS).status_code == 200
    explanation = client.get(f"/visualization/{trace_id}/steps/1", headers=HEADERS)
    assert explanation.status_code == 200
    assert explanation.json()["annotation"]["explanation"]

def test_visualization_rejects_non_python_and_unknown_trace():
    response = client.post("/visualization/trace", json={"language": "java", "source_code": "int x = 1;"}, headers=HEADERS)
    assert response.status_code == 400
    assert client.get("/visualization/missing", headers=HEADERS).status_code == 404

def test_visualization_reports_rejected_imports_as_a_client_error():
    response = client.post(
        "/visualization/trace",
        json={"language": "python", "source_code": "import os"},
        headers=HEADERS,
    )

    assert response.status_code == 400
    assert "Imports" in response.json()["detail"]
