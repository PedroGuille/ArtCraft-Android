#!/usr/bin/env bash
set -e
lucy_script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$lucy_script_dir/lucy.py" "$@"
