# ElevateGate Backend API Contract

This describes the **actual, implemented** contract of the FastAPI backend at `backend/`. It
supersedes an earlier placeholder version of this document that was written before the backend
existed, to be "handed to a future backend-build prompt." That prompt arrived with a more
detailed and slightly different spec than the placeholder guessed at — this document reflects
what was actually built, not the earlier guess.

There are now **two parallel families of endpoints**, both reading/writing the same underlying
tables:

1. The **admin/dashboard-facing endpoints** documented in "Endpoints" below — `snake_case` JSON,
   HTTP Basic device auth, used by the ElevateGate Dashboard and by nothing else.
2. The **agent-compatible endpoints** (`app/api/v1/agent_compat.py`) documented in its own section
   below — the exact paths, `camelCase` JSON, and device-bearer-token auth that the already-built
   .NET agent (`src/ElevateGate.Service`/`ElevateGate.Tray`,
   `ElevateGate.Infrastructure.Api.HttpApprovalApiClient`) actually calls. This reconciliation was
   done on the **backend** side, not the agent side: the agent binary is unchanged, and the
   backend was extended to speak its exact wire format instead.

> **History**: an earlier version of this document flagged the agent and this backend as
> mutually incompatible (different endpoint paths, device auth scheme, JSON casing, and signed
> payload byte layout — 5 fields in the agent vs. 7 in this backend's original design). That gap
> has been closed: the canonical signed payload is now the agent's original 5-field format
> (see "The signed approval token"), and the new agent-compatible endpoints below speak the
> agent's exact JSON shape and paths. This was verified byte-for-byte against a known-good
> cross-library interop vector (Python `cryptography` signing a message that Bouncy
> Castle/`ElevateGate.Core.Crypto.CanonicalApprovalPayload` independently verified) — see
> `backend/tests/unit/test_signing.py` and `backend/tests/integration/test_agent_compat.py`.

## Conventions

- JSON everywhere, `snake_case` field names (matching the entity definitions this backend was
  specified with — `device_uuid`, `signature_status`, `requested_at`, etc.).
- Timestamps: ISO-8601 UTC (accepts any valid ISO-8601 on input; emits with a `Z` suffix).
- Enums are serialized as their lowercase/snake_case string value (e.g. `"approved"`,
  `"hash_mismatch"`).
- Three distinct auth schemes, never mixed:
  - **Device-facing endpoints** (`/devices/*` except enroll, `/elevation-requests` POST,
    `/agent/decisions`, `/approvals/*/consumed`): **HTTP Basic**, username = the device's own
    `device_uuid`, password = the enrollment-issued device secret.
  - **Agent-compatible endpoints** (`/enroll`, `/requests`, `/devices/{id}/decisions` — see below):
    **`Authorization: Bearer <deviceUuid>.<secret>`**, the shape the real .NET agent actually
    sends. Same underlying device secret/Argon2id hash as HTTP Basic, just a different wire
    presentation for a client that only speaks bearer tokens.
  - **Admin-facing endpoints** (`/auth/me`, `/elevation-requests` GET/approve/deny): **Bearer
    JWT** from `POST /auth/login`.
- Rate limits (`slowapi`, in-memory, per client IP — see docs/BACKEND_THREAT_MODEL.md for the
  single-instance caveat) apply to every device-facing endpoint and to login; exceeding one
  returns `429`.

## Authentication

### Device enrollment and identity

- `POST /api/v1/devices/enroll` requires a pre-shared `X-Enrollment-Key` header (a secret
  configured on the backend, not tied to any specific device) — this isn't a fully open
  self-enrollment endpoint.
- Enrollment generates a random device secret, returns it **exactly once** in the response body,
  and persists only its Argon2id hash. There is no way to retrieve it again — re-enrollment
  requires a new `device_uuid` (the old one stays enrolled; there's no delete/rotate endpoint in
  this version).
- Every subsequent device call authenticates with HTTP Basic: `device_uuid` as username, the
  secret as password.

### Admin identity

- `POST /api/v1/auth/login` (email + password, Argon2id-verified) returns a JWT (HS256, 30 minute
  default expiry) carrying the admin's id and role.
- `Authorization: Bearer <token>` on every subsequent admin call.
- Two roles: `admin` and `reviewer`. Both are currently permitted on every RBAC-checked endpoint
  (`require_role("admin", "reviewer")`) — the distinction is enforced infrastructure (a `role`
  column, a JWT claim, a reusable `require_role(*roles)` dependency) ready for a future
  admin-only action, not a currently-observable behavioral difference between the two roles.

## Endpoints

### `POST /api/v1/devices/enroll`

Headers: `X-Enrollment-Key: <pre-shared secret>`

```json
{
  "device_uuid": "3f1c9c2e-6b7a-4b7b-9f0a-2b6a6a9e6b40",
  "hostname": "WORKSTATION-042",
  "operating_system": "Windows 11 23H2",
  "agent_version": "1.0.0"
}
```

→ `201`:

```json
{
  "id": 1,
  "device_uuid": "3f1c9c2e-6b7a-4b7b-9f0a-2b6a6a9e6b40",
  "device_secret": "shown-exactly-once-Zm9vYmFyYmF6cXV1eA",
  "enrollment_status": "active",
  "created_at": "2026-07-06T12:00:00.000000Z"
}
```

`401` wrong/missing enrollment key. `409` device_uuid already enrolled. `422` invalid body.

### `POST /api/v1/devices/heartbeat`

Auth: device Basic. Body (all optional): `{"agent_version": "1.0.1"}` → `200` with updated
`last_seen`/`enrollment_status`. `403` if the device has been revoked.

### `GET /api/v1/devices`

Auth: admin JWT. Added for the ElevateGate Dashboard, which needs a device list — not used by the
agent. Query params: `enrollment_status` (filter), `limit` (default 50, max 200), `offset`.

```json
{
  "items": [
    {
      "id": 1,
      "device_uuid": "3f1c9c2e-...",
      "hostname": "WORKSTATION-042",
      "operating_system": "Windows 11 23H2",
      "agent_version": "1.0.0",
      "last_seen": "2026-07-06T12:00:00.000000Z",
      "enrollment_status": "active",
      "online": true,
      "created_at": "2026-07-01T09:00:00.000000Z"
    }
  ],
  "total": 1
}
```

`online` is computed server-side (`enrollment_status == active AND last_seen` within
`DEVICE_ONLINE_THRESHOLD_SECONDS`, default 300) — the frontend never reimplements this rule. A
revoked device is always `online: false` regardless of `last_seen`.

### `POST /api/v1/elevation-requests`

Auth: device Basic. Every field describes a fact the agent derived locally — the backend
strictly validates shape (`sha256` must be 64 hex chars, `reason` non-trivial, etc.) but does not
re-derive these. (This is the dashboard-facing/`snake_case` route; the .NET agent instead calls
`POST /api/v1/requests` — see "Agent-compatible endpoints" below — which has no `username` field
at all and stores `username: null`.)

```json
{
  "username": "jdoe",
  "filename": "SomeInstaller.exe",
  "canonical_path": "C:\\Users\\jdoe\\Downloads\\SomeInstaller.exe",
  "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b85",
  "publisher": "Contoso Software Ltd.",
  "signature_status": "trusted",
  "file_size": 15481232,
  "file_version": "4.2.1.0",
  "reason": "Need this to configure the new label printer."
}
```

`signature_status` is one of: `unsigned`, `trusted`, `untrusted`, `hash_mismatch`, `revoked`,
`unknown`. Treated as strong input to the human review decision, never as an auto-approve signal.

→ `201` with the created `ElevationRequestRead` (status `"pending"`, a server-assigned
`request_uuid`, and `expires_at` = now + `ELEVATION_REQUEST_TTL_SECONDS`, default 1 hour — the
window during which it can still be reviewed). `ElevationRequestRead` also includes `device_uuid`
and `device_hostname` (joined from the owning `Device` row) alongside the raw internal
`device_id` — added for the ElevateGate Dashboard, which needs to display *which* device a
request came from without a separate per-row lookup.

### `GET /api/v1/elevation-requests`

Auth: admin JWT. Query params: `status` (filter), `limit` (default 50, max 200), `offset`.
→ `200` `{"items": [...], "total": N}`.

### `GET /api/v1/elevation-requests/{id}`

Auth: admin JWT. → `200` full `ElevationRequestRead`, or `404`.

### `POST /api/v1/elevation-requests/{id}/approve`

Auth: admin JWT. No body. Atomically transitions `pending` → `approved` (see "Concurrency" below);
generates a nonce, builds and Ed25519-signs the canonical approval payload, and persists an
`Approval` row. **The signed token is not returned in this response** — it's delivered to the
requesting device only, the next time that device polls `GET /agent/decisions`. This response
returns the updated `ElevationRequestRead` (now `status: "approved"`).

`404` unknown id. `409` already decided by someone else, or the review window already expired
(in which case the request is also flipped to `status: "expired"` as a side effect).

### `POST /api/v1/elevation-requests/{id}/deny`

Auth: admin JWT. Optional body `{"reason": "..."}` (recorded in the audit log only — there's no
dedicated denial-reason column on the entity). Same atomicity/expiry handling as approve, no
`Approval` row is ever created for a denial. → `200` updated `ElevationRequestRead`.

### `GET /api/v1/agent/decisions`

Auth: device Basic. Query param `since` (ISO-8601, optional — omit for "everything"). Returns
every non-pending decision for **the authenticated device only** — there's no device-id
parameter to spoof; identity comes entirely from the Basic auth credentials. Also lazily flips any
of that device's own stale-but-still-`pending` requests to `expired` before returning, so a
request nobody ever reviewed still eventually surfaces as expired rather than vanishing.

```json
[
  {
    "request_uuid": "a1b2c3d4-...",
    "status": "approved",
    "approval": {
      "id": 7,
      "elevation_request_id": 3,
      "action": "execute",
      "device_uuid": "3f1c9c2e-...",
      "sha256": "e3b0c442...",
      "nonce": "8f3c1e7a9b2d4f6e",
      "issued_at": "2026-07-06T12:05:00.000000Z",
      "expires_at": "2026-07-06T12:10:00.000000Z",
      "signature": "base64...",
      "consumed_at": null
    }
  },
  { "request_uuid": "b2c3d4e5-...", "status": "denied", "approval": null }
]
```

`approval` is non-null if and only if `status` is `"approved"`.

### `POST /api/v1/approvals/{id}/consumed`

Auth: device Basic. Called once the agent has verified the signature locally and executed the
file. `404` if the approval doesn't exist *or* belongs to a different device (deliberately the
same response either way — existence of another device's approval id isn't information this
caller is entitled to). `409` if already marked consumed. → `200`
`{"id": 7, "elevation_request_id": 3, "consumed_at": "..."}`.

