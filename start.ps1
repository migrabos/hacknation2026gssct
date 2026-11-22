# Retencja - lokalny start API + Web (Windows PowerShell 5.1+).
# Plik celowo tylko ASCII: PowerShell 5.1 czyta .ps1 bez BOM jako ANSI.
# Zwykle uruchamiany przez start.bat.
$ErrorActionPreference = "Stop"

function Log($m)  { Write-Host "[retencja] $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "[ok]       $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[uwaga]    $m" -ForegroundColor Yellow }
function Die($m)  { Write-Host "[blad]     $m" -ForegroundColor Red; Read-Host "Enter aby zamknac"; exit 1 }

$Root    = $PSScriptRoot
$ApiDir  = Join-Path $Root "apps\api"
$WebDir  = Join-Path $Root "apps\web"
$ApiPort = 8000
$WebPort = 3000

Write-Host "Retencja - start lokalny (Windows)" -ForegroundColor White

# --- narzedzia ------------------------------------------------
$Py = $null
foreach ($c in @("py", "python")) {
    if (Get-Command $c -ErrorAction SilentlyContinue) {
        $pyArgs = if ($c -eq "py") { @("-3", "-c") } else { @("-c") }
        # try/catch: atrapa "python" ze Sklepu MS pisze na stderr, co przy "Stop" przerwaloby skrypt
        $good = $false
        try {
            & $c @pyArgs "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
            $good = ($LASTEXITCODE -eq 0)
        } catch {}
        if ($good) { $Py = $c; break }
    }
}
if (-not $Py) { Die "Potrzebny Python 3.11+ z python.org (zaznacz 'Add python.exe to PATH')." }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Die "Potrzebny Node.js 20+ z nodejs.org." }
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { Die "Brak npm (instaluje sie razem z Node.js)." }
Ok ("Python: " + (& $Py --version 2>&1) + " / Node: " + (node --version))

# --- porty: probne zajecie portu (tak jak zrobi to serwer) ---------
# Wykrywa tez porty zarezerwowane przez Hyper-V/WSL (netsh int ipv4 show excludedportrange protocol=tcp).
function PortFree($p) {
    try {
        $l = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $p)
        $l.Start(); $l.Stop(); return $true
    } catch { return $false }
}
function PickPort($start) {
    for ($p = $start; $p -le $start + 20; $p++) { if (PortFree $p) { return $p } }
    return $null
}
$WantApi = $ApiPort; $WantWeb = $WebPort
$ApiPort = PickPort $WantApi
if (-not $ApiPort) { Die "Brak wolnego portu dla API w zakresie $WantApi-$($WantApi + 20)." }
$WebPort = PickPort $WantWeb
if (-not $WebPort) { Die "Brak wolnego portu dla frontendu w zakresie $WantWeb-$($WantWeb + 20)." }
if ($ApiPort -ne $WantApi) { Warn "Port $WantApi niedostepny - API wystartuje na $ApiPort" }
if ($WebPort -ne $WantWeb) { Warn "Port $WantWeb niedostepny - frontend wystartuje na $WebPort" }

# Frontend musi znac port API, a API musi wpuscic frontend z jego portu (env ma pierwszenstwo przed .env).
# Start-Process dziedziczy te zmienne.
$env:NEXT_PUBLIC_API_URL = "http://localhost:$ApiPort"
if ($WebPort -ne $WantWeb) { $env:CORS_ORIGINS = "http://localhost:$WebPort,http://127.0.0.1:$WebPort" }

# --- pliki .env -----------------------------------------------
if (-not (Test-Path "$ApiDir\.env"))       { Copy-Item "$ApiDir\.env.example" "$ApiDir\.env";       Warn "Utworzono apps\api\.env z przykladu" }
if (-not (Test-Path "$WebDir\.env.local")) { Copy-Item "$WebDir\.env.example" "$WebDir\.env.local"; Warn "Utworzono apps\web\.env.local z przykladu" }

# --- Python venv + zaleznosci ---------------------------------
$Venv  = Join-Path $ApiDir ".venv"
$VPy   = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $Venv)) {
    Log "Tworze srodowisko Python (.venv) ..."
    if ($Py -eq "py") { & py -3 -m venv $Venv } else { & python -m venv $Venv }
}
if (-not (Test-Path $VPy)) { Die "apps\api\.venv pochodzi z innego systemu (np. WSL). Usun ten katalog i uruchom ponownie." }
$Stamp = Join-Path $Venv ".installed"
$Req   = Join-Path $ApiDir "requirements.txt"
if (-not (Test-Path $Stamp) -or (Get-Item $Req).LastWriteTime -gt (Get-Item $Stamp).LastWriteTime) {
    Log "Instaluje zaleznosci Python (pierwszy raz trwa kilka minut) ..."
    & $VPy -m pip install -q --upgrade pip
    & $VPy -m pip install -q -r $Req
    if ($LASTEXITCODE -ne 0) { Die "Instalacja zaleznosci Python nie powiodla sie." }
    New-Item -ItemType File -Force $Stamp | Out-Null
}

# --- npm ------------------------------------------------------
$Lock    = Join-Path $WebDir "package-lock.json"
$NmLock  = Join-Path $WebDir "node_modules\.package-lock.json"
if (-not (Test-Path $NmLock) -or (Get-Item $Lock).LastWriteTime -gt (Get-Item $NmLock).LastWriteTime) {
    Log "Instaluje paczki npm ..."
    Push-Location $WebDir; & npm.cmd install; $code = $LASTEXITCODE; Pop-Location
    if ($code -ne 0) { Die "npm install nie powiodl sie." }
}

# --- start ----------------------------------------------------
function StopTree($proc) {
    # /T zamyka tez procesy potomne (uvicorn --reload, node); blad = proces juz nie zyje
    try { & taskkill.exe /PID $proc.Id /T /F 2>&1 | Out-Null } catch {}
}

Log "Startuje API (port $ApiPort) - log: api.log / api.err.log"
$Api = Start-Process -FilePath $VPy -WorkingDirectory $ApiDir -PassThru -WindowStyle Hidden `
    -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port $ApiPort --reload" `
    -RedirectStandardOutput "$Root\api.log" -RedirectStandardError "$Root\api.err.log"

$up = $false
for ($i = 0; $i -lt 40; $i++) {
    try { Invoke-WebRequest "http://127.0.0.1:$ApiPort/health" -UseBasicParsing -TimeoutSec 2 | Out-Null; $up = $true; break } catch { Start-Sleep 1 }
}
if (-not $up) { StopTree $Api; Die "API nie wstalo w 40 s - zobacz api.err.log" }
Ok "API: http://localhost:$ApiPort/docs"

Log "Startuje frontend (port $WebPort) - log: web.log / web.err.log"
$Web = Start-Process -FilePath "cmd.exe" -WorkingDirectory $WebDir -PassThru -WindowStyle Hidden `
    -ArgumentList "/c npm.cmd run dev -- --port $WebPort" `
    -RedirectStandardOutput "$Root\web.log" -RedirectStandardError "$Root\web.err.log"

for ($i = 0; $i -lt 90; $i++) {
    try { Invoke-WebRequest "http://127.0.0.1:$WebPort" -UseBasicParsing -TimeoutSec 2 | Out-Null; break } catch {
        if ($_.Exception.Response) { break }
        Start-Sleep 1
    }
}

$Url = "http://localhost:$WebPort"
Write-Host ""
Write-Host "Gotowe -> $Url" -ForegroundColor White
Start-Process $Url
Read-Host "Nacisnij Enter, aby zatrzymac API i frontend"

StopTree $Api
StopTree $Web
Ok "Zatrzymano."
