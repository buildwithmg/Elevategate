#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Adds the "Request IT Approval" verb to the Explorer context menu for .exe and .msi files.

.DESCRIPTION
    Registers a registry shell verb (not a COM shell extension) on the exefile and Msi.Package
    ProgIDs. Selecting the verb launches ElevateGate.Tray.exe with the clicked file's path as its
    only argument — the tray app treats that path purely as a hint and the service re-validates
    it from scratch, so this registration carries no elevated trust of its own.

.PARAMETER InstallDir
    Directory containing ElevateGate.Tray.exe. Defaults to the standard install location.
#>
param(
    [string]$InstallDir = "$env:ProgramFiles\ElevateGate"
)

$ErrorActionPreference = "Stop"

$trayExePath = Join-Path $InstallDir "ElevateGate.Tray.exe"
if (-not (Test-Path $trayExePath)) {
    Write-Warning "ElevateGate.Tray.exe not found at '$trayExePath'. Registering anyway; run this again (or re-run Install-ElevateGate.ps1) after the tray app is deployed there."
}

function Register-Verb {
    param([string]$ProgId)

    $verbKey = "Registry::HKEY_LOCAL_MACHINE\SOFTWARE\Classes\$ProgId\shell\ElevateGateRequest"
    New-Item -Path $verbKey -Force | Out-Null
    Set-ItemProperty -Path $verbKey -Name "MUIVerb" -Value "Request IT Approval"
    Set-ItemProperty -Path $verbKey -Name "Icon" -Value "`"$trayExePath`",0"

    $commandKey = Join-Path $verbKey "command"
    New-Item -Path $commandKey -Force | Out-Null
    Set-ItemProperty -Path $commandKey -Name "(default)" -Value "`"$trayExePath`" `"%1`""

    Write-Host "Registered 'Request IT Approval' verb on $ProgId."
}

Register-Verb -ProgId "exefile"
Register-Verb -ProgId "Msi.Package"

Write-Host "Done. Right-click an .exe or .msi file in Explorer to see 'Request IT Approval'."
