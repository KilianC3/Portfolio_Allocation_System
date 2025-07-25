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
sudo apt-get update
sudo apt-get install -y mariadb-server
# Bind MariaDB to all interfaces so remote clients can connect
sudo sed -i 's/^bind-address.*/bind-address = 0.0.0.0/' /etc/mysql/mariadb.conf.d/50-server.cnf
"$APP_DIR/scripts/setup_redis.sh"
sudo systemctl enable mariadb
sudo systemctl start mariadb
sudo mysql -e "CREATE DATABASE IF NOT EXISTS quant_fund;"
sudo mysql -e "GRANT ALL PRIVILEGES ON quant_fund.* TO 'maria'@'%' IDENTIFIED BY 'maria'; FLUSH PRIVILEGES;"
python -m playwright install chromium || true


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
ExecStart=$VENV_DIR/bin/python $APP_DIR/service/start.py --host 192.168.0.59 --port 8001
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
