#!/usr/bin/env bash
# Bootstrap the portfolio system.

set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$APP_DIR/venv"

# Create or activate virtual environment
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r "$APP_DIR/deploy/requirements.txt"

# Run each scraper sequentially and log the result
for f in "$APP_DIR"/scrapers/*.py; do
  name="$(basename "$f" .py)"
  set +e
  out=$(python "$f" 2>&1)
  status=$?
  set -e
  last_line=$(echo "$out" | tail -n 1)
  if [ $status -eq 0 ] && [[ $last_line =~ ROWS=([0-9]+)\ COLUMNS=([0-9]+) ]]; then
    rows=${BASH_REMATCH[1]}
    cols=${BASH_REMATCH[2]}
    echo "[OK] $name: ${rows}x${cols}"
  else
    echo "[FAIL] $name: failed"
  fi
done

# Register the service
cat <<EOF >/etc/systemd/system/portfolio.service
[Unit]
Description=Portfolio Service
After=network.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
ExecStart=$VENV_DIR/bin/python -m service.start
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable portfolio
systemctl start portfolio

echo "Bootstrap complete. Service portfolio is running."
