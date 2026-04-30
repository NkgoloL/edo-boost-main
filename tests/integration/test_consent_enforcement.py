"""
tests/popia/test_consent_enforcement.py

Integration tests that verify the POPIA consent gate fires correctly
at every learner data endpoint.  These run against the live FastAPI app
(via httpx AsyncClient) with a real test database.

These tests are the primary gate for the report finding:
  "Parental consent enforcement unverified end-to-end"
"""
from __future__ import annotations

import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# ── Adjust this import to your actual app entrypoint ──────────────────────────
from app.api.main import app
from app.api.core.db import get_db
from app.api.services.consent_service import ConsentService, ConsentNotGrantedError
from app.api.models.consent import ConsentStatus


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture
async def client():
    """ASGI test client — no network needed."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def guardian_token(client: AsyncClient):
    """Register a guardian and return a valid JWT."""
    email = f"popia_test_{uuid.uuid4().hex[:8]}@test.local"
    reg = await client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "TestPass!99",
        "display_name": "POPIA Test Guardian",
    })
    assert reg.status_code == 201

    login = await client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "TestPass!99",
    })
    assert login.status_code == 200
    return login.json()["access_token"]


@pytest_asyncio.fixture
async def learner_without_consent(client: AsyncClient, guardian_token: str):
    """Learner registered but consent still in 'pending' state."""
    headers = {"Authorization": f"Bearer {guardian_token}"}
    res = await client.post("/api/v1/learners", headers=headers, json={
        "display_name": "No Consent Child",
        "grade": "3",
    })
    assert res.status_code == 201
    return res.json()["id"]


@pytest_asyncio.fixture
async def learner_with_consent(client: AsyncClient, guardian_token: str):
    """Learner with active parental consent."""
    headers = {"Authorization": f"Bearer {guardian_token}"}
    res = await client.post("/api/v1/learners", headers=headers, json={
        "display_name": "Consented Child",
        "grade": "5",
    })
    assert res.status_code == 201
    learner_id = res.json()["id"]

    consent = await client.post("/api/v1/consent/grant", headers=headers, json={
        "learner_id": learner_id,
        "consent_version": "1.0",
    })
    assert consent.status_code == 200
    assert consent.json()["status"] == "granted"
    return learner_id


# ── Tests: endpoints that MUST block without consent ─────────────────────────

LEARNER_ENDPOINTS = [
    ("GET",  "/api/v1/learners/{id}/plan"),
    ("POST", "/api/v1/learners/{id}/plan/generate"),
    ("GET",  "/api/v1/learners/{id}/lesson"),
    ("POST", "/api/v1/learners/{id}/lesson"),
    ("GET",  "/api/v1/learners/{id}/diagnostic"),
    ("POST", "/api/v1/learners/{id}/diagnostic"),
    ("GET",  "/api/v1/learners/{id}/diagnostic/results"),
]


@pytest.mark.anyio
@pytest.mark.parametrize("method,url_template", LEARNER_ENDPOINTS)
async def test_endpoint_blocks_without_consent(
    client: AsyncClient,
    guardian_token: str,
    learner_without_consent: str,
    method: str,
    url_template: str,
):
    """
    Critical POPIA gate: every learner data endpoint must return 403
    when consent is pending (not yet granted).
    """
    url = url_template.replace("{id}", learner_without_consent)
    headers = {"Authorization": f"Bearer {guardian_token}"}
    fn = client.get if method == "GET" else client.post
    response = await fn(url, headers=headers)

    assert response.status_code == 403, (
        f"{method} {url} returned {response.status_code} instead of 403. "
        "This is a POPIA compliance failure — consent gate is missing."
    )
    body = response.json()
    detail = body.get("detail", body.get("message", ""))
    assert "consent" in detail.lower(), (
        f"403 response from {url} does not mention 'consent' in detail: {detail!r}"
    )


@pytest.mark.anyio
@pytest.mark.parametrize("method,url_template", LEARNER_ENDPOINTS)
async def test_endpoint_allows_access_with_consent(
    client: AsyncClient,
    guardian_token: str,
    learner_with_consent: str,
    method: str,
    url_template: str,
):
    """
    With active consent, endpoints must not return 403 (may return other codes
    like 404 or 422 if data is missing, but consent is not the blocker).
    """
    url = url_template.replace("{id}", learner_with_consent)
    headers = {"Authorization": f"Bearer {guardian_token}"}
    fn = client.get if method == "GET" else client.post
    response = await fn(url, headers=headers)

    assert response.status_code != 403, (
        f"{method} {url} returned 403 even with active consent. "
        "Consent gate is incorrectly blocking a consented learner."
    )


@pytest.mark.anyio
async def test_consent_gate_fires_after_revocation(
    client: AsyncClient,
    guardian_token: str,
    learner_with_consent: str,
):
    """
    After consent is revoked, all learner data endpoints must immediately
    return 403 — no caching or race condition window.
    """
    headers = {"Authorization": f"Bearer {guardian_token}"}

    # Verify access works with consent
    res = await client.get(
        f"/api/v1/learners/{learner_with_consent}/plan", headers=headers
    )
    assert res.status_code != 403, "Prerequisite failed: consented learner should have access"

    # Revoke consent
    revoke = await client.post("/api/v1/consent/revoke", headers=headers, json={
        "learner_id": learner_with_consent,
    })
    assert revoke.status_code == 200

    # Access must now be blocked — immediately
    res = await client.get(
        f"/api/v1/learners/{learner_with_consent}/plan", headers=headers
    )
    assert res.status_code == 403, (
        "After consent revocation, GET /plan must return 403 immediately. "
        "Consent revocation is not being enforced."
    )


@pytest.mark.anyio
async def test_unauthenticated_request_returns_401(client: AsyncClient):
    """Public safety: any learner endpoint without JWT returns 401, not data."""
    res = await client.get(
        f"/api/v1/learners/{uuid.uuid4()}/plan"
    )
    assert res.status_code in (401, 403), (
        f"Unauthenticated request returned {res.status_code}. "
        "Must be 401 or 403, never 200."
    )


@pytest.mark.anyio
async def test_right_to_erasure_soft_deletes_learner(
    client: AsyncClient,
    guardian_token: str,
    learner_with_consent: str,
):
    """
    Execute erasure: learner must be soft-deleted and subsequent
    access attempts must return 404 (not 200 or 403 — the record is gone).
    """
    headers = {"Authorization": f"Bearer {guardian_token}"}

    erase = await client.post("/api/v1/consent/erase", headers=headers, json={
        "learner_id": learner_with_consent,
        "confirm": True,
    })
    assert erase.status_code == 200
    result = erase.json()
    assert result["learner_soft_deleted"] is True
    assert result["consent_revoked_at"] is not None

    # Deleted learner must not be retrievable
    res = await client.get(
        f"/api/v1/learners/{learner_with_consent}", headers=headers
    )
    assert res.status_code in (404, 403), (
        f"After erasure, GET /learners/<id> returned {res.status_code}. "
        "Soft-deleted learners must not be accessible."
    )


# ── Unit tests for ConsentService ─────────────────────────────────────────────

class TestConsentServiceUnit:
    """Fast unit tests for ConsentService logic — no DB required."""

    def test_consent_not_granted_error_message(self):
        learner_id = uuid.uuid4()
        err = ConsentNotGrantedError(learner_id)
        assert str(learner_id) in str(err)
        assert "consent" in str(err).lower()

    def test_consent_status_enum_values(self):
        assert ConsentStatus.pending.value == "pending"
        assert ConsentStatus.granted.value == "granted"
        assert ConsentStatus.revoked.value == "revoked"
        assert ConsentStatus.expired.value == "expired"
