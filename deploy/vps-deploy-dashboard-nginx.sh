#!/usr/bin/env bash
# Run ON THE VPS from the watchmatch repo (clone or pull first).
# Prefer: run Docker as your login user, then nginx steps with sudo.
#
#   export WATCHMATCH_DIR=/path/to/watchmatch
#   export NGINX_SITE_FILE=/etc/nginx/sites-available/brimit.de   # optional; auto-detect brimit.de
#   bash deploy/vps-deploy-dashboard-nginx.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${WATCHMATCH_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
cd "$REPO"

echo "==> repo: $REPO"

run_docker() {
  if [[ "${EUID:-0}" -eq 0 && -n "${SUDO_USER:-}" ]]; then
    sudo -u "$SUDO_USER" -H bash -lc "cd $(printf '%q' "$REPO") && docker compose build dashboard && docker compose --profile dashboard up -d"
  else
    docker compose build dashboard
    docker compose --profile dashboard up -d
  fi
}

echo "==> build + start dashboard (Docker)"
run_docker

echo "==> check dashboard on loopback"
code="$(curl -sf -o /dev/null -w "%{http_code}" http://127.0.0.1:3000/ || true)"
if echo "$code" | grep -qE '^(200|307|304)$'; then
  echo "dashboard OK on :3000 (HTTP $code)"
else
  echo "WARNING: http://127.0.0.1:3000/ returned ${code:-fail} — check: docker compose --profile dashboard ps"
fi

SNIPPET_SRC="$SCRIPT_DIR/snippets/watchmatch-root-dashboard.conf"
SNIPPET_DST="/etc/nginx/snippets/watchmatch-root-dashboard.conf"

echo "==> install nginx snippet -> $SNIPPET_DST (needs sudo)"
sudo install -d /etc/nginx/snippets
sudo install -m 644 "$SNIPPET_SRC" "$SNIPPET_DST"

SITE_FILE="${NGINX_SITE_FILE:-}"
if [[ -z "$SITE_FILE" ]]; then
  # Prefer sites-enabled symlink target or first file mentioning brimit
  if compgen -G "/etc/nginx/sites-enabled/*" >/dev/null; then
    SITE_FILE="$(grep -l "brimit\\.de" /etc/nginx/sites-enabled/* 2>/dev/null | head -1 || true)"
  fi
fi
if [[ -z "$SITE_FILE" || ! -f "$SITE_FILE" ]]; then
  echo "Set NGINX_SITE_FILE to your vhost path, e.g.:"
  echo "  export NGINX_SITE_FILE=/etc/nginx/sites-available/brimit.de"
  echo "Then re-run this script, or manually add inside the HTTPS server { }:  include $SNIPPET_DST;"
  exit 1
fi

echo "==> patch nginx vhost: $SITE_FILE"
sudo python3 "$SCRIPT_DIR/nginx_patch_root_to_dashboard.py" "$SITE_FILE"

echo "==> nginx test + reload"
sudo nginx -t
sudo systemctl reload nginx

echo "Done. Open https://www.brimit.de/ (HTML) and keep https://www.brimit.de/api/v1/... (JSON)."