### `POST /api/v1/auth/login`

Public (rate-limited). `{"email": "...", "password": "..."}` → `200`
`{"access_token": "...", "token_type": "bearer"}`, or `401`. Response timing is equalized between
"unknown email" and "wrong password" (a dummy Argon2id verify runs either way) so the two aren't
distinguishable from latency alone.

### `GET /api/v1/auth/me`

Auth: admin JWT. → `200` `{"id", "email", "name", "role", "is_active", "created_at"}` — never the
password hash.

### `GET /api/v1/audit-logs`

Auth: admin JWT. Added for the ElevateGate Dashboard. Query params: `actor_type` (`admin` |
`device` | `system`), `action` (exact match, e.g. `"elevation_request.approved"`), `target_type`
(exact match, e.g. `"elevation_request"`), `limit` (default 50, max 200), `offset`. Ordered newest
first.

```json
{
  "items": [
    {
      "id": 42,
      "actor_type": "admin",
      "actor_id": "3",
      "action": "elevation_request.approved",
      "target_type": "elevation_request",
      "target_id": "17",
      "metadata": { "nonce": "8f3c1e7a9b2d4f6e" },
      "timestamp": "2026-07-06T12:05:00.000000Z"
    }
  ],
  "total": 1
}
```

Note `actor_id` for an `admin` actor is the admin's numeric id as a string (no name/email join —
audit logs record what happened, not a resolved display name).

