"""
Build the CONUS parcel universe for the Applied Energy usable-area benchmark.

Inputs
  - Data/Site Lists/Sites MECS Scaled/aggregated_facility_level_site_list_2026_04_23.csv
      (parcel-level, FIPS-fixed; 306,339 unique PARCEL_LIDs)
  - Data/Site Lists/.../Working Site Lists/matched_collapsed_filtered.gpkg
      (parcel polygon geometries; 307,127 rows)

Pipeline
  1. Load the aggregated CSV (PARCEL_LID keyed).
  2. Load the parcel GPKG and inner-join on PARCEL_LID (geometry source).
  3. Filter to CONUS (exclude AK=02, HI=15) via FIPS_CODE.
  4. Preserve ALL retained parcels including flag_industrial_park and flag_colocation,
     per scope decision 2026-04-27 (this paper benchmarks usable-area methods;
     energy allocation across co-located facilities is out of scope).
  5. Drop only rows with missing parcel_area_sf, null geometry, or empty geometry.
  6. Derive: acres, parcel_area_m2, size_bin, state_for_batch.
  7. Write a compact intermediate GPKG for downstream scenario scripts.

Outputs
  - Scripts/applied_energy_paper/intermediate/parcels_conus_2026_04_23.gpkg
  - Scripts/applied_energy_paper/intermediate/parcels_conus_2026_04_23_manifest.txt

Run
  cd Scripts/method_comparison
  pixi run python -u ../applied_energy_paper/01_build_parcel_universe_2026_04_23.py

Author: Stefan Rose / PNNL
Dataset version: 2026_04_23 (post FIPS fix)
"""

from __future__ import annotations

import sys
from pathlib import Path
import pandas as pd
import geopandas as gpd

sys.stdout.reconfigure(line_buffering=True)

BASE       = Path("/Users/rose501/Library/CloudStorage/OneDrive-PNNL/Desktop/IEDO")
NEW_CSV    = BASE / "Data/Site Lists/Sites MECS Scaled/aggregated_facility_level_site_list_2026_04_23.csv"
PARCEL_GPKG= BASE / "Data/Site Lists/New Site List Effort/Parcel Match Outputs/geocoded_matches/joined_output/final_filtering/Working Site Lists/matched_collapsed_filtered.gpkg"

OUT_DIR    = BASE / "Scripts/applied_energy_paper/intermediate"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_GPKG     = OUT_DIR / "parcels_conus_2026_04_23.gpkg"
OUT_MANIFEST = OUT_DIR / "parcels_conus_2026_04_23_manifest.txt"

# Non-CONUS FIPS state codes (2-digit)
NON_CONUS_FIPS = {"02", "15"}  # AK, HI. (DC=11, territories 60+ also excluded implicitly below)
VALID_CONUS_FIPS = {
    "01","04","05","06","08","09","10","11","12","13","16","17","18","19","20",
    "21","22","23","24","25","26","27","28","29","30","31","32","33","34","35",
    "36","37","38","39","40","41","42","44","45","46","47","48","49","50","51",
    "53","54","55","56",
}
# Note: 11 = DC. Retained with CONUS.

FIPS_TO_STATE = {
    "01":"AL","02":"AK","04":"AZ","05":"AR","06":"CA","08":"CO","09":"CT","10":"DE",
    "11":"DC","12":"FL","13":"GA","15":"HI","16":"ID","17":"IL","18":"IN","19":"IA",
    "20":"KS","21":"KY","22":"LA","23":"ME","24":"MD","25":"MA","26":"MI","27":"MN",
    "28":"MS","29":"MO","30":"MT","31":"NE","32":"NV","33":"NH","34":"NJ","35":"NM",
    "36":"NY","37":"NC","38":"ND","39":"OH","40":"OK","41":"OR","42":"PA","44":"RI",
    "45":"SC","46":"SD","47":"TN","48":"TX","49":"UT","50":"VT","51":"VA","53":"WA",
    "54":"WV","55":"WI","56":"WY",
}

SIZE_BINS   = [0, 0.5, 1, 10, 100, float("inf")]
SIZE_LABELS = ["tiny", "small", "medium", "large", "xlarge"]


