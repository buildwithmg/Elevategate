# ElevateGate

An endpoint privilege-approval system: a Windows agent lets a standard user pick an installer
(`.exe`/`.msi`), state a reason, and ask IT for approval — without ever being handed local admin
rights or a generic "run anything" capability — and a FastAPI/PostgreSQL backend lets an admin
review and approve/deny those requests, issuing a signed, single-use, short-lived Ed25519 token
the agent verifies before executing anything.

- **`src/`, `tools/`** — the Windows agent (C#/.NET 8). See [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md).
- **`backend/`** — the FastAPI/PostgreSQL backend admins and agents talk to. See
  [backend/README.md](backend/README.md) and [docs/BACKEND_THREAT_MODEL.md](docs/BACKEND_THREAT_MODEL.md).
- **`dashboard/`** — the Next.js admin dashboard for reviewing/approving requests. See
  [dashboard/README.md](dashboard/README.md).
- **[docs/API_CONTRACT.md](docs/API_CONTRACT.md)** — the contract between agent and backend,
  including the exact signed-token byte layout, **and an explicit compatibility notice**: the
  agent and backend were built against two different versions of this contract and are not
  wire-compatible as they stand today — reconciling them is a follow-up task, not yet done. (The
  dashboard talks to the backend's actual, current contract and has no such mismatch.)

## Architecture

```
                    ┌─────────────────────────┐
 Explorer  ───verb──▶   ElevateGate.Tray.exe   │  (user session, WinForms)
 right-click        │  - file picker + reason  │
                    └────────────┬─────────────┘
                                 │ named pipe (ACL + client identity checked)
                                 ▼
                    ┌─────────────────────────┐        HTTPS       ┌──────────┐
                    │  ElevateGate.Service.exe │ ◀─────────────────▶ Backend  │
                    │  (Windows Service,       │   enroll / submit /          │
                    │   LocalSystem)           │   poll decisions             │
                    └────────────┬─────────────┘                   └──────────┘
                                 │ Process.Start (verified path only)
                                 ▼
                       the approved installer
```

| Project | What it is |
|---|---|
| `src/ElevateGate.Core` | Pure logic: models, path/token validation, hashing, Ed25519 verification, pipe protocol. No OS-specific I/O — runs and tests on any OS. |
| `src/ElevateGate.Infrastructure` | SQLite-backed nonce ledger + audit log, HTTP client for the backend API. Cross-platform. |
| `src/ElevateGate.Service` | The Windows Service: enrollment, named pipe server, Authenticode inspection, DPAPI credential storage, backend polling, and the `ExecutionEngine` — the only place a process is ever started. Windows-only. |
| `src/ElevateGate.Tray` | WinForms tray app in the user's session: file picker, reason form, status display, notifications. Windows-only. |
| `tools/shell-integration` | PowerShell scripts to add/remove the "Request IT Approval" Explorer verb. |
| `tools/install` | PowerShell scripts to publish, install, register, and uninstall the agent. |
| `tests/` | xUnit tests for the security-critical logic in Core and Infrastructure. |
| `backend/` | FastAPI + PostgreSQL backend: enrollment, elevation-request review/approve/deny, Ed25519-signed approvals, admin auth/RBAC. See [backend/README.md](backend/README.md). |
| `dashboard/` | Next.js dashboard for admins: review/approve/deny requests, devices, audit logs. Token never reaches the browser (httpOnly-cookie BFF proxy). See [dashboard/README.md](dashboard/README.md). |

## Documentation

- [docs/INSTALL.md](docs/INSTALL.md) — installing the agent on a Windows machine.
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — building/testing the agent, and the macOS/Windows
  testing split (it was developed and unit-tested on macOS; see that doc for exactly what that
  does and doesn't cover).
- [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) — the agent's assets, trust boundaries, threats and mitigations.
- [docs/BACKEND_THREAT_MODEL.md](docs/BACKEND_THREAT_MODEL.md) — the backend's, including the
  concurrent-approval race prevention and the signing key handling.
- [docs/API_CONTRACT.md](docs/API_CONTRACT.md) — the actual, implemented backend HTTP contract,
  the exact signed-token byte layout, and the agent/backend compatibility notice.
- [backend/README.md](backend/README.md) — running the backend locally, with Docker, and its tests.

## What this agent will never do

- Accept or execute an arbitrary shell command, script, or command line from the backend, the
  tray, or anywhere else.
- Expose a generic "run as admin" / elevate-any-process function.
- Handle, store, or transmit an administrator (or any) password.
- Execute a file whose SHA-256 doesn't match what a human approved, recomputed at the moment of
  execution, not at request time.
