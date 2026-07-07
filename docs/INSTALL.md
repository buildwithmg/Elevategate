# Installing ElevateGate Agent

## Prerequisites

- Windows 10/11 or Windows Server, x64.
- [.NET 8 Desktop Runtime](https://dotnet.microsoft.com/download/dotnet/8.0) installed on the
  target machine (the install script publishes framework-dependent, not self-contained).
- Administrator rights on the target machine (installs a service and writes to
  `HKEY_LOCAL_MACHINE`).
- A reachable backend implementing [API_CONTRACT.md](API_CONTRACT.md), and its Ed25519 public key
  (base64-encoded).

## Install

From an elevated PowerShell prompt, from the repo root:

```powershell
.\tools\install\Install-ElevateGate.ps1 `
    -BackendBaseUrl "https://elevategate.keystone.ae/" `
    -ServerPublicKeyBase64 "<base64 Ed25519 public key from the backend team>" `
    -EnrollmentKey "<pre-shared enrollment key from the backend team>"
```

This will:

1. Publish `ElevateGate.Service` and `ElevateGate.Tray` (framework-dependent, `win-x64`) to
   `%ProgramFiles%\ElevateGate`.
2. Write the backend URL and pinned public key into
   `%ProgramFiles%\ElevateGate\appsettings.json`.
3. Register and start the `ElevateGateAgent` Windows Service (Local System, automatic start).
4. Register the "Request IT Approval" Explorer context-menu verb for `.exe` and `.msi` files.

Optional parameters: `-InstallDir` (default `%ProgramFiles%\ElevateGate`), `-ServiceName`
(default `ElevateGateAgent`).

## Verify

- `Get-Service ElevateGateAgent` should show `Running`.
- Local state lives under `%ProgramData%\ElevateGate`: `device-credential.json` (DPAPI-protected
  bearer token), `nonces.db`, `audit.db`, and `logs\elevategate-*.log`.
- Right-click any `.exe` or `.msi` file in Explorer — "Request IT Approval" should appear and
  launch the tray with that file pre-selected.
- The tray also runs standalone (Start Menu / a scheduled task / a login script, depending on how
  you choose to launch it for the logged-in user) and shows a shield icon in the system tray.

## Uninstall

```powershell
.\tools\install\Uninstall-ElevateGate.ps1
```

Add `-KeepData` to preserve `%ProgramData%\ElevateGate` (audit log, nonce ledger, device
credential) instead of deleting it.

## Configuration reference

`%ProgramFiles%\ElevateGate\appsettings.json`, under the `ElevateGate` section:

| Setting | Meaning |
|---|---|
| `BackendBaseUrl` | Base URL of the backend API |
| `ServerPublicKeyBase64` | Pinned Ed25519 public key used to verify every approval token |
| `EnrollmentKey` | Sent as `X-Enrollment-Key` on every backend call — gates enrollment |
| `PollingIntervalSeconds` | How often the service polls the backend for decisions (default 15) |
| `DataDirectory` | Where local state lives (default `%ProgramData%\ElevateGate`) |
| `PipeName` | Named pipe the tray connects to (default `ElevateGate.Agent`) |
| `ExpectedTrayExecutablePath` | Exact path the connecting tray process must match |
| `RequestTimeToLiveMinutes` | How long a pending request is tracked locally |

Changing `PipeName` or `ExpectedTrayExecutablePath` requires the tray and service to agree — if
you relocate the install directory manually instead of via the install script, update
`ExpectedTrayExecutablePath` to match.
