from fastapi.testclient import TestClient
from interview_engine.app.main import app

client = TestClient(app)
HEADERS = {"X-API-Key": "dev-api-key", "X-User-ID": "u-api"}

def payload():
    return {"context": {"submission_id": "s-api", "user_id": "u-api", "problem_title": "Reverse String", "problem_description": "Reverse a string", "language": "python", "code": "return s[::-1]", "execution_result": "passed", "hint_count": 0, "attempt_count": 1, "difficulty": "Easy"}}

def test_http_contract():
    started = client.post("/interview/start", json=payload(), headers=HEADERS)
    assert started.status_code == 200
    interview_id = started.json()["interview_id"]
    answered = client.post(f"/interview/{interview_id}/answer", json={"answer": "O(n) time and O(1) space; empty strings are valid."}, headers=HEADERS)
    assert answered.status_code == 200
    assert "evaluation" in answered.json()
    assert client.get(f"/interview/{interview_id}", headers=HEADERS).status_code == 200

def test_invalid_interview_is_404():
    assert client.get("/interview/missing", headers=HEADERS).status_code == 404

def test_interview_requires_credentials():
    assert client.post("/interview/start", json=payload()).status_code == 401

def test_interview_owner_check():
    started = client.post("/interview/start", json=payload(), headers=HEADERS)
    interview_id = started.json()["interview_id"]
    other_user = {"X-API-Key": "dev-api-key", "X-User-ID": "different-user"}
    assert client.get(f"/interview/{interview_id}", headers=other_user).status_code == 403
    assert client.post(f"/interview/{interview_id}/answer", json={"answer": "not mine"}, headers=other_user).status_code == 403

def test_visualization_requires_credentials():
    response = client.post("/visualization/trace", json={"language": "python", "source_code": "print(1)"})
    assert response.status_code == 401