### `GET /api/v1/dashboard/summary`

Auth: admin JWT. Added for the ElevateGate Dashboard's summary cards — computed server-side with
real aggregate queries so the dashboard never pages through full lists to produce a number.
"Today" = current UTC calendar day, from midnight UTC.

```json
{
  "pending_requests": 4,
  "approved_today": 12,
  "denied_today": 1,
  "active_devices": 37,
  "offline_devices": 3
}
```

`active_devices`/`offline_devices` only count currently-enrolled (`enrollment_status: active`)
devices — a revoked device counts toward neither bucket.

## Concurrency: preventing a double-approve

`approve`/`deny` are implemented as a single
`UPDATE elevation_requests SET status=... WHERE id=:id AND status='pending' RETURNING *`
inside one transaction. PostgreSQL serializes concurrent `UPDATE`s to the same row; whichever
transaction commits second has its `WHERE status='pending'` clause re-evaluated against the
already-changed row and matches zero rows, so it observably gets `409`. No explicit
`SELECT ... FOR UPDATE` bookkeeping needed. Verified with an integration test that fires two
concurrent approve calls at the same request and asserts exactly one `200` and one `409`, and
exactly one `Approval` row.

## The signed approval token

**Canonical payload** (`app/core/signing.py:build_canonical_payload`), Ed25519-signed — this is
byte-for-byte the same layout the .NET agent's
`ElevateGate.Core.Crypto.CanonicalApprovalPayload.Build` reconstructs and verifies:

