#!/bin/bash
# run_nwi_coverage_sample.sh
#
# Download NWI GPKG for a 6-state sample, compute per-parcel coverage
# fraction, discard raw data. Sample chosen to span wetland regimes:
#   WY, MT  — arid west (salt flats, playas, sagebrush riparian)
#   ME      — northern forested (bogs, glacial wetlands)
#   MS      — southeast (bottomland hardwood, bayous)
#   MN      — midwest (prairie pothole, lakes)
#   PA      — mid-atlantic (mixed forest + farmland)
#
# Output: Data/wind_exclusions/NWI/_coverage_sample_2026_04_30/{STATE}_nwi_coverage.csv
#
# Skips states with existing output (idempotent).

set -euo pipefail

REPO="/Users/rose501/Library/CloudStorage/OneDrive-PNNL/Desktop/IEDO"
OUT_DIR="$REPO/Data/wind_exclusions/NWI/_coverage_sample_2026_04_30"
TMP_DIR="$REPO/Data/wind_exclusions/NWI/_tmp"
FLAG_SCRIPT="$REPO/Scripts/applied_energy_paper/data_download/flag_parcels_one_state_nwi_coverage.R"
LOG_FILE="$OUT_DIR/run.log"

mkdir -p "$OUT_DIR" "$TMP_DIR"

STATES=("WY" "MT" "ME" "MS" "MN" "PA")

exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== NWI coverage sample run started $(date -u) ==="

for STATE in "${STATES[@]}"; do
  OUT_CSV="$OUT_DIR/${STATE}_nwi_coverage.csv"
  if [ -f "$OUT_CSV" ]; then
    echo "[$STATE] output exists, skipping"
    continue
  fi

  echo "---"
  echo "[$STATE] begin $(date -u)"

  ZIP_PATH="$TMP_DIR/${STATE}.zip"
  UNZIP_DIR="$TMP_DIR/${STATE}_unzip"
  URL="https://documentst.ecosphere.fws.gov/wetlands/data/State-Downloads/${STATE}_geopackage_wetlands.zip"

  # Download
  if [ ! -f "$ZIP_PATH" ]; then
    echo "[$STATE] downloading"
    curl -sfL --retry 3 --retry-delay 10 -o "$ZIP_PATH" "$URL"
  fi
  echo "[$STATE] zip size: $(du -h "$ZIP_PATH" | cut -f1)"

  # Unzip
  rm -rf "$UNZIP_DIR"
  mkdir -p "$UNZIP_DIR"
  unzip -q -o "$ZIP_PATH" -d "$UNZIP_DIR"
  GPKG=$(find "$UNZIP_DIR" -name "*.gpkg" | head -1)
  if [ -z "$GPKG" ]; then
    echo "[$STATE] ERROR: no .gpkg after unzip"
    rm -rf "$UNZIP_DIR" "$ZIP_PATH"
    continue
  fi
  echo "[$STATE] gpkg: $(du -h "$GPKG" | cut -f1)"

  # Coverage
  Rscript "$FLAG_SCRIPT" "$STATE" "$GPKG" "$OUT_CSV"
  echo "[$STATE] done $(date -u)"

  # Cleanup
  rm -rf "$UNZIP_DIR" "$ZIP_PATH"
done

echo "=== NWI coverage sample run finished $(date -u) ==="
