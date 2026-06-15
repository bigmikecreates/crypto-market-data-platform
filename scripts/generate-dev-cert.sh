#!/bin/sh
# Generate a self-signed development certificate for local HTTPS testing.
# Usage: scripts/generate-dev-cert.sh [output-dir]
# Default output: ./certs/

set -e

OUT="${1:-certs}"
mkdir -p "$OUT"

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout "$OUT/key.pem" \
  -out "$OUT/cert.pem" \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

echo "Self-signed certificate generated in $OUT/"
echo "  cert.pem — certificate"
echo "  key.pem  — private key"
echo ""
echo "Mount the directory as /etc/nginx/certs in the nginx container"
echo "and uncomment the HTTPS server block in nginx/nginx.conf."
