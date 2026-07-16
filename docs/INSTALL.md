# Installing ElevateGate Agent

## Prerequisites

- Windows 10/11 or Windows Server, x64.
- Administrator rights on the target machine (installs a service and writes to
  `HKEY_LOCAL_MACHINE`).
- The enrollment key for the backend you're pointing at (ask whoever runs it). The backend URL and
  its pinned Ed25519 public key are already baked into the release — see
  [API_CONTRACT.md](API_CONTRACT.md) for what those mean.

## Install (one line, recommended)

From **any** PowerShell prompt (it re-launches itself elevated if needed):

```powershell
irm https://raw.githubusercontent.com/buildwithmg/Elevategate/main/install.ps1 | iex
```

This downloads the latest pre-built release (self-contained — **no .NET runtime install
required**), prompts once for the enrollment key, and installs everything. Set
`$env:ELEVATEGATE_ENROLLMENT_KEY` beforehand to skip the prompt (e.g. in an unattended/scripted
deployment).

What it does:

1. Downloads the latest `ElevateGate-Agent-*-win-x64.zip` release asset (built via
   `dotnet publish -r win-x64 --self-contained true -p:PublishSingleFile=true`) and extracts it.
2. Copies `ElevateGate.Service.exe`/`ElevateGate.Tray.exe` to `%ProgramFiles%\ElevateGate`.
3. Fills in the enrollment key in `appsettings.json` (backend URL and public key are already set).
4. Registers and starts the `ElevateGateAgent` Windows Service (Local System, automatic start).
5. Registers the "Request IT Approval" Explorer context-menu verb for `.exe` and `.msi` files.
6. Registers `ElevateGate.Tray.exe` to launch at login for any user (`HKLM\...\CurrentVersion\Run`)
   and starts it immediately in the current session, so the tray icon appears right away.

## Install from source (for development)

If you're working on the agent itself rather than just installing it, build and install from a
local clone instead — this is a framework-dependent build, so it does need the
[.NET 8 Desktop Runtime](https://dotnet.microsoft.com/download/dotnet/8.0) on the target machine:

```powershell
.\tools\install\Install-ElevateGate.ps1 `
    -BackendBaseUrl "https://elevategate.keystone.ae/" `
    -ServerPublicKeyBase64 "<base64 Ed25519 public key from the backend team>" `
    -EnrollmentKey "<pre-shared enrollment key from the backend team>"
```

Optional parameters on either script: `-InstallDir` (default `%ProgramFiles%\ElevateGate`),
`-ServiceName` (default `ElevateGateAgent`).

## Verify

- `Get-Service ElevateGateAgent` should show `Running`.
- Local state lives under `%ProgramData%\ElevateGate`: `device-credential.json` (DPAPI-protected
  bearer token), `nonces.db`, `audit.db`, and `logs\elevategate-*.log`.
- Right-click any `.exe` or `.msi` file in Explorer — "Request IT Approval" should appear and
  launch the tray with that file pre-selected.
- The tray icon should already be visible in the system tray immediately after install (it's
  started right away, and registered to auto-start at login for any user from then on — see
  `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Run\ElevateGateTray`). Only one instance ever
  runs per user session — a second launch (e.g. via the context-menu verb) hands off to the
  already-running icon instead of spawning a duplicate.

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
