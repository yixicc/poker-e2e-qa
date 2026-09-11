#!/bin/bash
cd "$(dirname "$0")"
exec python3 e2e_quality_server.py --host 0.0.0.0 --port 8767 "$@"
