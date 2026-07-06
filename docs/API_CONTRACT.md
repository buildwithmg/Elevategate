# ElevateGate Backend API Contract

This describes the **actual, implemented** contract of the FastAPI backend at `backend/`. It
supersedes an earlier placeholder version of this document that was written before the backend
existed, to be "handed to a future backend-build prompt." That prompt arrived with a more
detailed and slightly different spec than the placeholder guessed at — this document reflects
what was actually built, not the earlier guess.

> **Compatibility notice for the existing .NET agent** (`src/ElevateGate.Service`,
> `src/ElevateGate.Tray`, built in an earlier session): that agent was built against the old
> placeholder contract and is **not** wire-compatible with this backend as it stands. Concretely:
> - Endpoint paths differ (`POST /api/v1/enroll` → `POST /api/v1/devices/enroll`,
>   `POST /api/v1/requests` → `POST /api/v1/elevation-requests`,
>   `GET /api/v1/devices/{id}/decisions` → `GET /api/v1/agent/decisions`, plus new
>   `POST /api/v1/devices/heartbeat` and `POST /api/v1/approvals/{id}/consumed` endpoints the
>   agent doesn't call today).
> - Device auth differs (agent sends a bearer token from a JSON enrollment response; this backend
>   uses HTTP Basic with the device's own UUID as username and its enrollment secret as password).
> - JSON casing differs (agent expects `camelCase`; this backend uses `snake_case` throughout,
>   matching the entity field names given in the backend's own spec).
> - **The signed approval payload byte layout is different and incompatible** — see "The signed
>   approval token" below. The agent's `ElevateGate.Core.Crypto.CanonicalApprovalPayload` encodes
>   5 fields (no `action`, no `issued_at`); this backend signs 7 fields including both, per its
>   own explicit spec.
>
> Making the agent and this backend interoperate is a **follow-up task**, not done here — this
> backend was built to its own spec, and the agent was built to its own (earlier) spec, and
> reconciling them means updating the agent's HTTP client and canonical payload builder to match
> what's documented below.

## Conventions

- JSON everywhere, `snake_case` field names (matching the entity definitions this backend was
  specified with — `device_uuid`, `signature_status`, `requested_at`, etc.).
- Timestamps: ISO-8601 UTC (accepts any valid ISO-8601 on input; emits with a `Z` suffix).
- Enums are serialized as their lowercase/snake_case string value (e.g. `"approved"`,
  `"hash_mismatch"`).
- Two distinct auth schemes, never mixed:
  - **Device-facing endpoints** (`/devices/*` except enroll, `/elevation-requests` POST,
    `/agent/decisions`, `/approvals/*/consumed`): **HTTP Basic**, username = the device's own
    `device_uuid`, password = the enrollment-issued device secret.
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
re-derive these.

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

**Canonical payload** (`app/core/signing.py:build_canonical_payload`), Ed25519-signed:

```
byte     schema_version = 0x01
uint16BE len(request_uuid) + UTF-8 bytes of request_uuid
uint16BE len(device_uuid)  + UTF-8 bytes of device_uuid
uint16BE len(sha256)       + UTF-8 bytes of sha256, lowercase hex text
uint16BE len(action)       + UTF-8 bytes of action (currently always "execute")
uint16BE len(issued_at)    + UTF-8 bytes, "%Y-%m-%dT%H:%M:%S.%fZ" (UTC, microsecond precision)
uint16BE len(expires_at)   + UTF-8 bytes, same format
uint16BE len(nonce)        + UTF-8 bytes of nonce
```

All integers big-endian; every field length-prefixed (not delimited) so no field's content can
ever be crafted to shift where one field ends and the next begins — this was validated with tests
proving two different field splits that would concatenate identically under naive delimiting
produce different bytes here.

Signing key: Ed25519 (RFC 8032), loaded once at startup from `ED25519_PRIVATE_KEY_B64` (env) or
`ED25519_PRIVATE_KEY_PATH` (mounted file — a base64-encoded 32-byte seed) — **never from the
database**, and the running process never logs it. The corresponding public key must be
distributed to devices out of band (this backend never serves it over the API).

Cross-library Ed25519 interop (Python `cryptography` signing, verified by a different Ed25519
implementation) was empirically confirmed during design of this backend and is preserved as a
regression test in `backend/tests/unit/test_signing.py`.

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
