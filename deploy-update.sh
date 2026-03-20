#!/usr/bin/env bash
set -euo pipefail

APP_NAME="skland-login-web"

upsert_env_key() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" .env; then
    sed -i "s#^${key}=.*#${key}=${value}#" .env
  else
    printf '%s=%s\n' "${key}" "${value}" >> .env
  fi
}

generate_secret() {
  if command -v python3 >/dev/null 2>&1; then
    python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
  elif command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  else
    date +%s | sha256sum | awk '{print $1}'
  fi
}

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

# 自动准备 .env。优先复用模板，其次创建最小配置。
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
  else
    cat > .env <<'EOF'
PORT=5000
FLASK_SECRET_KEY=change-me-to-a-long-random-string
BUILD_COMMIT=unknown
EOF
  fi
fi

# 补齐必需配置并更新构建号
if ! grep -q '^PORT=' .env; then
  printf 'PORT=5000\n' >> .env
fi

current_secret="$(grep '^FLASK_SECRET_KEY=' .env | head -n1 | cut -d'=' -f2- || true)"
if [ -z "${current_secret}" ] || [ "${current_secret}" = "change-me-to-a-long-random-string" ]; then
  upsert_env_key "FLASK_SECRET_KEY" "$(generate_secret)"
fi

upsert_env_key "BUILD_COMMIT" "${BUILD_COMMIT}"

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
