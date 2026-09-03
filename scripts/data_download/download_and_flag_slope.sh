#!/usr/bin/env bash
# Stream-download 3DEP 1 arc-second DEM tiles and produce per-parcel
# slope>25% flags. Never keeps raw DEM tiles on disk — each is deleted after
# the slope mask is derived and accumulated into parcel flags.
#
# For each tile in Scripts/applied_energy_paper/intermediate/dem_tiles_needed.txt:
#   1. aws s3 cp tile to TMP (no-sign-request, ~56 MB)
#   2. gdaldem slope (percent, neighbor=8)  -> slope.tif
#   3. gdal_calc.py slope >= 25 -> mask.tif (byte, 1/0)
#   4. Reproject mask to EPSG:5070 & aggregate to parcel-level "any-cell-true"
#      via R/exactextractr (faster than per-parcel terra::extract)
#   5. Append parcel flags to running CSV; delete tile + slope + mask
#
# Output:
#   Data/wind_exclusions/Slope/_per_tile/<TILE>_flags.csv   (per-tile parcels with flag=TRUE)
#   Data/wind_exclusions/Slope/_download.log
# Final merge -> Scripts/applied_energy_paper/intermediate/wind_flags/flag_slope_gt25.csv
#
# Usage:
#   bash download_and_flag_slope.sh              # all tiles
#   bash download_and_flag_slope.sh --resume     # skip tiles with existing per-tile CSV
#   bash download_and_flag_slope.sh n40w080      # one tile (testing)
#   bash download_and_flag_slope.sh --n-parallel 4  # parallel tile pipelines

set -euo pipefail

REPO="/Users/rose501/Library/CloudStorage/OneDrive-PNNL/Desktop/IEDO"
OUT_DIR="$REPO/Data/wind_exclusions/Slope"
PER_TILE_DIR="$OUT_DIR/_per_tile"
TMP_DIR="$OUT_DIR/_tmp"
LOG="$OUT_DIR/_download.log"
TILES_LIST="$REPO/Scripts/applied_energy_paper/intermediate/dem_tiles_needed.txt"
FLAG_SCRIPT="$REPO/Scripts/applied_energy_paper/data_download/flag_parcels_one_tile_slope.R"
S3_BASE="s3://prd-tnm/StagedProducts/Elevation/1/TIFF/current"

SLOPE_THRESHOLD_PCT=25  # Lopez 2023 Reference Access slope cutoff

mkdir -p "$OUT_DIR" "$PER_TILE_DIR" "$TMP_DIR"

RESUME=false
N_PARALLEL=1
SKIP_MERGE=false
TILES=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --resume) RESUME=true; shift ;;
    --n-parallel) N_PARALLEL="$2"; shift 2 ;;
    --skip-merge) SKIP_MERGE=true; shift ;;  # internal: used by parallel workers
    *) TILES+=("$1"); shift ;;
  esac
done

