#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Installs ElevateGate Agent (service + tray) from a pre-built release package - no .NET SDK,
    no repo clone, no build step. Companion to Install-ElevateGate.ps1, which builds from source
    for developers; this script is what ships inside the release zip for end users.

.DESCRIPTION
    Expects ElevateGate.Service.exe, ElevateGate.Tray.exe, and appsettings.json to already exist
    alongside this script (that's what the release zip contains - both exes are self-contained
    single-file publishes, so the target machine needs no .NET runtime at all).

    1. Copies the pre-built exes + appsettings.json to $InstallDir.
    2. Fills in the enrollment key (the only value not already baked into the shipped
       appsettings.json, since it's a secret - BackendBaseUrl/ServerPublicKeyBase64 aren't).
    3. Registers the Windows Service (LocalSystem, automatic start) and starts it.
    4. Registers the "Request IT Approval" Explorer context-menu verb.

.PARAMETER EnrollmentKey
    Pre-shared secret the backend requires (as an X-Enrollment-Key header) to accept a new
    device's enrollment.
#>
param(
    [Parameter(Mandatory = $true)][string]$EnrollmentKey,
    [string]$InstallDir = "$env:ProgramFiles\ElevateGate",
    [string]$ServiceName = "ElevateGateAgent"
)

$ErrorActionPreference = "Stop"

$serviceExe = Join-Path $PSScriptRoot "ElevateGate.Service.exe"
$trayExe = Join-Path $PSScriptRoot "ElevateGate.Tray.exe"
$settingsSource = Join-Path $PSScriptRoot "appsettings.json"
foreach ($required in @($serviceExe, $trayExe, $settingsSource)) {
    if (-not (Test-Path $required)) { throw "Expected release file not found: $required" }
}

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

Write-Host "Copying ElevateGate.Service.exe and ElevateGate.Tray.exe to $InstallDir..."
Copy-Item $serviceExe (Join-Path $InstallDir "ElevateGate.Service.exe") -Force
Copy-Item $trayExe (Join-Path $InstallDir "ElevateGate.Tray.exe") -Force

Write-Host "Configuring appsettings.json..."
$settingsPath = Join-Path $InstallDir "appsettings.json"
$settings = Get-Content $settingsSource -Raw | ConvertFrom-Json
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
$contextMenuScript = Join-Path $PSScriptRoot "Register-ContextMenu.ps1"
& $contextMenuScript -InstallDir $InstallDir

Write-Host ""
Write-Host "ElevateGate Agent installed to $InstallDir."
Write-Host "Local state (audit log, nonce ledger, device credential): $env:ProgramData\ElevateGate"
