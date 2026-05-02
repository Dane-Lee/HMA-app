#!/bin/sh
set -e

CERT_DIR=/app/certs
CERT_FILE=$CERT_DIR/cert.pem
KEY_FILE=$CERT_DIR/key.pem

if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
  echo "Generating self-signed TLS certificate..."
  python api/generate_cert.py "$CERT_FILE" "$KEY_FILE"
  echo "Certificate ready."
fi

exec python -m uvicorn api.app.main:app \
  --host 0.0.0.0 \
  --port 443 \
  --ssl-keyfile "$KEY_FILE" \
  --ssl-certfile "$CERT_FILE"
