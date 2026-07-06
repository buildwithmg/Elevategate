# ElevateGate Agent — Threat Model

## Purpose and non-goals

ElevateGate lets a standard (non-admin) user ask IT for permission to run one specific, already-
selected installer, without ever handing that user (or the agent) local admin credentials.

**Explicit non-goals** — these are not partially implemented or "coming later," they are
deliberately absent from the design:

- No remote shell, PowerShell, or arbitrary command execution, from the backend or anywhere else.
- No generic "run as admin" / elevation API for arbitrary processes.
- No capability to execute anything other than the exact file, identified by exact SHA-256, that
  a human approved.
- No handling, storage, or transmission of administrator (or any user's) password, ever.

If a future requirement needs any of the above, it needs a new threat model, not an extension of
this one.

## Assets

| Asset | Where it lives | Why it matters |
|---|---|---|
| Server Ed25519 public key | Service config, pinned at deploy time | The entire trust boundary for "this decision is genuine" |
| Device bearer token | DPAPI-protected on disk (LocalSystem scope) | Lets a device submit requests / poll decisions as itself |
| Nonce ledger | Local SQLite (`nonces.db`) | Prevents an approval token from being replayed |
| Audit log | Local SQLite (`audit.db`) + rolling file log | Forensic record of every decision point |
| The file being approved | Wherever the user picked it from | The actual thing that gets executed |

## Trust boundaries

```
[ Standard user, Tray.exe (user session) ]
        | named pipe (local only, ACL + client identity checked)
        v
[ LocalSystem, Service.exe ]
        | HTTPS
        v
[ Backend (not built yet; see API_CONTRACT.md) ]
```

The tray is **never trusted**. It runs in the user's session, could in principle be a different
build than expected, and its input (a file path and a reason string) is treated by the service as
a hint to re-derive everything from, not as fact.

## Threats and mitigations

### T1 — Malicious/compromised tray process feeds a crafted path

A process impersonating the tray connects to the named pipe and submits an arbitrary path,
hoping the service will trust it enough to eventually execute it.

Mitigations:
- Named pipe DACL restricts connections to interactive local users + LocalSystem
  (`NativeMethods.PipeSecurityDescriptorSddl`).
- `PipeClientValidator` additionally checks, per connection: the client's process image path
  matches the exact installed `ElevateGate.Tray.exe` path, and the client's session id matches the
  active console session (rejects a background/service-session or other RDP session's process).
  Note this identity check is by path, not by Authenticode signature/hash of the running binary —
  something that could overwrite the file at that exact path could impersonate the tray. Writing
  to `%ProgramFiles%\ElevateGate` requires admin rights by default ACLs, so this isn't a
  standard-user escalation path; it's listed here as an accepted limitation, not a gap in the
  threat model's actual attacker scope.
- Even if all of the above were somehow bypassed, the path is re-validated and re-hashed by
  `ExecutionEngine` immediately before execution — the pipe message alone can never cause
  execution.

### T2 — Path traversal / UNC / removable-drive execution

An attacker tries to get the service to execute something outside the intended local, fixed-drive
file system — a network share under their control, a removable device, or a path built to escape
an assumed directory via `..` segments.

Mitigations:
- `PathValidator` (`ElevateGate.Core`) rejects any raw path containing a `..` segment outright
  (no attempt to "resolve" it), rejects UNC/`\\`-prefixed paths, and classifies the drive via
  `IDriveClassifier` — only a drive positively identified as `Fixed` is allowed; removable,
  network, and unrecognized drive types are all denied by default.
- This logic is implemented as plain string parsing independent of the host OS's path semantics
  (see `WindowsPathRules`), so it behaves identically under test and in production rather than
  relying on `System.IO.Path`'s platform-dependent interpretation.
- `ExecutionEngine` re-runs this validation immediately before launching, not just at submission
  time.

### T3 — Time-of-check to time-of-use (TOCTOU): file changes between request and approval

Minutes can pass between a user requesting approval and an admin deciding. The file on disk could
be swapped in that window.

Mitigation:
- `ExecutionEngine` recomputes SHA-256 from the file on disk immediately before execution and
  runs full `ApprovalTokenValidator` validation at that moment — the hash computed at request
  submission time is never reused to authorize execution.

### T4 — Approval token replay

An approval token is captured (e.g. from a log, or a compromised backend response cache) and
presented again later, or presented on a different device.

Mitigations:
- Token binds `deviceId`, `requestId`, `sha256Hex`, `expiresAtUtc`, and `nonce`, all covered by
  the Ed25519 signature.
- `ApprovalTokenValidator` checks `deviceId` **and** `requestId` against the specific execution
  being attempted, not just against "some pending request on this device" — this is what stops a
  token legitimately issued for one request from being cross-applied to a different request that
  happens to reference a file with identical content (and therefore an identical SHA-256).
- `INonceStore` persists every consumed nonce; a repeat is rejected regardless of whether the
  first use succeeded or failed validation (the nonce is consumed as soon as it reaches that
  check, closing off repeated attempts against the same token).
- `deviceId`/`requestId` mismatches are rejected independent of nonce/expiry state.
- Short token lifetime (`expiresAtUtc`) limits the replay window even before the nonce check.

### T5 — Forged approval (no legitimate signing key)

An attacker without the backend's private key tries to construct their own "approved" decision.

Mitigation:
- Ed25519 signature verification against a public key pinned into local configuration at deploy
  time. The public key is never fetched over the network or accepted from the enrollment response
  — see T7.

### T6 — Compromised/malicious backend, or on-path attacker between service and backend

Mitigations:
- Transport is HTTPS (TLS) end to end.
- Even a fully malicious backend cannot get the agent to run arbitrary code: the only capability
  the backend has is to sign an approval for a specific SHA-256 of a file the *device itself*
  already has on disk and already hashed. It cannot supply new file content, a command line, or a
  script — there is no code path that accepts any of those from the backend.
- A backend that returns `status: "approved"` without a valid signed token is rejected
  (`ApprovalTokenValidator`), and a decision with `approved` status but a missing token is treated
  as a protocol violation, not an approval.

### T7 — Key substitution at enrollment

If the server's public key were delivered as part of the enrollment response, an attacker
positioned during that one HTTP call (e.g. a compromised network path before HTTPS is fully
trusted, or a rogue backend during initial setup) could hand the device an attacker-controlled
public key, and every future forged "approval" signed with the matching private key would verify
successfully forever after.

Mitigation:
- The public key is **not** part of the enrollment response at all (see `API_CONTRACT.md`). It is
  baked into the service's deployed configuration by whoever packages the install
  (`ElevateGate:ServerPublicKeyBase64`), out of band from any network call the agent makes.

### T8 — Credential theft from disk

An attacker with local admin/SYSTEM access reads the device's bearer token off disk.

Mitigations:
- The token is DPAPI-protected (`LocalMachine` scope) rather than stored in plaintext.
- Blast radius if stolen: the attacker can submit requests and read decisions as that device —
  they still cannot execute anything without a legitimately signed approval token, because
  execution authority lives in the Ed25519 signature, not the bearer token. (An attacker with
  local SYSTEM access already has much stronger options than this anyway; DPAPI here is
  defense-in-depth against casual disk access, not a defense against a fully compromised host.)
- The agent never stores an administrator password, so there is no credential of that kind to
  steal in the first place.

### T9 — MSI/EXE argument injection

An attempt to smuggle extra command-line flags into the launched process (e.g. to make `msiexec`
do something other than a plain install).

Mitigation:
- `ExecutionEngine` builds the MSI invocation with a fixed, hard-coded argument list
  (`/i "<verified path>" /quiet`) where the verified path is the only variable. No argument is
  ever sourced from the tray, the backend, or the approval token. `.exe` files are launched
  directly with no arguments at all. There is no function anywhere in the codebase that accepts
  and forwards an arbitrary argument list to `Process.Start`.

### T10 — Unauthorized device enrollment

Nothing in this repo's HTTP client stops an arbitrary caller from hitting `POST /api/v1/enroll`
and obtaining a device identity.

Mitigation (backend responsibility, documented in `API_CONTRACT.md`): enrollment should require
some pre-authorization (shared secret, device allowlist, or an authenticated admin action).
Enrollment alone grants no execution capability — every request still requires a human decision —
but an open enrollment endpoint is still unnecessary attack surface and should be closed off when
the backend is built.

## Residual risk / accepted limitations (MVP)

- **In-flight request tracking is in-memory** (`RequestStateStore`). A service restart while a
  request is pending loses local tracking for it; the tray's status poll will report "unknown
  request," though the backend remains the durable source of truth for the decision itself. Not a
  security issue, but a usability one worth revisiting post-MVP.
- **Explorer integration is a registry shell verb**, not a COM `IExplorerCommand` handler. This
  was a deliberate scope decision (see the implementation plan) — it's simpler and has no COM
  registration/hosting risk, at the cost of a slightly less "native" menu placement.
- **`X509Certificate2.CreateFromSignedFile`** is used to read the signer certificate; it's
  functionally fine on .NET 8 but is obsolete-marked starting in .NET 9 and should be revisited on
  the next TFM upgrade.