```
byte     schema_version = 0x01
uint16BE len(device_uuid)  + UTF-8 bytes of device_uuid
uint16BE len(request_uuid) + UTF-8 bytes of request_uuid
uint16BE len(sha256)       + UTF-8 bytes of sha256, lowercase hex text
uint16BE len(expires_at)   + UTF-8 bytes, .NET "O" round-trip format:
                              "yyyy-MM-ddTHH:mm:ss.fffffff+00:00" (7 fractional digits, a
                              numeric "+00:00" offset — never "Z" — see
                              app/core/signing.py:format_dotnet_round_trip)
uint16BE len(nonce)        + UTF-8 bytes of nonce
```

All integers big-endian; every field length-prefixed (not delimited) so no field's content can
ever be crafted to shift where one field ends and the next begins — this was validated with tests
proving two different field splits that would concatenate identically under naive delimiting
produce different bytes here.

The `expires_at` format is the one genuinely fussy part of this reconciliation: .NET's
`DateTimeOffset.ToString("O")` always emits 7 fractional-second digits and a numeric UTC offset,
never a "Z" suffix — confirmed empirically against a live `dotnet run` probe, not assumed from
documentation. `format_dotnet_round_trip` reproduces this exactly (Python's 6-digit microsecond
precision gets one trailing zero appended). Both the backend (when signing) and the .NET agent
(when verifying, via `.ToUniversalTime()` before formatting) normalize to UTC before building this
string, so it's safe for the JSON wire representation of a timestamp to use a different — but
instant-equivalent — offset than what ends up in the signed bytes; only the *canonical payload
builder's own* formatting has to match exactly.

`issued_at`/`action` (from an earlier, incompatible 7-field design) are no longer part of the
signed bytes. `issued_at` is still stored on the `Approval` row for audit purposes; `action` is
still stored too (always `"execute"`) but likewise isn't signed over — a single-purpose approval
has nothing meaningful to gain from those two being part of the cryptographic commitment when the
one real client that verifies it (the agent) never included them.

