#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Builds, publishes, and installs ElevateGate Agent (service + tray) on this machine.

.DESCRIPTION
    1. Publishes ElevateGate.Service and ElevateGate.Tray (framework-dependent, win-x64) to
       $InstallDir.
    2. Writes the backend URL and pinned Ed25519 server public key into the service's
       appsettings.json.
    3. Registers the Windows Service (LocalSystem, automatic start) and starts it.
    4. Registers the "Request IT Approval" Explorer context-menu verb.

    Requires the .NET 8 Desktop Runtime to already be installed on this machine (framework-
    dependent deployment) — see docs/INSTALL.md.

.PARAMETER BackendBaseUrl
    Base URL of the backend API, e.g. https://elevategate.keystoneuae.com/

.PARAMETER ServerPublicKeyBase64
    Base64-encoded Ed25519 public key issued by the backend team. This is pinned into local
    config, never fetched over the network — see docs/THREAT_MODEL.md.

.PARAMETER EnrollmentKey
    Pre-shared secret the backend requires (as an X-Enrollment-Key header) to accept a new
    device's enrollment. Sent as a default header on every backend API call - see
    docs/API_CONTRACT.md.
#>
param(
    [Parameter(Mandatory = $true)][string]$BackendBaseUrl,
    [Parameter(Mandatory = $true)][string]$ServerPublicKeyBase64,
    [Parameter(Mandatory = $true)][string]$EnrollmentKey,
    [string]$InstallDir = "$env:ProgramFiles\ElevateGate",
    [string]$ServiceName = "ElevateGateAgent"
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")

Write-Host "Publishing ElevateGate.Service..."
dotnet publish "$repoRoot\src\ElevateGate.Service\ElevateGate.Service.csproj" `
    -c Release -r win-x64 --self-contained false -o $InstallDir
if ($LASTEXITCODE -ne 0) { throw "Publishing ElevateGate.Service failed." }

Write-Host "Publishing ElevateGate.Tray..."
dotnet publish "$repoRoot\src\ElevateGate.Tray\ElevateGate.Tray.csproj" `
    -c Release -r win-x64 --self-contained false -o $InstallDir
if ($LASTEXITCODE -ne 0) { throw "Publishing ElevateGate.Tray failed." }

Write-Host "Configuring appsettings.json..."
$settingsPath = Join-Path $InstallDir "appsettings.json"
$settings = Get-Content $settingsPath -Raw | ConvertFrom-Json
$settings.ElevateGate.BackendBaseUrl = $BackendBaseUrl
$settings.ElevateGate.ServerPublicKeyBase64 = $ServerPublicKeyBase64
$settings.ElevateGate.EnrollmentKey = $EnrollmentKey
$settings.ElevateGate.DataDirectory = "$env:ProgramData\ElevateGate"
$settings.ElevateGate.ExpectedTrayExecutablePath = (Join-Path $InstallDir "ElevateGate.Tray.exe")
$settings | ConvertTo-Json -Depth 10 | Set-Content $settingsPath

$existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existingService) {
    Write-Host "Stopping existing service..."
    Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
    sc.exe delete $ServiceName | Out-Null
    Start-Sleep -Seconds 2
}

Write-Host "Registering Windows Service '$ServiceName' (LocalSystem, automatic start)..."
$serviceBinaryPath = Join-Path $InstallDir "ElevateGate.Service.exe"
# Must be quoted: the default install path ("C:\Program Files\ElevateGate\...") contains a
# space, and the Service Control Manager otherwise misparses it as "C:\Program" plus arguments.
New-Service -Name $ServiceName `
    -BinaryPathName "`"$serviceBinaryPath`"" `
    -DisplayName "ElevateGate Agent" `
    -Description "Endpoint privilege-approval agent. Verifies signed IT approvals before running a requested installer." `
    -StartupType Automatic | Out-Null

Start-Service -Name $ServiceName
Write-Host "Service started."

Write-Host "Registering Explorer context menu..."
& (Join-Path $PSScriptRoot "..\shell-integration\Register-ContextMenu.ps1") -InstallDir $InstallDir

Write-Host "Registering ElevateGate Tray to start at login (all users)..."
$installedTrayExe = Join-Path $InstallDir "ElevateGate.Tray.exe"
$runKeyPath = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
Set-ItemProperty -Path $runKeyPath -Name "ElevateGateTray" -Value "`"$installedTrayExe`""

# Also launch it right now, in the current interactive session, so the icon shows up immediately
# instead of only after the next login.
Write-Host "Starting ElevateGate Tray..."
Start-Process -FilePath $installedTrayExe

Write-Host ""
Write-Host "ElevateGate Agent installed to $InstallDir."
Write-Host "Local state (audit log, nonce ledger, device credential): $env:ProgramData\ElevateGate"
