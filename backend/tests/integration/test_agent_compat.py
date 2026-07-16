"""
End-to-end coverage for the three endpoints the real .NET agent calls
(ElevateGate.Infrastructure.Api.HttpApprovalApiClient), at its actual paths, wire casing, and
device-bearer-token auth scheme - see app/api/v1/agent_compat.py and docs/API_CONTRACT.md.
"""

import base64
import os
import uuid
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core.security import create_access_token
from app.core.signing import build_canonical_payload
from tests.factories import (
    create_admin,
    create_app_allowlist_entry,
    create_device,
    create_device_group,
    create_elevation_request,
)

_ENROLLMENT_KEY = os.environ["ENROLLMENT_KEY"]
_TEST_PRIVATE_KEY = Ed25519PrivateKey.from_private_bytes(
    base64.b64decode(os.environ["ED25519_PRIVATE_KEY_B64"])
)
_TEST_PUBLIC_KEY = _TEST_PRIVATE_KEY.public_key()


def _admin_auth_header(admin) -> dict:
    token = create_access_token(subject=str(admin.id), role=admin.role.value)
    return {"Authorization": f"Bearer {token}"}


def _device_bearer_header(device, secret: str) -> dict:
    return {"Authorization": f"Bearer {device.device_uuid}.{secret}"}


def _approval_request_body(*, request_id: uuid.UUID, device_id: uuid.UUID, sha256: str = "ab" * 32) -> dict:
    return {
        "requestId": str(request_id),
        "deviceId": str(device_id),
        "file": {
            "fileName": "installer.exe",
            "fullPath": r"C:\Temp\installer.exe",
            "sizeBytes": 2048,
            "fileVersion": "1.2.3.4",
            "sha256Hex": sha256,
        },
        "signature": {
            "trustStatus": "trusted",
            "publisherCommonName": "Contoso Ltd.",
            "certificateThumbprint": "AABBCC",
        },
        "reason": "Need this installed for a printer driver.",
        "requestedAtUtc": datetime.now(timezone.utc).isoformat(),
    }


