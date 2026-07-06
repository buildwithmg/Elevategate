# ElevateGate Backend — Threat Model

Complements [THREAT_MODEL.md](THREAT_MODEL.md) (the Windows agent's threat model) rather than
duplicating it. That document covers the device-local trust boundary (tray → service → execution);
this one covers the backend's own trust boundaries (devices/admins → backend → database).

## Non-goals (unchanged from the agent's threat model)

The backend never issues, and has no code path capable of issuing, anything other than a
structured elevation approval bound to an exact device and an exact SHA-256. No endpoint accepts
or forwards a shell command, script, or arbitrary argument list to any device. No endpoint
handles, stores, or returns an administrator's Windows/domain password — device secrets and admin
passwords are backend-local credentials for calling this API, nothing more.

## Assets

| Asset | Where it lives | Why it matters |
|---|---|---|
| Ed25519 private signing key | Env var or mounted file, held only in process memory | The entire trust boundary for "a human actually approved this" |
| Device secrets | Argon2id hash in `devices.device_secret_hash` | Let a device submit requests / poll decisions / mark consumed as itself |
| Admin passwords | Argon2id hash in `admin_users.password_hash` | Let an admin approve/deny requests |
| JWT signing secret | Env var (`JWT_SECRET_KEY`) | Forging one = impersonating any admin |
| Enrollment key | Env var (`ENROLLMENT_KEY`) | Gates who can create new device identities at all |
| Nonces | `approvals.nonce`, unique constraint | Approval single-use guarantee |
| Audit log | `audit_logs`, append-only | Forensic record of every enroll/approve/deny/consume |

## Threats and mitigations

### T1 — Unauthorized device enrollment

Mitigation: `POST /devices/enroll` requires `X-Enrollment-Key` matching a backend-configured
secret. This is a shared secret, not per-device — it gates "can create *a* device identity at
all," not which specific identity. Rotate it if it leaks; devices already enrolled are unaffected
(the key isn't used again after enrollment).

Residual risk: anyone with the enrollment key can create arbitrarily many device identities. That
alone grants no execution capability — every elevation request still needs a human decision — but
it could be used to spam the review queue. Rate limiting (`RATE_LIMIT_ENROLL`, default 5/minute
per IP) bounds this.

### T2 — Device credential theft

An attacker who steals a device's secret can submit elevation requests and poll decisions as that
device.

Mitigations: secrets are Argon2id-hashed at rest (a stolen database dump doesn't yield usable
secrets directly). Blast radius even with the live plaintext secret: the attacker can submit
requests (which still need human approval) and read decisions/tokens *scoped to that one device*
(`/agent/decisions` derives device identity from the Basic auth credentials, never a path
parameter — cross-device enumeration isn't possible even with valid credentials for a different
device). They cannot forge an approval without the Ed25519 private key.

### T3 — Admin credential theft / JWT theft

Mitigations: Argon2id password hashing; JWTs are short-lived (30 min default); login responses are
timing-equalized between "unknown email" and "wrong password" so an attacker can't use latency to
enumerate valid admin emails. A stolen JWT is usable only until it expires — there's no revocation
list in this version (noted as a residual limitation below).

### T4 — Forged or tampered approval

Mitigation: every approval is Ed25519-signed over a length-prefixed canonical byte layout (see
API_CONTRACT.md) that binds device_uuid, request_uuid, sha256, action, issued_at, expires_at, and
nonce together. The private key never touches the database and is never logged. Tampering with
any field invalidates the signature (unit-tested, including a field-boundary-shift test proving
length-prefixing — not delimiting — is what's actually preventing ambiguity).

### T5 — Approval replay

Mitigations, layered: (a) `approvals.nonce` has a database uniqueness constraint — the nonce is
generated once per issued approval and never reused by construction; (b) `expires_at` bounds the
window regardless (`APPROVAL_TTL_SECONDS`, default 5 minutes); (c) `POST /approvals/{id}/consumed`
atomically sets `consumed_at` only if currently `NULL` (a second call gets `409`), giving the
backend its own idempotency record independent of whatever replay protection the agent implements
locally.

### T6 — Two admins approving the same request simultaneously

This is the specific race the spec calls out, and it's handled at the database level, not the
application level: `approve`/`deny` execute a single
`UPDATE ... WHERE id=:id AND status='pending' RETURNING *` inside one transaction. PostgreSQL
serializes concurrent `UPDATE`s to the same row; the loser's `WHERE` clause re-evaluates against
the winner's already-committed status and matches zero rows. Verified with an integration test
that fires two concurrent approve calls at the same request via `asyncio.gather` and asserts
exactly one `200`/one `409`, and exactly one `Approval` row ever created. No advisory locks or
`SELECT ... FOR UPDATE` needed — the atomic conditional `UPDATE` *is* the lock.

### T7 — Rate-limit bypass / brute force

Mitigation: `slowapi` in-memory limiter on every device-facing endpoint and on login.

**Residual limitation, stated plainly**: this is per-process, in-memory state. It does not share
counters across multiple backend replicas — behind a load balancer with N instances, the
effective limit is N× the configured value. A production multi-instance deployment should back
this with Redis (a drop-in `slowapi` storage backend) instead. Fine for the single-instance
deployment this Docker Compose setup describes; a real gap for horizontal scaling.

**Second residual limitation**: FastAPI resolves an endpoint's `Depends()` parameters (including
`get_current_device` and `get_current_admin`'s login lookup, both of which do a real Argon2id
verify) *before* calling the route function that `slowapi`'s `@limiter.limit(...)` decorator
wraps — the limit check itself only runs once that call happens. That means a request that will
ultimately be rejected with `429` still pays the full Argon2id cost first; the limiter bounds
*request rate*, not *CPU cost per request already in flight*. Combined with the `password`
length cap (see T9) this bounds the damage, but a determined attacker can still force N full
Argon2id verifications per rate-limit window rather than zero. Moving the limit check ahead of
authentication would need slowapi's lower-level API wired in as its own first-resolved
dependency rather than a decorator — not done here.

### T8 — Secrets in logs

Mitigation: nothing in this codebase logs a request body, an `Authorization` header, a password,
a device secret, or the Ed25519 private key. Uvicorn's default access log records only
method/path/status. The login endpoint's timing-equalization path explicitly discards its dummy
verification result rather than logging anything about it.

### T9 — SQL injection / malformed input

Mitigation: every query goes through SQLAlchemy's parameterized query builder — no string-built
SQL anywhere in the codebase. Every request body is validated by a Pydantic schema before it
reaches any repository function (`sha256` pattern-matched to 64 hex chars, string length bounds on
every free-text field, `file_size >= 0`, etc.), including `LoginRequest.password` (max 128
chars) — an unauthenticated, public endpoint whose password field feeds directly into Argon2id,
so an unbounded length would let a caller inflate per-request CPU cost with a large payload. Found
and fixed during review; regression-tested in `tests/integration/test_auth.py`.

### T10 — Private key exposure

Mitigation: loaded once at process startup from an env var or a mounted file (Docker Compose uses
a file-based secret mounted at `/run/secrets/ed25519_private_key`, never baked into the image or
passed as a plain environment variable in compose config). Never written to, or readable from, the
database. `get_public_key_b64()` exists only for operator-side confirmation of which key is
loaded and is never wired to any HTTP endpoint.

## Residual risks / accepted limitations (MVP, stated explicitly rather than left implicit)

- **No JWT revocation list.** A stolen token remains valid until its (short) expiry. Acceptable
  for an internal admin tool at this scope; a production hardening would add a revocation/blocklist
  or move to shorter-lived tokens with refresh.
- **Rate limiting is single-instance.** See T7.
- **No device secret rotation/revoke endpoint.** A compromised device's `enrollment_status` can be
  flipped in the database directly (blocking heartbeat/submit/decisions/consumed - all check for
  `ACTIVE`), but there's no API endpoint for an admin to do this yet.
- **Docker Compose was not actually built/run** in the environment this backend was developed in
  (no Docker available) — reviewed carefully, but stated as unverified rather than implied tested.
  See backend/README.md.
- **Not wire-compatible with the existing .NET agent** as-is — see the compatibility notice at the
  top of API_CONTRACT.md.
