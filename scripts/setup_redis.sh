#!/usr/bin/env bash
# Install and configure Redis for the portfolio system.
set -euo pipefail

REDIS_IP="192.168.0.59"
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
API_TOKEN=$(grep '^API_TOKEN:' "$APP_DIR/service/config.yaml" | awk '{print $2}' | tr -d '"')

sudo apt-get update
sudo apt-get install -y redis-server

# Bind Redis to the expected interface
sudo sed -i "s/^bind .*/bind ${REDIS_IP}/" /etc/redis/redis.conf
sudo sed -i "s/^# *requirepass .*$/requirepass ${API_TOKEN}/" /etc/redis/redis.conf

sudo systemctl enable --now redis-server.service
sudo systemctl restart redis-server.service

echo "Redis running on ${REDIS_IP}:6379"
