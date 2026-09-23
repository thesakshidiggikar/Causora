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


def test_yaml_config_diff_creates_analysis() -> None:
    response = client.post(
        "/api/v1/config-diffs",
        json={
            "service": "orders",
            "format": "yaml",
            "before": "pool:\n  size: 10\napi_token: previous-secret\n",
            "after": "pool:\n  size: 40\napi_token: next-secret\n",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert [change["key"] for change in body["changes"]] == ["api_token", "pool.size"]
    assert "previous-secret" not in response.text
    assert "next-secret" not in response.text
    assert body["changes"][0]["before"] == "[REDACTED]"
    assert body["changes"][0]["after"] == "[REDACTED]"
    assert {finding["code"] for finding in body["analysis"]["findings"]} == {
        "sensitive-config-change",
        "capacity-change",
    }


def test_invalid_yaml_is_rejected_without_parser_details() -> None:
    response = client.post(
        "/api/v1/config-diffs",
        json={"service": "orders", "before": "a: [", "after": "{}"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Configuration document is invalid."
