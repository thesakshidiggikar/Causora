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


def test_dependency_impact_returns_shortest_paths_through_cycles() -> None:
    response = client.post(
        "/api/v1/impact",
        json={
            "services": ["api", "auth", "database", "queue"],
            "changed_services": ["api"],
            "dependencies": [
                {"source": "api", "target": "auth"},
                {"source": "auth", "target": "database"},
                {"source": "database", "target": "api"},
                {"source": "api", "target": "queue"},
                {"source": "auth", "target": "queue"},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body["impacted_services"]) == {"auth", "database", "queue"}
    paths = {item["service"]: item["path"] for item in body["paths"]}
    assert paths["queue"] == ["api", "queue"]
    assert paths["database"] == ["api", "auth", "database"]
    assert body["mode"] == "bounded_breadth_first_traversal"


def test_dependency_impact_rejects_unknown_changed_service() -> None:
    response = client.post(
        "/api/v1/impact",
        json={"services": ["api"], "changed_services": ["missing"], "dependencies": []},
    )
    assert response.status_code == 422
