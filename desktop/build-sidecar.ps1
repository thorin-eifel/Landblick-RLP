<#
.SYNOPSIS
  Baut den Python-Dienst (app/desktop.py) als Einzeldatei und legt ihn samt pmtiles-CLI als Tauri-Sidecar ab (Windows).
.DESCRIPTION
  Gegenstück zu desktop/build-sidecar.sh für Windows, ohne bash, rsync und unzip. Baut für das System, auf dem es läuft.
  Danach: cd desktop; npm install --include=dev; npx tauri build --bundles nsis
.PARAMETER PmtilesVersion
  Version der go-pmtiles-CLI (github.com/protomaps/go-pmtiles/releases), Standard 1.31.2.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File desktop\build-sidecar.ps1
#>
[CmdletBinding()]
param([string]$PmtilesVersion = '1.31.2')
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Invoke-Checked {
    param([string]$What, [scriptblock]$Block)
    & $Block
    if ($LASTEXITCODE -ne 0) { throw "$What fehlgeschlagen (Exit $LASTEXITCODE)" }
}

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Bin = Join-Path $Root 'desktop\src-tauri\binaries'
$Triple = ((& rustc -vV) | Where-Object { $_ -like 'host:*' }) -replace '^host:\s*', ''
if (-not $Triple) { throw 'rustc fehlt (Zielplattform unbekannt)' }
if ($Triple -ne 'x86_64-pc-windows-msvc') { throw "Plattform $Triple nicht vorgesehen (nur x86_64-pc-windows-msvc)" }
New-Item -ItemType Directory -Force -Path $Bin | Out-Null

$Work = Join-Path ([IO.Path]::GetTempPath()) ("landblick-sidecar-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $Work | Out-Null
try {
    Write-Verbose "Arbeitsordner $Work"
    $py = (Get-Command python -ErrorAction Stop).Source
    Invoke-Checked 'venv' { & $py -m venv (Join-Path $Work 'venv') }
    $vpy = Join-Path $Work 'venv\Scripts\python.exe'
    Invoke-Checked 'pip install' { & $vpy -m pip install -q -r (Join-Path $Root 'requirements.txt') 'pyinstaller==6.*' }

    # Weboberfläche ohne Beispieldaten und ohne Höhenkacheln
    $web = Join-Path $Work 'web'
    & robocopy (Join-Path $Root 'web') $web /E /NFL /NDL /NJH /NJS /NP /XD (Join-Path $Root 'web\data') (Join-Path $Root 'web\tiles') | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy fehlgeschlagen (Exit $LASTEXITCODE)" }
    $global:LASTEXITCODE = 0

    Push-Location $Root
    try {
        Invoke-Checked 'PyInstaller' {
            & $vpy -m PyInstaller --onefile --name osint-core --distpath (Join-Path $Work 'dist') --workpath (Join-Path $Work 'build') --specpath $Work `
                --paths $Root --collect-submodules app --collect-data app --collect-data certifi `
                --add-data "$web;web" --add-data "$(Join-Path $Root 'sources.yaml');." --add-data "$(Join-Path $Root 'region.yaml');." app\desktop.py
        }
    } finally { Pop-Location }

    # Rauchtest: das Paket muss Region und Quellenregister finden (fehlende Datendateien fielen sonst erst im Betrieb auf)
    $exe = Join-Path $Work 'dist\osint-core.exe'
    $env:OSINT_NO_DOTENV = '1'
    Push-Location $Work
    try { Invoke-Checked 'Rauchtest app.region' { & $exe --run app.region | Out-Null } } finally { Pop-Location; Remove-Item Env:\OSINT_NO_DOTENV -ErrorAction SilentlyContinue }
    Copy-Item $exe (Join-Path $Bin "osint-core-$Triple.exe") -Force

    # pmtiles-CLI (go-pmtiles)
    $asset = "go-pmtiles_${PmtilesVersion}_Windows_x86_64.zip"
    $zip = Join-Path $Work 'pm.zip'
    Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/protomaps/go-pmtiles/releases/download/v$PmtilesVersion/$asset" -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath (Join-Path $Work 'pm') -Force
    $pm = Get-ChildItem (Join-Path $Work 'pm') -Recurse -Filter 'pmtiles.exe' | Select-Object -First 1
    if (-not $pm) { throw 'pmtiles.exe nicht im Archiv gefunden (Version/Name prüfen)' }
    Copy-Item $pm.FullName (Join-Path $Bin "pmtiles-$Triple.exe") -Force
    Write-Output "fertig: $Bin"
    Get-ChildItem $Bin | Format-Table Name, Length
} finally {
    Remove-Item -Recurse -Force $Work -ErrorAction SilentlyContinue
}
