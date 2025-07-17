#!/usr/bin/env bash
# Bootstrap the portfolio system inside a fresh container.

set -euo pipefail

PG_USER="portfolio"
PG_PASS="Hillside3693"
PG_DB="quant_fund"
APP_DIR="/opt/portfolio"
VENV_DIR="$APP_DIR/venv"


# The Postgres role and database must already exist

# Clone repo if not present
if [ ! -d "$APP_DIR" ]; then
  git clone https://example.com/portfolio.git "$APP_DIR"
fi
cd "$APP_DIR"

python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip
"$VENV_DIR/bin/pip" install -r deploy/requirements.txt

sed -i "s|^PG_URI:.*|PG_URI: 'postgresql://${PG_USER}:${PG_PASS}@localhost:5432/${PG_DB}'|" service/config.yaml

# Seed the database with a full scrape before starting the service
"$VENV_DIR/bin/python" -m scripts.bootstrap

cat <<'EOF' >/usr/local/bin/wait-for-postgres.sh
#!/usr/bin/env bash
until pg_isready -q; do
  sleep 1
done
EOF
chmod +x /usr/local/bin/wait-for-postgres.sh

cat <<EOF >/etc/systemd/system/portfolio.service
[Unit]
Description=Portfolio Allocation API
After=network.target
Requires=postgresql.service

[Service]
Type=simple
WorkingDirectory=$APP_DIR
ExecStartPre=/usr/local/bin/wait-for-postgres.sh
ExecStart=$VENV_DIR/bin/python -m service.start
Restart=on-failure
WatchdogSec=30

[Install]
WantedBy=multi-user.target
EOF

cat <<EOF >/etc/logrotate.d/portfolio
$APP_DIR/logs/*.log {
    rotate 4
    weekly
    missingok
    notifempty
    compress
}
EOF

systemctl daemon-reload
systemctl enable postgresql
systemctl enable portfolio
systemctl start postgresql
systemctl start portfolio

sed -i 's|#SystemMaxUse=.*|SystemMaxUse=50M|' /etc/systemd/journald.conf
systemctl restart systemd-journald

echo "Bootstrap complete"
