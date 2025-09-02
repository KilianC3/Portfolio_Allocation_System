#!/usr/bin/env bash
# Bootstrap the portfolio system.

set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$APP_DIR/venv"
# Use the fixed application IP required by infrastructure
APP_IP="192.168.0.59"

# Create or activate virtual environment
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r "$APP_DIR/deploy/requirements.txt"
sudo apt-get update
echo "Installing git, git-lfs, curl and MariaDB"
sudo apt-get install -y git git-lfs curl mariadb-server
git lfs install --system
if ! git -C "$APP_DIR" remote | grep -q backup; then
  git -C "$APP_DIR" remote add backup https://github.com/KilianC3/Backup
fi
git -C "$APP_DIR" lfs install --local
# Bind MariaDB to the deployment IP so remote clients can connect. Keep the
# default MySQL port to avoid clashes with the API server which listens on
# ``8001``.
sudo sed -i "s/^bind-address.*/bind-address = ${APP_IP}/" /etc/mysql/mariadb.conf.d/50-server.cnf
sudo sed -i "s/^#\?port.*/port = 3306/" /etc/mysql/mariadb.conf.d/50-server.cnf
"$APP_DIR/scripts/setup_redis.sh" "$APP_IP"
sudo systemctl enable mariadb
sudo systemctl start mariadb
sudo mysql -e "CREATE DATABASE IF NOT EXISTS quant_fund;"
sudo mysql -e "GRANT ALL PRIVILEGES ON quant_fund.* TO 'maria'@'%' IDENTIFIED BY 'maria'; FLUSH PRIVILEGES;"
python -m playwright install chromium
# Scrapers are intentionally excluded from bootstrap to avoid noisy console
# output and to keep deployment idempotent. Run `scripts/populate.py`
# manually once the service is up if data backfilling is required.


# Register the service
cat <<EOF >/etc/systemd/system/portfolio.service
[Unit]
Description=Portfolio Service
After=network.target mariadb.service redis-server.service
Requires=mariadb.service redis-server.service

[Service]
Type=simple
WorkingDirectory=$APP_DIR
Environment=PYTHONPATH=$APP_DIR
ExecStart=$VENV_DIR/bin/python $APP_DIR/service/start.py --host ${APP_IP} --port 8001
Restart=on-failure
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable portfolio
systemctl start portfolio

# Retry health check with a bounded loop so bootstrap never blocks indefinitely
echo "Waiting for API to become available"
for attempt in {1..6}; do
  if curl -sf --connect-timeout 5 "http://${APP_IP}:8001/health" >/dev/null; then
    echo "API is on at http://${APP_IP}:8001"
    API_UP=1
    break
  fi
  if [ "$attempt" -lt 6 ]; then
    echo "Attempt ${attempt}/6 failed; retrying in 5s..."
    sleep 5
  fi
done
if [ -z "${API_UP:-}" ]; then
  echo "API failed to respond after 6 attempts; check 'journalctl -u portfolio' for details" >&2
  exit 1
fi
echo "Bootstrap complete. Service portfolio is running."