if [[ ${#TILES[@]} -eq 0 ]]; then
  # Portable replacement for `mapfile -t TILES < file` (macOS ships bash 3.2).
  TILES=()
  while IFS= read -r _line || [[ -n "$_line" ]]; do
    [[ -z "$_line" ]] && continue
    TILES+=("$_line")
  done < "$TILES_LIST"
fi

log() {
  echo "[$(date +%H:%M:%S)] $*" | tee -a "$LOG"
}

process_tile() {
  local TILE="$1"
  local PER_TILE_CSV="$PER_TILE_DIR/${TILE}_flags.csv"

  if $RESUME && [[ -f "$PER_TILE_CSV" ]]; then
    # Empty file (0 bytes) is valid: tile had no parcels or no slope>=25% cells
    return 0
  fi

  local URL="$S3_BASE/${TILE}/USGS_1_${TILE}.tif"
  local TIF="$TMP_DIR/${TILE}.tif"
  local SLOPE="$TMP_DIR/${TILE}_slope.tif"
  local MASK="$TMP_DIR/${TILE}_mask.tif"

  log "[$TILE] download"
  if ! aws s3 cp "$URL" "$TIF" --no-sign-request --only-show-errors; then
    log "[$TILE] WARN — S3 download failed (tile may not exist; check coverage)"
    # Leave empty per-tile CSV so resume skips next time
    : > "$PER_TILE_CSV"
    return 0
  fi

  log "[$TILE] gdaldem slope (percent)"
  # -p: percent slope. -s 111120 scales degrees→meters at equator for 1-arc-sec
  # input in geographic CRS. 8-neighbor (ZevenbergenThorne) is gdaldem default.
  if ! gdaldem slope "$TIF" "$SLOPE" -p -s 111120 -q; then
    log "[$TILE] ERROR — gdaldem slope failed"
    rm -f "$TIF" "$SLOPE" "$MASK"
    return 1
  fi

  log "[$TILE] threshold >= ${SLOPE_THRESHOLD_PCT}%"
  if ! gdal_calc.py --quiet -A "$SLOPE" --outfile="$MASK" \
       --calc="(A>=${SLOPE_THRESHOLD_PCT}).astype(uint8)" \
       --NoDataValue=255 --type=Byte --overwrite; then
    log "[$TILE] ERROR — gdal_calc failed"
    rm -f "$TIF" "$SLOPE" "$MASK"
    return 1
  fi

  # Remove raw DEM and slope raster immediately; only the byte mask remains
  # (typical size ~1-5 MB vs 56 MB DEM + ~112 MB float32 slope).
  rm -f "$TIF" "$SLOPE"

  log "[$TILE] flag parcels"
  if ! Rscript "$FLAG_SCRIPT" "$TILE" "$MASK" "$PER_TILE_CSV" 2>&1 | \
       grep -v "^\\s*\$" | tee -a "$LOG"; then
    log "[$TILE] ERROR — flag script failed"
    rm -f "$MASK"
    return 1
  fi

  rm -f "$MASK"
  return 0
}

log "=== 3DEP slope download + flag pipeline start ==="
log "Tiles to process (${#TILES[@]}): N=${#TILES[@]} (first 5: ${TILES[*]:0:5} ...)"
log "Slope threshold: ${SLOPE_THRESHOLD_PCT}%"
log "Resume mode: $RESUME"
log "Parallelism: $N_PARALLEL"

if [[ "$N_PARALLEL" -gt 1 ]]; then
  if ! command -v parallel >/dev/null; then
    log "GNU parallel not installed; falling back to N_PARALLEL=1"
    N_PARALLEL=1
  fi
fi

if [[ "$N_PARALLEL" -gt 1 ]]; then
  # Self-invoke one-tile-at-a-time via GNU parallel. Each child run uses
  # --resume + a single tile arg, which exercises the same process_tile path.
  # Pass --resume so parallel workers skip completed tiles transparently.
  SELF="$REPO/Scripts/applied_energy_paper/data_download/download_and_flag_slope.sh"
  # Use --eta for progress without tty (--bar needs /dev/tty which isn't
  # available when launched via the process manager).
  printf "%s\n" "${TILES[@]}" | \
    parallel -j "$N_PARALLEL" --lb --eta --joblog "$OUT_DIR/_parallel_joblog.tsv" \
      "bash '$SELF' --resume --skip-merge {} > /dev/null 2>&1 && echo '[done] {}' || echo '[fail] {}'" | \
    tee -a "$LOG"
else
  i=0
  for T in "${TILES[@]}"; do
    i=$((i+1))
    if ! process_tile "$T"; then
      log "[$T] continuing after error"
    fi
    if (( i % 25 == 0 )); then
      log "Progress: $i / ${#TILES[@]} tiles"
      # Report disk usage
      df -h "$REPO" | tail -1 | tee -a "$LOG"
    fi
  done
fi

log "=== All tiles processed ==="

if $SKIP_MERGE; then
  log "Skipping merge (worker invocation)"
  exit 0
fi

# Merge per-tile CSVs into authoritative flag_slope_gt25.csv
log "Merging per-tile flag CSVs"
Rscript "$REPO/Scripts/applied_energy_paper/data_download/merge_slope_flags.R" 2>&1 | tee -a "$LOG"

log "=== Pipeline complete ==="
