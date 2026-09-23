from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    assert client.get("/health/live").json() == {"status": "ok"}


def test_secret_change_is_flagged_and_redacted() -> None:
    response = client.post(
        "/api/v1/analyses",
        json={
            "changes": [
                {
                    "service": "billing",
                    "key": "API_TOKEN",
                    "before": "dont-leak-old",
                    "after": "dont-leak-new",
                }
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["findings"][0]["code"] == "sensitive-config-change"
    assert body["overall_severity"] == "high"
    assert "dont-leak" not in str(body)
    assert "[REDACTED]" in body["findings"][0]["evidence"][0]


def test_unknown_change_returns_review_finding() -> None:
    response = client.post(
        "/api/v1/analyses",
        json={"changes": [{"service": "web", "key": "THEME", "before": "dark", "after": "light"}]},
    )
    assert response.json()["findings"][0]["code"] == "review-required"
