<#
.SYNOPSIS
  Landblick - RLP: Installer für Windows (Start von install.py mit passendem Python).

.DESCRIPTION
  Sucht Python ab 3.11 (Startprogramm 'py' oder 'python') und ruft install.py auf. Der Installer richtet .venv, .env,
  die erste Datensammlung, den lokalen Webserver und die Aufgaben in der Windows-Aufgabenplanung ein (Ordner "Landblick"),
  darunter die R6-Jobs für Sicherung, Gesundheitsprüfung und Dauerlauf-Proben.

.PARAMETER Kontakt          Absender im User-Agent der Abrufe (Pflicht beim ersten Lauf).
.PARAMETER Karte            'keine' (Standard) oder 'voll' (Basiskarte laden, rund 1,5 GB).
.PARAMETER Port             Port des Webservers (Standard 8080).
.PARAMETER Bind             Adresse des Webservers (Standard 127.0.0.1).
.PARAMETER Dauerlauf        Proben für das R6-Protokoll alle 10 Minuten.
.PARAMETER System           Aufgaben für den ganzen Rechner, laufen ohne Anmeldung (als Administrator starten).
.PARAMETER RuhezustandAus   Standby im Netzbetrieb abschalten.
.PARAMETER OhneLive         Livemodul (Luftverkehr) nicht einrichten.
.PARAMETER OhneErstlauf     Keine erste Datensammlung jetzt.
.PARAMETER Ja               Rückfragen mit Ja beantworten.
.PARAMETER Status           Zustand der Aufgaben und Gesundheitsprüfung zeigen.
.PARAMETER Deinstall        Aufgaben entfernen (Daten bleiben).
.PARAMETER PythonInstallieren  Fehlt Python, per winget installieren (Python 3.12).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File install.ps1 -Kontakt name@example.org -Dauerlauf -RuhezustandAus
#>
[CmdletBinding()]
param(
  [string]$Kontakt, [ValidateSet('keine','voll')][string]$Karte = 'keine', [int]$Port = 8080, [string]$Bind = '127.0.0.1',
  [switch]$Dauerlauf, [switch]$System, [switch]$RuhezustandAus, [switch]$OhneLive, [switch]$OhneErstlauf,
  [switch]$Ja, [switch]$Status, [switch]$Deinstall, [switch]$PythonInstallieren, [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

function Find-Python {
  foreach ($cand in @(@('py','-3.13'), @('py','-3.12'), @('py','-3.11'), @('python'), @('python3'))) {
    $exe = $cand[0]
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
    $extra = @(); if ($cand.Count -gt 1) { $extra = $cand[1..($cand.Count-1)] }
    & $exe @extra -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) { return ,(@($exe) + $extra) }
  }
  return $null
}

$py = Find-Python
if (-not $py -and $PythonInstallieren) {
  Write-Verbose 'Python fehlt, installiere per winget (Python.Python.3.12)'
  winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
  Write-Warning 'Python wurde installiert. Dieses Fenster schließen, ein neues öffnen und install.ps1 erneut starten (PATH).'
  exit 1
}
if (-not $py) {
  Write-Error 'Python 3.11 oder neuer nicht gefunden. Installieren (winget install -e --id Python.Python.3.12) oder install.ps1 mit -PythonInstallieren starten.'
  exit 1
}

if ($System) {
  $admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
  if (-not $admin) { Write-Error '-System braucht ein Administrator-Fenster.'; exit 1 }
}

$argsList = @('install.py', '--port', "$Port", '--bind', $Bind, '--karte', $Karte)
if ($Kontakt)            { $argsList += @('--kontakt', $Kontakt) }
if ($Dauerlauf)          { $argsList += '--dauerlauf' }
if ($System)             { $argsList += '--system' }
if ($RuhezustandAus)     { $argsList += '--ruhezustand-aus' }
if ($OhneLive)           { $argsList += '--ohne-live' }
if ($OhneErstlauf)       { $argsList += '--ohne-erstlauf' }
if ($Ja)                 { $argsList += '--ja' }
if ($Status)             { $argsList += '--status' }
if ($Deinstall)          { $argsList += '--deinstall' }
if ($DryRun)             { $argsList += '--dry-run' }

$extra = @(); if ($py.Count -gt 1) { $extra = $py[1..($py.Count-1)] }
& $py[0] @extra @argsList
exit $LASTEXITCODE
