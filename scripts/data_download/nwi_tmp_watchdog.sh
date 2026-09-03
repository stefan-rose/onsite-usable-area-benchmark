#!/usr/bin/env bash
# NWI tmp-dir watchdog
#
# Scans Data/wind_exclusions/NWI/_tmp/ every 5 minutes. Deletes any
# subdirectory or .zip file whose mtime is older than 30 minutes AND which
# is not currently being read by any running Rscript or unzip process.
#
# Safety: only touches files inside the _tmp/ dir. Silent unless it removes
# something, in which case it writes one line to _watchdog.log.
#
# Exits on its own after MAX_ITERS iterations (default: 12 hours worth).

set -euo pipefail

REPO="/Users/rose501/Library/CloudStorage/OneDrive-PNNL/Desktop/IEDO"
TMP_DIR="$REPO/Data/wind_exclusions/NWI/_tmp"
LOG="$REPO/Data/wind_exclusions/NWI/_watchdog.log"

STALE_MINUTES=30
SLEEP_SEC=300
MAX_ITERS=144  # 12 hours

mkdir -p "$TMP_DIR"

log() {
  local msg="[$(date +%H:%M:%S)] $*"
  # Append to file directly, and echo to stdout with explicit flush.
  # Avoid `tee` which buffers stdout when piped to a non-terminal.
  printf '%s\n' "$msg" >> "$LOG"
  printf '%s\n' "$msg"
}

log "=== NWI tmp watchdog started (stale threshold: ${STALE_MINUTES} min, sleep: ${SLEEP_SEC}s) ==="

iter=0
while (( iter < MAX_ITERS )); do
  iter=$((iter + 1))

  # Check each entry in _tmp/
  for entry in "$TMP_DIR"/*; do
    [[ -e "$entry" ]] || continue
    base="$(basename "$entry")"

    # Skip the watchdog log itself
    [[ "$base" == "_watchdog.log" ]] && continue

    # Find mtime in minutes ago (macOS stat syntax)
    mtime_sec=$(stat -f %m "$entry" 2>/dev/null || echo 0)
    now_sec=$(date +%s)
    age_min=$(( (now_sec - mtime_sec) / 60 ))

    if (( age_min < STALE_MINUTES )); then
      continue
    fi

    # Is any Rscript or unzip process actively referencing this path?
    # Use pgrep to check running commands. If our path appears in any
    # running process's command line, skip.
    if pgrep -fl "$entry" > /dev/null 2>&1; then
      continue
    fi

    # Also check if an R process is reading the state that this entry belongs to.
    # e.g. if entry is MN_nwi or MN_nwi.zip, state = MN
    state=$(echo "$base" | sed -E 's/^([A-Z]{2})_nwi.*/\1/')
    if [[ ${#state} -eq 2 ]]; then
      # Any R process with "--args $state" means it's flagging that state
      if pgrep -fl "args $state " > /dev/null 2>&1; then
        continue
      fi
    fi

    # Safe to remove
    size=$(du -sh "$entry" 2>/dev/null | awk '{print $1}')
    log "STALE: removing $entry ($size, age ${age_min}min)"
    rm -rf "$entry"
  done

  sleep "$SLEEP_SEC"
done

log "=== watchdog exiting after ${MAX_ITERS} iterations ==="