Signing key: Ed25519 (RFC 8032), loaded once at startup from `ED25519_PRIVATE_KEY_B64` (env) or
`ED25519_PRIVATE_KEY_PATH` (mounted file — a base64-encoded 32-byte seed) — **never from the
database**, and the running process never logs it. The corresponding public key must be
distributed to devices out of band (this backend never serves it over the API) — it's what gets
pinned into the agent's own configuration at deployment time (see THREAT_MODEL.md).

Cross-library Ed25519 interop (Python `cryptography` signing a message, verified successfully by
the real .NET agent's Bouncy Castle-backed `Ed25519Verifier`) was empirically confirmed and is
preserved as a permanent regression test — `test_ed25519_cross_library_interop_known_vector` in
`backend/tests/unit/test_signing.py` — and exercised end-to-end (submit → approve → poll →
independently re-verify) in `backend/tests/integration/test_agent_compat.py`.

## Agent-compatible endpoints (`app/api/v1/agent_compat.py`)

These are the **only three endpoints the real .NET agent calls**
(`ElevateGate.Infrastructure.Api.HttpApprovalApiClient`), at its exact paths and JSON shape —
`camelCase` throughout (matching .NET's `JsonSerializerDefaults.Web`), mirroring the C# records in
`ElevateGate.Core.Models` field-for-field. See `backend/app/schemas/agent_wire.py`.

**Device auth**: `Authorization: Bearer <deviceUuid>.<secret>` — a single opaque token issued once
by `POST /api/v1/enroll`. The `<deviceUuid>.` prefix isn't itself a secret (the device already
discloses its own UUID elsewhere); it just lets the backend look the device up in O(1) instead of
scanning every enrolled device's Argon2id hash per request. Only the part after the dot
authenticates anything, verified the same way (Argon2id) as the dashboard-facing HTTP-Basic
device secret — the two auth schemes share the same underlying `device_secret_hash` column and
`generate_device_secret()`/`verify_secret()` functions, just presented differently on the wire.

### `POST /api/v1/enroll`

Headers: `X-Enrollment-Key: <pre-shared secret>` (same shared secret as the dashboard-facing
enroll route).

```json
{ "deviceId": "3f1c9c2e-6b7a-4b7b-9f0a-2b6a6a9e6b40", "machineName": "WORKSTATION-042", "operatingSystemVersion": "Windows 11 23H2" }
```

→ `201`:

```json
{ "bearerToken": "3f1c9c2e-6b7a-4b7b-9f0a-2b6a6a9e6b40.Zm9vYmFyYmF6cXV1eA", "enrolledAtUtc": "2026-07-06T12:00:00.000000Z" }
```

`401` wrong/missing enrollment key, `409` device already enrolled, `422` invalid body. Deliberately
does **not** return the server's Ed25519 public key in this response — see THREAT_MODEL.md: it's
pinned into the agent's own configuration at deployment time, never learned from enrollment, so a
party positioned during enrollment can never substitute their own signing key.

Note: `EnrollmentRequest` has no `agentVersion` field (the agent never sends one at enroll time) —
`Device.agent_version` is nullable and stays `null` for agent-enrolled devices until/unless
something populates it later.

### `POST /api/v1/requests`

Auth: device bearer token. Mirrors `ApprovalRequest(RequestId, DeviceId, File, Signature, Reason, RequestedAtUtc)`:

```json
{
  "requestId": "a1b2c3d4-...",
  "deviceId": "3f1c9c2e-...",
  "file": {
    "fileName": "SomeInstaller.exe",
    "fullPath": "C:\\Users\\jdoe\\Downloads\\SomeInstaller.exe",
    "sizeBytes": 15481232,
    "fileVersion": "4.2.1.0",
    "sha256Hex": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b85"
  },
  "signature": {
    "trustStatus": "trusted",
    "publisherCommonName": "Contoso Software Ltd.",
    "certificateThumbprint": "AABBCCDD..."
  },
  "reason": "Need this to configure the new label printer.",
  "requestedAtUtc": "2026-07-06T12:00:00.000000Z"
}
```

`trustStatus` is one of `unsigned`, `trusted`, `untrusted`, `hashMismatch`, `revoked`, `unknown` —
note **`hashMismatch`** (camelCase), which differs from this backend's own internal
`SignatureStatus.HASH_MISMATCH` spelling (`hash_mismatch`); `agent_wire.py` maps between the two
explicitly.

The **`requestId` the agent supplies is preserved verbatim** as the elevation request's
`request_uuid` — the agent generates this id itself and never reads the response body
(`SubmitRequestAsync` only checks `EnsureSuccessStatusCode()`), so whatever id it used to submit is
the only id it will later recognize when polling decisions or validating a token. A `deviceId` in
the body that doesn't match the authenticated device is rejected with `400`.

→ `201` (body not part of the contract — the agent never reads it). `400` deviceId mismatch, `401`
missing/invalid bearer token, `403` device not active, `422` invalid body.

Note: `ApprovalRequest` has no `username` field — the agent never captures the locally logged-in
Windows username anywhere in its current implementation. `ElevationRequest.username` is nullable;
a request submitted through this route always has `username: null`. The dashboard shows "—" for
this case rather than a blank cell or a fabricated placeholder.

### `GET /api/v1/devices/{deviceId}/decisions`

Auth: device bearer token. Query param `since` (ISO-8601, optional — the agent sends
`sinceUtc.ToUniversalTime().ToString("O")`, e.g. `2026-07-06T12:00:00.1234567+00:00`; this backend
accepts any valid ISO-8601, including that exact shape). The `deviceId` path segment must match the
authenticated device's own uuid (`403` otherwise, so a device can never even probe whether some
other id belongs to a real device) — real identity for the query still comes exclusively from the
bearer token, same as the dashboard-facing `/agent/decisions`. Also lazily flips any of that
device's stale-but-still-pending requests to `expired` before returning.

