#!/usr/bin/env bash
set -euo pipefail
kit="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$kit/linux.py" "$@"
