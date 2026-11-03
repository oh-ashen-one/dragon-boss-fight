#!/bin/bash
# Launch only the verified packaged build through the shared GPU guard.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/play_shipping.py" "$@"