```json
[
  {
    "requestId": "a1b2c3d4-...",
    "status": "approved",
    "token": {
      "deviceId": "3f1c9c2e-...",
      "requestId": "a1b2c3d4-...",
      "sha256Hex": "e3b0c442...",
      "expiresAtUtc": "2026-07-06T12:10:00.000000Z",
      "nonce": "8f3c1e7a9b2d4f6e",
      "signature": "base64..."
    }
  },
  { "requestId": "b2c3d4e5-...", "status": "denied", "token": null }
]
```

`token` is non-null if and only if `status` is `"approved"` — mirrors `ApprovalDecision(RequestId, Status, Token)`.

### `POST /api/v1/heartbeat`

Auth: device bearer token. Not part of the agent's originally-shipped contract — added alongside
`ElevateGate.Infrastructure.Api.HttpApprovalApiClient.SendHeartbeatAsync` so the dashboard can show
live disk/RAM telemetry and each device's running agent version, and so an admin's "update now"
request (`POST /api/v1/devices/{id}/request-update`) actually reaches the device. Sent every
`TelemetryIntervalMinutes` (agent-side setting, default 5).

```json
{
  "agentVersion": "1.0.4",
  "diskTotalBytes": 512110190592,
  "diskFreeBytes": 128027557888,
  "ramTotalBytes": 17179869184,
  "ramUsedBytes": 8589934592
}
```

All fields optional/nullable — a stat the agent couldn't read is simply omitted, never fabricated.

→ `200`:

```json
{ "updateRequested": false }
```

`updateRequested` is `true` iff an admin has asked this device to update and it hasn't yet
reported back a different `agentVersion` since that request — see `Device.update_requested_at`.

## Error responses

Standard FastAPI shape: `{"detail": "human-readable message"}` (or FastAPI's structured
`detail` array for `422` validation errors). No error path ever includes a stack trace, a secret,
or a JWT/password/device-secret value.

| Status | Meaning |
|---|---|
| 400 / 422 | Malformed request body |
| 401 | Missing/invalid credentials (device Basic or admin JWT) |
| 403 | Authenticated but not authorized (revoked device, insufficient role) |
| 404 | Unknown resource, or a resource that exists but doesn't belong to the caller |
| 409 | Conflict (already enrolled, already decided, already consumed, expired) |
| 429 | Rate limit exceeded |
