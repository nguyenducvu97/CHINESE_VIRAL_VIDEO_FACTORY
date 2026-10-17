"""Unit tests for Control Center REST API endpoints."""

import pytest
from fastapi.testclient import TestClient

from src.control_center.app import app
from src.core.models import AuthorInfo, InteractionMetrics, StandardVideoItem
from src.control_center.app import dedup_store


@pytest.fixture
def client():
    return TestClient(app)


def test_api_health(client):
    """Verify health endpoint reports healthy status and port 3080."""
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["port"] == 3080
    assert data["isolated_namespace"] == "cvvf"


def test_api_budget(client):
    """Verify strict zero-dollar budget cap and circuit breaker."""
    res = client.get("/api/budget")
    assert res.status_code == 200
    data = res.json()
    assert data["daily_limit_usd"] == 0.0
    assert data["spent_today_usd"] == 0.0
    assert data["circuit_breaker_active"] is False


def test_api_list_videos(client):
    """Verify listing videos returns tracked items with viral scoring."""
    # Seed sample item
    item = StandardVideoItem(
        dedup_key="bilibili:BV_API_TEST",
        source_platform="bilibili",
        source_item_id="BV_API_TEST",
        canonical_url="https://example.com/BV_API_TEST",
        title="API测试视频",
        author=AuthorInfo(id="author_api", name="Creator API"),
        metrics=InteractionMetrics(views=120000, likes=9000, shares=1000, comments=400),
    )
    dedup_store.add(item)

    res = client.get("/api/videos")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    found = next((v for v in data["videos"] if v["dedup_key"] == "bilibili:BV_API_TEST"), None)
    assert found is not None
    assert "scored" in found
    assert found["scored"]["measured_viral_score"] is not None


def test_api_human_approval_gate(client):
    """Verify human approval requirement before full pipeline processing."""
    item = StandardVideoItem(
        dedup_key="bilibili:BV_GATE_TEST",
        source_platform="bilibili",
        source_item_id="BV_GATE_TEST",
        canonical_url="https://example.com/BV_GATE_TEST",
        title="Gate Test Video",
        author=AuthorInfo(id="author_gate", name="Creator Gate"),
        metrics=InteractionMetrics(views=50000, likes=4000),
    )
    dedup_store.add(item)

    # 1. Processing without approval MUST be rejected (HTTP 400)
    process_res = client.post("/api/videos/bilibili:BV_GATE_TEST/process-all")
    assert process_res.status_code == 400
    assert "Human review required" in process_res.json()["detail"]

    # 2. Approve video rights explicitly
    appr_res = client.post("/api/videos/bilibili:BV_GATE_TEST/approve")
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "success"

    # Verify status updated
    detail_res = client.get("/api/videos/bilibili:BV_GATE_TEST")
    assert detail_res.json()["video"]["rights_status"] == "APPROVED_BY_USER"


def test_api_audit_logs(client):
    """Verify audit log captures operations."""
    res = client.get("/api/audit-logs")
    assert res.status_code == 200
    logs = res.json()
    assert isinstance(logs, list)
    assert len(logs) > 0
    assert any(log["action"] == "RIGHTS_APPROVAL" for log in logs)
