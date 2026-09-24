"""Tests: FastAPI backend endpoints - integration + E2E workflow tests."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(engine, monkeypatch):
    """Build the API app wired to the test engine rather than the default one."""
    import src.api.main as api_main
    monkeypatch.setattr(api_main, "ENGINE", engine)
    return TestClient(api_main.app)


class TestHealthAndDocs:
    def test_health_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_openapi_schema_available(self, client):
        r = client.get("/openapi.json")
        assert r.status_code == 200


class TestAnalyticsEndpoints:
    @pytest.mark.parametrize("path", [
        "/api/analytics/spend",
        "/api/analytics/suppliers",
        "/api/analytics/kpis",
        "/api/analytics/budget-utilisation",
    ])
    def test_endpoint_returns_200(self, client, path):
        r = client.get(path)
        assert r.status_code == 200


class TestAIEndpoints:
    @pytest.mark.parametrize("path", [
        "/api/ai/maverick-spend",
        "/api/ai/maverick-spend/validation",
        "/api/ai/consolidation",
        "/api/ai/savings",
        "/api/ai/narrative",
    ])
    def test_endpoint_returns_200(self, client, path):
        r = client.get(path)
        assert r.status_code == 200

    def test_narrative_has_fallback_option(self, client):
        r = client.get("/api/ai/narrative", params={"force_fallback": True})
        assert r.status_code == 200
        assert r.json()["source"] == "rule_based"


class TestRequisitionWorkflowEndToEnd:
    """The full requisition lifecycle: create -> validate -> approve."""

    def test_full_lifecycle(self, client):
        create_resp = client.post("/api/requisitions", json={
            "requester": "QA Suite",
            "department": "IT",
            "category": "IT Hardware",
            "requested_supplier_id": "SUP0001",
            "estimated_amount": 42000,
            "justification": "Automated E2E test requisition",
        })
        assert create_resp.status_code == 200
        req_id = create_resp.json()["requisition_id"]
        assert create_resp.json()["status"] == "PENDING"

        get_resp = client.get(f"/api/requisitions/{req_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["requisition_id"] == req_id

        validate_resp = client.get(f"/api/requisitions/{req_id}/validate")
        assert validate_resp.status_code == 200
        assert "recommendation" in validate_resp.json()

        decide_resp = client.post(f"/api/requisitions/{req_id}/decide", json={
            "approver": "QA Reviewer",
            "decision": "APPROVED",
        })
        assert decide_resp.status_code == 200
        assert decide_resp.json()["status"] == "APPROVED"

        final = client.get(f"/api/requisitions/{req_id}")
        assert final.json()["status"] == "APPROVED"

    def test_invalid_decision_rejected(self, client):
        create_resp = client.post("/api/requisitions", json={
            "requester": "QA Suite", "department": "IT", "category": "IT Hardware",
            "estimated_amount": 1000, "justification": "invalid decision test",
        })
        req_id = create_resp.json()["requisition_id"]
        r = client.post(f"/api/requisitions/{req_id}/decide", json={
            "approver": "QA", "decision": "MAYBE",
        })
        assert r.status_code == 400

    def test_nonexistent_requisition_404s(self, client):
        r = client.get("/api/requisitions/REQ99999")
        assert r.status_code == 404


class TestGovernanceEndpoints:
    def test_catalogue_returns_assets(self, client):
        r = client.get("/api/governance/catalogue")
        assert r.status_code == 200
        assert len(r.json()) > 0

    def test_audit_log_returns_entries(self, client):
        r = client.get("/api/governance/audit-log")
        assert r.status_code == 200