def main():
    lines = []  # manifest lines

    def log(msg: str) -> None:
        print(msg)
        lines.append(msg)

    log(f"Dataset version: 2026_04_23 (post FIPS fix)")
    log(f"NEW_CSV:  {NEW_CSV}")
    log(f"GPKG:     {PARCEL_GPKG}")

    log("\nLoading aggregated CSV (parcel-level)...")
    df = pd.read_csv(
        NEW_CSV,
        dtype={"PARCEL_LID": str, "FIPS_CODE": str},
        low_memory=False,
    )
    log(f"  CSV rows: {len(df):,}  unique PARCEL_LIDs: {df['PARCEL_LID'].nunique():,}")
    assert len(df) == df["PARCEL_LID"].nunique(), "PARCEL_LID is expected to be unique in the new CSV"

    # Normalize FIPS: keep as-is 5-digit string; pad if needed and extract 2-digit state
    df["FIPS_CODE"] = df["FIPS_CODE"].fillna("").astype(str)
    df["fips_state2"] = df["FIPS_CODE"].str.zfill(5).str[:2]
    n_no_fips = (df["fips_state2"].isin({"", "00", "nan"}) | df["fips_state2"].isna()).sum()
    log(f"  Rows with missing/invalid FIPS: {n_no_fips:,}")

    # CONUS filter
    mask_conus = df["fips_state2"].isin(VALID_CONUS_FIPS)
    n_non_conus = (df["fips_state2"].isin(NON_CONUS_FIPS)).sum()
    n_other = (~mask_conus & ~df["fips_state2"].isin(NON_CONUS_FIPS)).sum()
    log(f"  AK + HI parcels (FIPS 02, 15) excluded:      {n_non_conus:,}")
    log(f"  Other non-CONUS / invalid FIPS excluded:     {n_other:,}")
    df_conus = df[mask_conus].copy()
    log(f"  CONUS CSV rows: {len(df_conus):,}")

    log("\nLoading parcel GPKG...")
    gdf = gpd.read_file(PARCEL_GPKG)
    log(f"  GPKG rows: {len(gdf):,}  CRS: {gdf.crs}")

    # Inner join on PARCEL_LID -> adds geometry to the CSV-sourced attributes
    log("\nJoining CSV attributes to GPKG geometry on PARCEL_LID (inner)...")
    gdf_small = gdf[["PARCEL_LID", "geometry"]].copy()
    gdf_j = gdf_small.merge(df_conus, on="PARCEL_LID", how="inner")
    gdf_j = gpd.GeoDataFrame(gdf_j, geometry="geometry", crs=gdf.crs)
    log(f"  Joined rows: {len(gdf_j):,}")
    dropped_from_csv = len(df_conus) - len(gdf_j)
    log(f"  CONUS CSV rows with no GPKG match: {dropped_from_csv:,}")

    # Geometry validity
    n_null = gdf_j.geometry.isna().sum()
    n_empty = gdf_j.geometry.is_empty.sum()
    n_null_area = gdf_j["parcel_area_sf"].isna().sum()
    log(f"  Null geometry: {n_null:,} | Empty geometry: {n_empty:,} | Null parcel_area_sf: {n_null_area:,}")

    keep = gdf_j.geometry.notna() & (~gdf_j.geometry.is_empty) & gdf_j["parcel_area_sf"].notna()
    n_dropped_valid = (~keep).sum()
    gdf_v = gdf_j[keep].copy()
    log(f"  Dropped for invalid geometry/area: {n_dropped_valid:,}")
    log(f"  Remaining CONUS parcels (valid geometry): {len(gdf_v):,}")

    # Derive size, area, state
    gdf_v["acres"]          = gdf_v["parcel_area_sf"] / 43_560.0
    gdf_v["parcel_area_m2"] = gdf_v["parcel_area_sf"] * 0.092903
    gdf_v["size_bin"]       = pd.cut(
        gdf_v["acres"], bins=SIZE_BINS, labels=SIZE_LABELS, right=False,
    )

    # state_for_batch — prefer SITE_STATE then FIPS-derived
    fips_state_ab = gdf_v["fips_state2"].map(FIPS_TO_STATE)
    if "SITE_STATE" in gdf_v.columns:
        gdf_v["state_for_batch"] = gdf_v["SITE_STATE"].fillna(fips_state_ab)
    else:
        gdf_v["state_for_batch"] = fips_state_ab
    n_null_state = gdf_v["state_for_batch"].isna().sum()
    log(f"  Rows with unresolved state: {n_null_state:,}")

    log("\nSize-bin distribution (CONUS):")
    bin_counts = gdf_v["size_bin"].value_counts().reindex(SIZE_LABELS)
    for b, n in bin_counts.items():
        log(f"  {b:>7}: {int(n):>9,}")

    log("\nTop 10 states by parcel count:")
    state_counts = gdf_v["state_for_batch"].value_counts().head(10)
    for s, n in state_counts.items():
        log(f"  {s}: {n:,}")

    log("\nFlag tallies (retained parcels):")
    for col in ("flag_industrial_park", "flag_colocation", "flag_multi_facility_confirmed"):
        if col in gdf_v.columns:
            n_true = (gdf_v[col] == True).sum()
            log(f"  {col} == True: {n_true:,}")

    # Keep only columns we need downstream — keeps the intermediate gpkg small
    keep_cols = [
        "PARCEL_LID", "FIPS_CODE", "fips_state2", "state_for_batch",
        "SITE_STATE", "COUNTY",
        "parcel_area_sf", "parcel_area_m2", "acres", "size_bin",
        "flag_industrial_park", "flag_colocation", "flag_multi_facility_confirmed",
        "bldg_footprint_sqm", "rooftop_solar_sqm", "usable_solar_sqm", "usable_wind_sqm",
        "geometry",
    ]
    keep_cols = [c for c in keep_cols if c in gdf_v.columns]
    gdf_out = gdf_v[keep_cols].copy()

    log(f"\nWriting intermediate GPKG → {OUT_GPKG}")
    if OUT_GPKG.exists():
        OUT_GPKG.unlink()
    gdf_out.to_file(OUT_GPKG, driver="GPKG")
    log(f"  Wrote {len(gdf_out):,} parcels")

    with OUT_MANIFEST.open("w") as f:
        f.write("\n".join(lines) + "\n")
    log(f"\nManifest → {OUT_MANIFEST}")
    log("Done.")


if __name__ == "__main__":
    main()
