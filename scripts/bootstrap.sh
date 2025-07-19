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
python -m playwright install chromium || true

# Refresh ticker universe before running other scrapers
PYTHONPATH="$APP_DIR" python3 -m scrapers.universe --refresh-universe

# Run each scraper sequentially and log the result
echo "Starting data bootstrap..."
LOG_CHECKLIST=()

for script in "$APP_DIR"/scrapers/*.py; do
  name="$(basename "$script" .py)"
  # Skip __init__.py and the universe script already run above
  [ "$name" = "__init__" ] && continue
  [ "$name" = "universe" ] && continue

  echo -e "\nRunning scraper: $name"
  cd "$APP_DIR"
  set +e
  out=$(PYTHONPATH="$APP_DIR" python3 -m scrapers."$name" 2>&1)
  status=$?
  set -e
  echo "$out"

  if [ $status -eq 0 ] && grep -qE 'ROWS=[0-9]+ COLUMNS=[0-9]+' <<<"$out"; then
    summary=$(grep -oE 'ROWS=[0-9]+ COLUMNS=[0-9]+' <<<"$out")
    rows=$(sed -n 's/.*ROWS=\([0-9]\+\).*/\1/p' <<<"$summary")
    cols=$(sed -n 's/.*COLUMNS=\([0-9]\+\).*/\1/p' <<<"$summary")
    echo "[OK]  $name: ${rows}x${cols}"
    LOG_CHECKLIST+=("[OK]  $name: ${rows}x${cols}")
  elif [ $status -eq 0 ]; then
    echo "[OK]  $name: 0x0 (no data summary)"
    LOG_CHECKLIST+=("[OK]  $name: 0x0")
  else
    echo "[FAIL] $name: failed"
    LOG_CHECKLIST+=("[FAIL] $name: failed")
  fi
done

echo -e "\nBootstrap checklist:"
for entry in "${LOG_CHECKLIST[@]}"; do
  echo "  $entry"
done

# Register the service
cat <<EOF >/etc/systemd/system/portfolio.service
[Unit]
Description=Portfolio Service
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
WorkingDirectory=$APP_DIR
Environment=PYTHONPATH=$APP_DIR
ExecStart=$VENV_DIR/bin/python -m service.start
Restart=on-failure
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable portfolio
systemctl start portfolio

echo "Bootstrap complete. Service portfolio is running."
