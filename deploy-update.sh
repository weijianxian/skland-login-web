#!/usr/bin/env bash
set -euo pipefail

APP_NAME="skland-login-web"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
else
  echo "[ERROR] Neither 'docker compose' nor 'docker-compose' is available."
  exit 1
fi

if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  BUILD_COMMIT="$(git rev-parse --short=12 HEAD)"
else
  BUILD_COMMIT="manual-$(date +%Y%m%d%H%M)"
fi

if [ -f .env ]; then
  if grep -q '^BUILD_COMMIT=' .env; then
    sed -i "s/^BUILD_COMMIT=.*/BUILD_COMMIT=${BUILD_COMMIT}/" .env
  else
    printf '\nBUILD_COMMIT=%s\n' "${BUILD_COMMIT}" >> .env
  fi
else
  printf 'BUILD_COMMIT=%s\n' "${BUILD_COMMIT}" > .env
fi

echo "[INFO] BUILD_COMMIT=${BUILD_COMMIT}"
echo "[INFO] Pulling latest code..."
git pull --ff-only || true

echo "[INFO] Rebuilding and recreating containers..."
$COMPOSE_CMD up -d --build --force-recreate

echo "[INFO] Service status:"
$COMPOSE_CMD ps

echo "[INFO] Last 80 log lines:"
$COMPOSE_CMD logs --tail=80 "${APP_NAME}"

echo "[DONE] Update completed."
