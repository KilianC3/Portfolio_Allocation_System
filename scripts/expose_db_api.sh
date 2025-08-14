#!/usr/bin/env bash
# Start the FastAPI service on an external interface.
# Usage: API_TOKEN=secret ./scripts/expose_db_api.sh [host] [port]
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HOST=${1:-$(grep '^REDIS_URL:' "$APP_DIR/service/config.yaml" | sed -E 's/.*@([0-9.]+):.*/\1/')}
PORT=${2:-8001}
if [ -z "${API_TOKEN:-}" ]; then
  echo "API_TOKEN environment variable required" >&2
  exit 1
fi
export API_HOST="$HOST"
export API_PORT="$PORT"
python -m service.start --host "$HOST" --port "$PORT"

