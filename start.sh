#!/usr/bin/env bash
# Retencja - lokalny start API + Web (Linux, macOS, WSL, Git Bash).
# Na czystym Windowsie uzyj start.bat.
set -uo pipefail

if [ -t 1 ]; then
  GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BOLD='\033[1m'; RESET='\033[0m'
else
  GREEN=''; CYAN=''; YELLOW=''; RED=''; BOLD=''; RESET=''
fi
log()  { echo -e "${CYAN}[retencja]${RESET} $*"; }
ok()   { echo -e "${GREEN}[ok]${RESET}       $*"; }
warn() { echo -e "${YELLOW}[uwaga]${RESET}    $*"; }
die()  { echo -e "${RED}[błąd]${RESET}     $*"; exit 1; }

case "$(uname -s)" in
  Linux*)  grep -qi microsoft /proc/version 2>/dev/null && OS=wsl || OS=linux ;;
  Darwin*) OS=mac ;;
  MINGW*|MSYS*|CYGWIN*) OS=windows ;;
  *) OS=unknown ;;
esac

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_DIR="$ROOT/apps/api"
WEB_DIR="$ROOT/apps/web"
API_PORT=8000
WEB_PORT=3000

echo -e "${BOLD}Retencja — start lokalny${RESET}  (system: $OS)"

# --- narzędzia ------------------------------------------------
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
[ -n "$PY" ] || die "Potrzebny Python 3.11+ (python.org)."
command -v node >/dev/null 2>&1 || die "Potrzebny Node.js 20+ (nodejs.org)."
command -v npm  >/dev/null 2>&1 || die "Brak npm (instaluje się razem z Node.js)."
command -v curl >/dev/null 2>&1 || die "Brak curl."
ok "Python: $($PY --version 2>&1) · Node: $(node --version)"

# --- porty wolne? ---------------------------------------------
for p in $API_PORT $WEB_PORT; do
  "$PY" - "$p" <<'PYPORT' || exit 1
import errno
import socket
import sys

port = int(sys.argv[1])
with socket.socket() as sock:
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    else:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("127.0.0.1", port))
        sock.listen()
    except OSError as exc:
        message = "port jest zajęty" if exc.errno == errno.EADDRINUSE else str(exc)
        sys.exit(f"[błąd] Port {port}: {message}")
PYPORT
done

# --- pliki .env -----------------------------------------------
[ -f "$API_DIR/.env" ]       || { cp "$API_DIR/.env.example" "$API_DIR/.env"; warn "Utworzono apps/api/.env z przykładu"; }
[ -f "$WEB_DIR/.env.local" ] || { cp "$WEB_DIR/.env.example" "$WEB_DIR/.env.local"; warn "Utworzono apps/web/.env.local z przykładu"; }

# --- Python venv + zależności (tylko gdy requirements.txt się zmienił) ---
VENV="$API_DIR/.venv"
if [ "$OS" = windows ]; then VBIN="$VENV/Scripts"; else VBIN="$VENV/bin"; fi
if [ ! -d "$VENV" ]; then
  log "Tworzę środowisko Python (.venv) …"
  "$PY" -m venv "$VENV" || die "Nie udało się utworzyć venv (na Debian/Ubuntu: sudo apt install python3-venv)."
fi
[ -x "$VBIN/python" ] || [ -x "$VBIN/python.exe" ] || \
  die "apps/api/.venv pochodzi z innego systemu (np. Windows vs WSL). Usuń ten katalog i uruchom ponownie."
STAMP="$VENV/.installed"
if [ ! -f "$STAMP" ] || [ "$API_DIR/requirements.txt" -nt "$STAMP" ]; then
  log "Instaluję zależności Python (pierwszy raz trwa kilka minut) …"
  "$VBIN/python" -m pip install -q --upgrade pip || die "pip upgrade nie powiódł się"
  "$VBIN/python" -m pip install -q -r "$API_DIR/requirements.txt" || die "Instalacja zależności Python nie powiodła się"
  touch "$STAMP"
fi

# --- npm (tylko gdy brak node_modules albo zmienił się lockfile) ---
if [ ! -d "$WEB_DIR/node_modules" ] || [ "$WEB_DIR/package-lock.json" -nt "$WEB_DIR/node_modules/.package-lock.json" ]; then
  log "Instaluję paczki npm …"
  (cd "$WEB_DIR" && npm install) || die "npm install nie powiódł się"
fi

# --- start ----------------------------------------------------
cleanup() {
  trap - INT TERM EXIT
  echo; log "Zatrzymuję API i frontend …"
  kill 0 2>/dev/null
}
trap cleanup INT TERM EXIT

log "Startuję API (port $API_PORT) — log: api.log"
(cd "$API_DIR" && exec "$VBIN/python" -m uvicorn app.main:app --host 127.0.0.1 --port "$API_PORT" --reload) >"$ROOT/api.log" 2>&1 &

for i in $(seq 1 40); do
  curl -sf --max-time 2 "http://127.0.0.1:$API_PORT/health" >/dev/null 2>&1 && break
  [ "$i" -eq 40 ] && { tail -n 20 "$ROOT/api.log"; die "API nie wstało w 40 s (pełny log: api.log)"; }
  sleep 1
done
ok "API: http://localhost:$API_PORT/docs"

log "Startuję frontend (port $WEB_PORT) — log: web.log"
(cd "$WEB_DIR" && exec npm run dev -- --port "$WEB_PORT") >"$ROOT/web.log" 2>&1 &

for i in $(seq 1 90); do
  curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$WEB_PORT" && break
  [ "$i" -eq 90 ] && warn "Frontend jeszcze się kompiluje — sprawdź web.log"
  sleep 1
done

URL="http://localhost:$WEB_PORT"
echo -e "\n${BOLD}Gotowe → $URL${RESET}   (Ctrl+C zatrzymuje wszystko)\n"
case "$OS" in
  linux)   command -v xdg-open >/dev/null && xdg-open "$URL" >/dev/null 2>&1 & ;;
  mac)     open "$URL" ;;
  wsl)     cmd.exe /c start "$URL" >/dev/null 2>&1 ;;
  windows) start "$URL" ;;
esac

wait
