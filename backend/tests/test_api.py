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


def test_registration_login_workspace_snapshots_and_tenant_isolation() -> None:
    from fastapi.testclient import TestClient

    client = TestClient(app)
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Northstar",
            "email": "owner@example.com",
            "password": "correct horse battery staple",
        },
    )
    assert registration.status_code == 201
    token = registration.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "OWNER@example.com", "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "owner@example.com", "password": "wrong password"}
        ).status_code
        == 401
    )

    service_response = client.post("/api/v1/services", headers=headers, json={"name": "billing"})
    assert service_response.status_code == 201
    service_id = service_response.json()["id"]
    assert client.get("/api/v1/services").status_code == 401
    downstream = client.post("/api/v1/services", headers=headers, json={"name": "ledger"}).json()
    edge = client.post(
        "/api/v1/dependencies",
        headers=headers,
        json={"source_id": service_id, "target_id": downstream["id"]},
    )
    assert edge.status_code == 201

    first = client.post(
        "/api/v1/snapshots",
        headers=headers,
        json={
            "service_id": service_id,
            "format": "json",
            "document": '{"database":{"pool_size":20,"password":"secret-one"}}',
        },
    )
    second = client.post(
        "/api/v1/snapshots",
        headers=headers,
        json={
            "service_id": service_id,
            "format": "json",
            "document": '{"database":{"pool_size":40,"password":"secret-two"}}',
        },
    )
    assert first.status_code == second.status_code == 201
    assert "secret-one" not in first.text
    assert first.json()["document"]["database"]["password"] == "[REDACTED]"

    diff = client.post(
        "/api/v1/analysis-runs/simulate",
        headers=headers,
        json={
            "before_snapshot_id": first.json()["id"],
            "after_snapshot_id": second.json()["id"],
            "context": {"max_replicas": 10, "database_max_connections": 1000},
        },
    )
    assert diff.status_code == 200
    assert "secret-one" not in diff.text and "secret-two" not in diff.text
    assert {finding["code"] for finding in diff.json()["analysis"]["findings"]} == {
        "sensitive-config-change",
        "capacity-change",
    }
    assert diff.json()["impact"]["impacted_services"] == ["ledger"]
    assert client.get("/api/v1/audit-events", headers=headers).json()

    other = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Other tenant",
            "email": "other@example.com",
            "password": "another correct horse battery",
        },
    )
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}
    hidden = client.get(f"/api/v1/snapshots?service_id={service_id}", headers=other_headers)
    assert hidden.status_code == 404


def test_protected_routes_reject_invalid_bearer_token() -> None:
    from fastapi.testclient import TestClient

    response = TestClient(app).get(
        "/api/v1/services", headers={"Authorization": "Bearer invalid-token"}
    )
    assert response.status_code == 401


def test_tenant_saved_dependency_graph_can_be_traversed() -> None:
    client = TestClient(app)
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "organization_name": "Graph tenant",
            "email": "graph@example.com",
            "password": "graph workspace password",
        },
    )
    headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}
    api_service = client.post("/api/v1/services", headers=headers, json={"name": "api"}).json()
    db_service = client.post("/api/v1/services", headers=headers, json={"name": "database"}).json()
    edge = client.post(
        "/api/v1/dependencies",
        headers=headers,
        json={"source_id": api_service["id"], "target_id": db_service["id"]},
    )
    assert edge.status_code == 201
    assert len(client.get("/api/v1/dependencies", headers=headers).json()) == 1
    impact = client.post(
        "/api/v1/impact/workspace",
        headers=headers,
        json={"changed_services": [api_service["id"]]},
    )
    assert impact.status_code == 200
    assert impact.json()["paths"] == [{"service": "database", "path": ["api", "database"]}]


def test_readiness_request_id_and_metrics_endpoint() -> None:
    from fastapi.testclient import TestClient

    client = TestClient(app)
    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.headers.get("x-request-id")
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "causora_http_requests_total" in metrics.text


def test_database_budget_rule_explains_excess_and_safe_options() -> None:
    response = client.post(
        "/api/v1/analyses",
        json={
            "changes": [
                {"service": "checkout", "key": "max_replicas", "before": 10, "after": 30},
                {"service": "checkout", "key": "database.pool_size", "before": 20, "after": 50},
            ],
            "context": {"database_max_connections": 1000, "database_safety_margin": 0.1},
        },
    )
    assert response.status_code == 200
    finding = next(
        item
        for item in response.json()["findings"]
        if item["code"] == "database-connection-budget-exceeded"
    )
    assert finding["severity"] == "high"
    assert "1500" in " ".join(finding["evidence"])
    assert len(finding["remediation_options"]) == 3
    assert all(option["requires_approval"] for option in finding["remediation_options"])


def test_non_finite_capacity_context_does_not_create_numeric_risk() -> None:
    response = client.post(
        "/api/v1/analyses",
        json={
            "changes": [{"service": "api", "key": "pool_size", "before": 10, "after": 50}],
            "context": {"max_replicas": 20, "database_max_connections": "NaN"},
        },
    )
    codes = {finding["code"] for finding in response.json()["findings"]}
    assert "database-connection-budget-exceeded" not in codes
