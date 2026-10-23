#!/usr/bin/env bash
# Stream-download and parcel-flag NWI state GeoPackages.
#
# For each CONUS state:
#   1. Download <STATE>_geopackage_wetlands.zip from FWS
#   2. Unzip to a temp area
#   3. Run R/sf to st_intersects parcels (filtered to that state + adjacent bbox)
#      against the Wetlands polygon layer; save per-parcel flag CSV
#   4. Delete the zip and unzipped files (keep only the flag CSV)
#
# Output:
#   Data/wind_exclusions/NWI/<STATE>_nwi_parcel_flags.csv
#   Data/wind_exclusions/NWI/_download.log
# Final merge (driven by Rscript at end):
#   Scripts/applied_energy_paper/intermediate/wind_flags/flag_nwi.csv
#
# Usage:
#   bash download_and_flag_nwi.sh            # all CONUS states
#   bash download_and_flag_nwi.sh TX         # one state
#   bash download_and_flag_nwi.sh --resume   # skip states with existing flag CSV
#
# Disk discipline: at most one state's zip + unzipped data on disk at a time.

set -euo pipefail

REPO="${IEDO_BASE:?export IEDO_BASE=/path/to/IEDO (data root)}"
OUT_DIR="$REPO/Data/wind_exclusions/NWI"
TMP_DIR="$OUT_DIR/_tmp"
LOG="$OUT_DIR/_download.log"
# Flag method: raster (30 m, cell-centroid, EPSG:5070). Chosen for
# methodological consistency and scalability (MN's 2.66M-feature NWI layer
# wedges vector st_intersects under memory pressure). Vector method preserved
# at flag_parcels_one_state_nwi.R for reference.
FLAG_SCRIPT="$REPO/Scripts/applied_energy_paper/data_download/flag_parcels_one_state_nwi_raster.R"
BASE_URL="https://documentst.ecosphere.fws.gov/wetlands/data/State-Downloads"

mkdir -p "$OUT_DIR" "$TMP_DIR"
# CONUS states (from parcel universe 2026-04-23, N=49 — no HI/AK, no DC needs
# special-cased below since DC NWI exists separately)
STATES_DEFAULT=(AL AR AZ CA CO CT DC DE FL GA IA ID IL IN KS KY LA MA MD ME \
                MI MN MO MS MT NC ND NE NH NJ NM NV NY OH OK OR PA RI SC SD \
                TN TX UT VA VT WA WI WV WY)

RESUME=false
STATES=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --resume) RESUME=true; shift ;;
    *) STATES+=("$1"); shift ;;
  esac
done
if [[ ${#STATES[@]} -eq 0 ]]; then
  STATES=("${STATES_DEFAULT[@]}")
fi

log() {
  echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"
}

process_state() {
  local S="$1"
  local FLAG_CSV="$OUT_DIR/${S}_nwi_parcel_flags.csv"

  if $RESUME && [[ -f "$FLAG_CSV" ]]; then
    log "[$S] SKIP — already have $FLAG_CSV"
    return 0
  fi

  local URL="$BASE_URL/${S}_geopackage_wetlands.zip"
  local ZIP="$TMP_DIR/${S}_nwi.zip"
  local UNZ="$TMP_DIR/${S}_nwi"

  log "[$S] Downloading $URL"
  # Follow redirects, show progress-bar-less, fail on HTTP error
  if ! curl -fL --retry 3 --retry-delay 5 -o "$ZIP" "$URL"; then
    log "[$S] ERROR — download failed"
    return 1
  fi
  local SIZE=$(du -h "$ZIP" | awk '{print $1}')
  log "[$S] Downloaded $SIZE"

  log "[$S] Unzipping"
  rm -rf "$UNZ"
  mkdir -p "$UNZ"
  unzip -q "$ZIP" -d "$UNZ"

  # Find the .gpkg (layout varies by state)
  local GPKG
  GPKG="$(find "$UNZ" -maxdepth 3 -name '*.gpkg' | head -1)"
  if [[ -z "$GPKG" ]]; then
    log "[$S] ERROR — no .gpkg found in $UNZ"
    rm -rf "$ZIP" "$UNZ"
    return 1
  fi
  log "[$S] GPKG: $(basename "$GPKG")"

  log "[$S] Running flag script"
  if ! Rscript "$FLAG_SCRIPT" "$S" "$GPKG" "$FLAG_CSV" 2>&1 | tee -a "$LOG"; then
    log "[$S] ERROR — flag script failed"
    rm -rf "$ZIP" "$UNZ"
    return 1
  fi

  log "[$S] Cleaning up"
  rm -rf "$ZIP" "$UNZ"
  log "[$S] DONE — wrote $FLAG_CSV"
}

log "=== NWI download + flag pipeline start ==="
log "States to process (${#STATES[@]}): ${STATES[*]}"
log "Resume mode: $RESUME"

for S in "${STATES[@]}"; do
  if ! process_state "$S"; then
    log "[$S] continuing after error"
  fi
done

log "=== All states processed ==="

# Merge all per-state flag CSVs into one authoritative flag_nwi.csv
log "Merging per-state flag CSVs"
Rscript "$REPO/Scripts/applied_energy_paper/data_download/merge_nwi_flags.R" 2>&1 | tee -a "$LOG"

log "=== Pipeline complete ==="
