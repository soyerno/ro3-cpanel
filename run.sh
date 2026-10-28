#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo "==================================================="
echo " Starting RO3 CPanel (White-Label Admin Panel)"
echo "==================================================="

if [ ! -f "config.json" ] && [ -f "config.example.json" ]; then
    echo "[Notice] config.json not found, copying from config.example.json..."
    cp config.example.json config.json
fi

exec python3 server.py
