#!/usr/bin/env bash
# Install and configure Redis for the portfolio system.
set -euo pipefail

REDIS_IP="192.168.0.59"

sudo apt-get update
sudo apt-get install -y redis-server

# Bind Redis to the expected interface
sudo sed -i "s/^bind .*/bind ${REDIS_IP}/" /etc/redis/redis.conf

sudo systemctl enable --now redis-server.service

echo "Redis running on ${REDIS_IP}:6379"
