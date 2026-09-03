"""
Sanity check for the FIPS-fixed parcel universe prior to reV solar re-runs.

Checks:
  1. Row count and PARCEL_LID uniqueness in the new aggregated file.
  2. Join coverage against the existing parcel geometry GPKG.
  3. Parcel area availability and geometry validity for the joined set.
  4. Flag counts (industrial park, colocation) in the new universe.
  5. State distribution of unmatched rows (to triage missing geometries).

Run from repo root with the method_comparison pixi env:
  cd Scripts/method_comparison && pixi run python ../applied_energy_paper/00_sanity_check_parcel_universe.py
"""

from __future__ import annotations

from pathlib import Path
import sys
import pandas as pd
import geopandas as gpd

# Path configuration: load BASE and named input paths from config.toml at
# the repo root (falls back to config.example.toml if config.toml is absent).
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
from _config import BASE  # noqa: E402
NEW_CSV = BASE / "Data/Site Lists/Sites MECS Scaled/aggregated_facility_level_site_list_2026_04_23.csv"
PARCEL_GPKG = BASE / "Data/Site Lists/New Site List Effort/Parcel Match Outputs/geocoded_matches/joined_output/final_filtering/Working Site Lists/matched_collapsed_filtered.gpkg"

# Force line-buffered output so progress is visible in long runs
sys.stdout.reconfigure(line_buffering=True)

print("Loading new aggregated CSV (parcel-level, FIPS-fixed)...")
df = pd.read_csv(NEW_CSV, dtype={"PARCEL_LID": str, "FIPS_CODE": str}, low_memory=False)
print(f"  Rows: {len(df):,}")
print(f"  Unique PARCEL_LIDs: {df['PARCEL_LID'].nunique():,}")
n_dup = len(df) - df["PARCEL_LID"].nunique()
print(f"  Duplicate PARCEL_LIDs: {n_dup:,}")

print("\nFlag tallies (new file):")
for col in ("flag_industrial_park", "flag_colocation", "flag_multi_facility_confirmed"):
    if col in df.columns:
        n_true = (df[col] == True).sum()
        print(f"  {col} == True: {n_true:,}")

print("\nLoading existing parcel GPKG (geometry source)...")
gdf = gpd.read_file(PARCEL_GPKG)
print(f"  Rows: {len(gdf):,}")
print(f"  Unique PARCEL_LIDs: {gdf['PARCEL_LID'].nunique():,}")

print("\nJoin coverage: new CSV → GPKG geometry")
in_both = df["PARCEL_LID"].isin(set(gdf["PARCEL_LID"]))
print(f"  New CSV rows with matching geometry: {in_both.sum():,}  ({in_both.mean()*100:.2f}%)")
print(f"  New CSV rows WITHOUT matching geometry: {(~in_both).sum():,}")

print("\nJoin coverage: GPKG → new CSV")
gpkg_in_new = gdf["PARCEL_LID"].isin(set(df["PARCEL_LID"]))
print(f"  GPKG rows present in new CSV:       {gpkg_in_new.sum():,}  ({gpkg_in_new.mean()*100:.2f}%)")
print(f"  GPKG rows dropped from new CSV:     {(~gpkg_in_new).sum():,}")

# Geometry validity on the joined set
print("\nGeometry validity on the intersection set:")
joined = gdf.merge(df[["PARCEL_LID"]].drop_duplicates(), on="PARCEL_LID", how="inner")
n_null_geom = joined.geometry.isna().sum()
n_empty_geom = joined.geometry.is_empty.sum()
n_null_area = joined["parcel_area_sf"].isna().sum() if "parcel_area_sf" in joined.columns else -1
print(f"  Joined rows:              {len(joined):,}")
print(f"  Null geometry:            {n_null_geom:,}")
print(f"  Empty geometry:           {n_empty_geom:,}")
print(f"  parcel_area_sf null:      {n_null_area:,}")

# Triage: unmatched rows by state
if (~in_both).any():
    print("\nUnmatched rows by state (top 15):")
    unmatched = df.loc[~in_both, ["SITE_STATE", "FIPS_CODE"]]
    by_state = unmatched["SITE_STATE"].fillna("<null>").value_counts().head(15)
    for s, n in by_state.items():
        print(f"  {s}: {n:,}")

print("\nDone.")