async def test_agent_enroll_creates_device_and_returns_bearer_token(client, db_session):
    device_id = uuid.uuid4()
    response = await client.post(
        "/api/v1/enroll",
        headers={"X-Enrollment-Key": _ENROLLMENT_KEY},
        json={
            "deviceId": str(device_id),
            "machineName": "WKS-042",
            "operatingSystemVersion": "Windows 11 24H2",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert "bearerToken" in body and body["bearerToken"].startswith(str(device_id))
    assert "enrolledAtUtc" in body

    from app.repositories import device_repository

    device = await device_repository.get_by_uuid(db_session, device_id)
    assert device is not None
    assert device.hostname == "WKS-042"
    assert device.operating_system == "Windows 11 24H2"
    assert device.agent_version is None


async def test_agent_enroll_requires_enrollment_key(client):
    response = await client.post(
        "/api/v1/enroll",
        json={
            "deviceId": str(uuid.uuid4()),
            "machineName": "WKS-042",
            "operatingSystemVersion": "Windows 11 24H2",
        },
    )
    assert response.status_code in (401, 422)


async def test_agent_enroll_rejects_duplicate_device(client, db_session):
    device, _ = await create_device(db_session)
    response = await client.post(
        "/api/v1/enroll",
        headers={"X-Enrollment-Key": _ENROLLMENT_KEY},
        json={
            "deviceId": str(device.device_uuid),
            "machineName": "WKS-042",
            "operatingSystemVersion": "Windows 11 24H2",
        },
    )
    assert response.status_code == 409


async def test_agent_submit_request_preserves_client_supplied_request_id(client, db_session):
    device, secret = await create_device(db_session)
    request_id = uuid.uuid4()

    response = await client.post(
        "/api/v1/requests",
        headers=_device_bearer_header(device, secret),
        json=_approval_request_body(request_id=request_id, device_id=device.device_uuid),
    )

    assert response.status_code == 201

    from app.repositories import elevation_request_repository

    stored = await elevation_request_repository.get_by_uuid(db_session, request_id)
    assert stored is not None
    assert stored.username is None
    assert stored.filename == "installer.exe"
    assert stored.publisher == "Contoso Ltd."


async def test_agent_submit_request_maps_hash_mismatch_camelcase_enum(client, db_session):
    device, secret = await create_device(db_session)
    request_id = uuid.uuid4()
    body = _approval_request_body(request_id=request_id, device_id=device.device_uuid)
    body["signature"]["trustStatus"] = "hashMismatch"

    response = await client.post(
        "/api/v1/requests", headers=_device_bearer_header(device, secret), json=body
    )
    assert response.status_code == 201

    from app.models.enums import SignatureStatus
    from app.repositories import elevation_request_repository

    stored = await elevation_request_repository.get_by_uuid(db_session, request_id)
    assert stored.signature_status == SignatureStatus.HASH_MISMATCH


async def test_agent_submit_request_rejects_device_id_mismatch(client, db_session):
    device, secret = await create_device(db_session)
    other_device_id = uuid.uuid4()

    response = await client.post(
        "/api/v1/requests",
        headers=_device_bearer_header(device, secret),
        json=_approval_request_body(request_id=uuid.uuid4(), device_id=other_device_id),
    )
    assert response.status_code == 400


async def test_agent_submit_request_requires_bearer_auth(client):
    response = await client.post(
        "/api/v1/requests",
        json=_approval_request_body(request_id=uuid.uuid4(), device_id=uuid.uuid4()),
    )
    assert response.status_code == 401


async def test_agent_submit_request_rejects_malformed_bearer_token(client, db_session):
    device, _secret = await create_device(db_session)
    response = await client.post(
        "/api/v1/requests",
        headers={"Authorization": "Bearer not-a-valid-token-format"},
        json=_approval_request_body(request_id=uuid.uuid4(), device_id=device.device_uuid),
    )
    assert response.status_code == 401


async def test_agent_decisions_excludes_pending(client, db_session):
    device, secret = await create_device(db_session)
    await create_elevation_request(db_session, device=device)

    response = await client.get(
        f"/api/v1/devices/{device.device_uuid}/decisions",
        headers=_device_bearer_header(device, secret),
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_agent_decisions_rejects_path_device_id_mismatch(client, db_session):
    device_a, secret_a = await create_device(db_session)
    device_b, _secret_b = await create_device(db_session)

    response = await client.get(
        f"/api/v1/devices/{device_b.device_uuid}/decisions",
        headers=_device_bearer_header(device_a, secret_a),
    )
    assert response.status_code == 403


async def test_agent_decisions_since_accepts_dotnet_round_trip_format(client, db_session):
    """A real .NET agent calls PollDecisionsAsync with `since` formatted via
    `sinceUtc.ToUniversalTime().ToString("O")` - e.g. 7 fractional digits and a numeric "+00:00"
    offset, never "Z". This must parse cleanly, not 422, or the agent could never poll at all."""
    device, secret = await create_device(db_session)

    response = await client.get(
        f"/api/v1/devices/{device.device_uuid}/decisions",
        params={"since": "2026-07-06T13:07:11.1234567+00:00"},
        headers=_device_bearer_header(device, secret),
    )
    assert response.status_code == 200


async def test_agent_decisions_approved_token_is_genuinely_ed25519_verifiable(client, db_session):
    """The whole point of this reconciliation: an approval issued through the ordinary
    admin-approve flow must carry a signature that verifies against the exact 5-field payload
    the real .NET CanonicalApprovalPayload.Build/ApprovalTokenValidator would reconstruct from
    this wire response - not just "some" signature."""
    device, secret = await create_device(db_session)
    admin, _ = await create_admin(db_session)
    request_id = uuid.uuid4()

    await client.post(
        "/api/v1/requests",
        headers=_device_bearer_header(device, secret),
        json=_approval_request_body(request_id=request_id, device_id=device.device_uuid, sha256="cd" * 32),
    )

    from app.repositories import elevation_request_repository

    stored = await elevation_request_repository.get_by_uuid(db_session, request_id)
    await client.post(
        f"/api/v1/elevation-requests/{stored.id}/approve", headers=_admin_auth_header(admin)
    )

    response = await client.get(
        f"/api/v1/devices/{device.device_uuid}/decisions",
        headers=_device_bearer_header(device, secret),
    )
    decisions = response.json()
    assert len(decisions) == 1
    decision = decisions[0]
    assert decision["requestId"] == str(request_id)
    assert decision["status"] == "approved"

    token = decision["token"]
    assert token["deviceId"] == str(device.device_uuid)
    assert token["requestId"] == str(request_id)
    assert token["sha256Hex"] == "cd" * 32
    assert token["nonce"]

    expires_at = datetime.fromisoformat(token["expiresAtUtc"].replace("Z", "+00:00"))
    rebuilt_payload = build_canonical_payload(
        device_uuid=token["deviceId"],
        request_uuid=token["requestId"],
        sha256=token["sha256Hex"],
        expires_at=expires_at,
        nonce=token["nonce"],
    )
    signature = base64.b64decode(token["signature"])

    # Does not raise => the exact bytes an agent would reconstruct from this JSON response
    # verify against the backend's real signing key. This is the actual interop guarantee.
    _TEST_PUBLIC_KEY.verify(signature, rebuilt_payload)


async def test_agent_decisions_denied_has_no_token(client, db_session):
    device, secret = await create_device(db_session)
    admin, _ = await create_admin(db_session)
    request_id = uuid.uuid4()

    await client.post(
        "/api/v1/requests",
        headers=_device_bearer_header(device, secret),
        json=_approval_request_body(request_id=request_id, device_id=device.device_uuid),
    )
    from app.repositories import elevation_request_repository

    stored = await elevation_request_repository.get_by_uuid(db_session, request_id)
    await client.post(
        f"/api/v1/elevation-requests/{stored.id}/deny", headers=_admin_auth_header(admin)
    )

    response = await client.get(
        f"/api/v1/devices/{device.device_uuid}/decisions",
        headers=_device_bearer_header(device, secret),
    )
    decisions = response.json()
    assert len(decisions) == 1
    assert decisions[0]["status"] == "denied"
    assert decisions[0]["token"] is None


# --- Heartbeat / telemetry / remote update -----------------------------------------------------


async def test_agent_heartbeat_records_telemetry_and_version(client, db_session):
    device, secret = await create_device(db_session, agent_version="1.0.2")

    response = await client.post(
        "/api/v1/heartbeat",
        headers=_device_bearer_header(device, secret),
        json={
            "agentVersion": "1.0.3",
            "diskTotalBytes": 500_000_000_000,
            "diskFreeBytes": 100_000_000_000,
            "ramTotalBytes": 16_000_000_000,
            "ramUsedBytes": 8_000_000_000,
        },
    )
    assert response.status_code == 200
    assert response.json() == {"updateRequested": False}

    # device was loaded (and cached in the identity map) by this same session's own
    # create_device() call above - refresh it to see the client's separate-session commit.
    await db_session.refresh(device)
    assert device.agent_version == "1.0.3"
    assert device.disk_total_bytes == 500_000_000_000
    assert device.disk_free_bytes == 100_000_000_000
    assert device.ram_used_bytes == 8_000_000_000
    assert device.last_telemetry_at is not None


async def test_agent_heartbeat_requires_bearer_auth(client):
    response = await client.post("/api/v1/heartbeat", json={"agentVersion": "1.0.3"})
    assert response.status_code == 401


async def test_request_update_then_heartbeat_reports_true_until_version_changes(client, db_session):
    device, secret = await create_device(db_session, agent_version="1.0.2")
    admin, _ = await create_admin(db_session)

    response = await client.post(
        f"/api/v1/devices/{device.id}/request-update", headers=_admin_auth_header(admin)
    )
    assert response.status_code == 200
    assert response.json()["update_requested"] is True

    # Still on the old version - the agent hasn't actually updated yet.
    response = await client.post(
        "/api/v1/heartbeat",
        headers=_device_bearer_header(device, secret),
        json={"agentVersion": "1.0.2"},
    )
    assert response.json() == {"updateRequested": True}

    # Now it reports a different version - the update landed, so the flag clears.
    response = await client.post(
        "/api/v1/heartbeat",
        headers=_device_bearer_header(device, secret),
        json={"agentVersion": "1.0.3"},
    )
    assert response.json() == {"updateRequested": False}

    response = await client.post(
        "/api/v1/heartbeat",
        headers=_device_bearer_header(device, secret),
        json={"agentVersion": "1.0.3"},
    )
    assert response.json() == {"updateRequested": False}


# --- Auto-approve via app allowlist -------------------------------------------------------------


async def test_matching_global_allowlist_entry_auto_approves(client, db_session):
    """The default _approval_request_body() submits publisher="Contoso Ltd.",
    filename="installer.exe", trustStatus="trusted" - matches this global entry exactly."""
    device, secret = await create_device(db_session)
    await create_app_allowlist_entry(db_session, group_id=None, publisher="Contoso Ltd.", filename="installer.exe")
    request_id = uuid.uuid4()

    response = await client.post(
        "/api/v1/requests",
        headers=_device_bearer_header(device, secret),
        json=_approval_request_body(request_id=request_id, device_id=device.device_uuid),
    )
    assert response.status_code == 201

    from app.models.enums import ElevationRequestStatus
    from app.repositories import elevation_request_repository

    stored = await elevation_request_repository.get_by_uuid(db_session, request_id)
    assert stored.status == ElevationRequestStatus.APPROVED

    decisions_response = await client.get(
        f"/api/v1/devices/{device.device_uuid}/decisions",
        headers=_device_bearer_header(device, secret),
    )
    decisions = decisions_response.json()
    assert len(decisions) == 1
    assert decisions[0]["status"] == "approved"
    assert decisions[0]["token"] is not None


async def test_auto_approval_is_audit_logged(client, db_session):
    device, secret = await create_device(db_session)
    entry = await create_app_allowlist_entry(
        db_session, group_id=None, publisher="Contoso Ltd.", filename="installer.exe"
    )
    admin, _ = await create_admin(db_session)

    await client.post(
        "/api/v1/requests",
        headers=_device_bearer_header(device, secret),
        json=_approval_request_body(request_id=uuid.uuid4(), device_id=device.device_uuid),
    )

    response = await client.get(
        "/api/v1/audit-logs", params={"action": "elevation_request.auto_approved"}, headers=_admin_auth_header(admin)
    )
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["metadata"]["matched_allowlist_entry_id"] == entry.id
    assert items[0]["actor_type"] == "system"


async def test_allowlist_entry_scoped_to_different_group_does_not_match(client, db_session):
    device_group = await create_device_group(db_session, name="Engineering")
    other_group = await create_device_group(db_session, name="Finance")
    device, secret = await create_device(db_session, group_id=device_group.id)
    await create_app_allowlist_entry(
        db_session, group_id=other_group.id, publisher="Contoso Ltd.", filename="installer.exe"
    )
    request_id = uuid.uuid4()

    await client.post(
        "/api/v1/requests",
        headers=_device_bearer_header(device, secret),
        json=_approval_request_body(request_id=request_id, device_id=device.device_uuid),
    )

    from app.models.enums import ElevationRequestStatus
    from app.repositories import elevation_request_repository

    stored = await elevation_request_repository.get_by_uuid(db_session, request_id)
    assert stored.status == ElevationRequestStatus.PENDING


async def test_allowlist_entry_scoped_to_matching_group_does_match(client, db_session):
    group = await create_device_group(db_session, name="Finance")
    device, secret = await create_device(db_session, group_id=group.id)
    await create_app_allowlist_entry(
        db_session, group_id=group.id, publisher="Contoso Ltd.", filename="installer.exe"
    )
    request_id = uuid.uuid4()

    await client.post(
        "/api/v1/requests",
        headers=_device_bearer_header(device, secret),
        json=_approval_request_body(request_id=request_id, device_id=device.device_uuid),
    )

    from app.models.enums import ElevationRequestStatus
    from app.repositories import elevation_request_repository

    stored = await elevation_request_repository.get_by_uuid(db_session, request_id)
    assert stored.status == ElevationRequestStatus.APPROVED


async def test_untrusted_signature_never_auto_approves_even_with_matching_publisher_filename(client, db_session):
    device, secret = await create_device(db_session)
    await create_app_allowlist_entry(db_session, group_id=None, publisher="Contoso Ltd.", filename="installer.exe")
    request_id = uuid.uuid4()

    body = _approval_request_body(request_id=request_id, device_id=device.device_uuid)
    body["signature"]["trustStatus"] = "untrusted"

    await client.post(
        "/api/v1/requests", headers=_device_bearer_header(device, secret), json=body
    )

    from app.models.enums import ElevationRequestStatus
    from app.repositories import elevation_request_repository

    stored = await elevation_request_repository.get_by_uuid(db_session, request_id)
    assert stored.status == ElevationRequestStatus.PENDING


async def test_no_matching_allowlist_entry_stays_pending(client, db_session):
    device, secret = await create_device(db_session)
    await create_app_allowlist_entry(db_session, group_id=None, publisher="Other Publisher", filename="other.exe")
    request_id = uuid.uuid4()

    await client.post(
        "/api/v1/requests",
        headers=_device_bearer_header(device, secret),
        json=_approval_request_body(request_id=request_id, device_id=device.device_uuid),
    )

    from app.models.enums import ElevationRequestStatus
    from app.repositories import elevation_request_repository

    stored = await elevation_request_repository.get_by_uuid(db_session, request_id)
    assert stored.status == ElevationRequestStatus.PENDING
