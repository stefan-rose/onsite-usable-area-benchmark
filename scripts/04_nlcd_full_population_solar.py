"""
NLCD full-population solar usable-area computation.

Replaces the stratified-sample + extrapolation workflow (09_national_nlcd_rates.py +
12_nlcd_refined_estimator.py + 08_full_comparison.py) with a direct per-parcel
calculation, for methodological symmetry with the reV pipeline.

Inputs
  - Data/LC_Output/output_4_15_26/2021_NLCD_parcels_area_m2_*.csv  (17 CONUS state-batch files)
      Per-parcel NLCD 2021 class area in m^2, extracted in Google Earth Engine.
      Columns: system:index, <16 NLCD class codes>, PARCEL_LID, Total_Area, Year, .geo
      Header rows (system:index == '1_0') present in each file and are dropped.

  - Scripts/applied_energy_paper/intermediate/parcels_conus_2026_04_23.gpkg
      305,123 CONUS parcels with size_bin, acres, parcel_area_m2, state.

Outputs
  Scripts/method_comparison/outputs/full_run_nlcd_2026_04_23/nlcd_full_population.csv
      Per-parcel NLCD solar usable area. Schema analogous to the reV outputs:
      PARCEL_LID, SITE_STATE, state_for_batch, acres, parcel_area_m2, size_bin,
      <per-class area columns>, total_nlcd_area_m2, nlcd_coverage_ratio,
      flag_nlcd_no_value, usable_area_nlcd_m2, usable_area_nlcd_ac.

Approach
  usable_area_nlcd_m2 = sum_c ( class_area_m2[c] * solar_availability[c] )

Availability percentages come from Communications/Paper/Applied Energy/
nlcd_availability_reference.md (same values used in 03_nlcd_usable_area.py
and 09_national_nlcd_rates.py).

Run
  cd Scripts/method_comparison
  pixi run python -u ../applied_energy_paper/04_nlcd_full_population_solar.py

Author: Stefan Rose / PNNL
Dataset version: 2026_04_23 (post FIPS fix)
"""

from __future__ import annotations

import sys
import time
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning)
sys.stdout.reconfigure(line_buffering=True)

# ─── Paths ──────────────────────────────────────────────────────────────────

# Path configuration: load BASE and named input paths from config.toml at
# the repo root (falls back to config.example.toml if config.toml is absent).
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
from _config import BASE  # noqa: E402
GEE_DIR      = BASE / "Data/LC_Output/output_4_15_26"
PARCEL_GPKG  = BASE / "Scripts/applied_energy_paper/intermediate/parcels_conus_2026_04_23.gpkg"
OUT_DIR      = BASE / "Scripts/method_comparison/outputs/full_run_nlcd_2026_04_23"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DATASET_TAG = "2026_04_23"

# ─── NLCD class solar availability table ─────────────────────────────────────
# Source: Communications/Paper/Applied Energy/nlcd_availability_reference.md
# (underlying reference: Onsite Solar PV and Wind Metrics for Industrial
# Facilities. See manuscript §3 and Appendix A).

NLCD_CLASSES = {
    "11": {"name": "open_water",                   "solar_avail": 0.00},
    "12": {"name": "perennial_ice_snow",            "solar_avail": 0.00},
    "21": {"name": "developed_open_space",          "solar_avail": 0.30},
    "22": {"name": "developed_low_intensity",       "solar_avail": 0.30},
    "23": {"name": "developed_medium_intensity",    "solar_avail": 0.20},
    "24": {"name": "developed_high_intensity",      "solar_avail": 0.20},
    "31": {"name": "barren_land",                   "solar_avail": 0.80},
    "41": {"name": "deciduous_forest",              "solar_avail": 0.10},
    "42": {"name": "evergreen_forest",              "solar_avail": 0.05},
    "43": {"name": "mixed_forest",                  "solar_avail": 0.15},
    "52": {"name": "shrub_scrub",                   "solar_avail": 0.70},
    "71": {"name": "grassland_herbaceous",          "solar_avail": 0.70},
    "81": {"name": "pasture_hay",                   "solar_avail": 0.60},
    "82": {"name": "cultivated_crops",              "solar_avail": 0.60},
    "90": {"name": "woody_wetlands",                "solar_avail": 0.00},
    "95": {"name": "emergent_herbaceous_wetlands",  "solar_avail": 0.00},
}
CLASS_CODES = list(NLCD_CLASSES.keys())


def main() -> None:
    print(f"Dataset version: {DATASET_TAG}")
    print(f"GEE source dir:  {GEE_DIR}")
    print(f"Parcel source:   {PARCEL_GPKG}")
    print(f"Output dir:      {OUT_DIR}")

    # ── Load and concatenate GEE CSVs ────────────────────────────────────────
    gee_files = sorted(GEE_DIR.glob("2021_NLCD_parcels_area_m2_*.csv"))
    if not gee_files:
        print(f"!! No GEE CSVs found in {GEE_DIR}")
        sys.exit(1)
    print(f"\nLoading {len(gee_files)} GEE CSVs...")

    frames = []
    for p in gee_files:
        df = pd.read_csv(p, dtype={"PARCEL_LID": str})
        # Drop the header/dummy row (system:index == '1_0' with PARCEL_LID == '0')
        df = df[df["system:index"].astype(str) != "1_0"].copy()
        df = df[df["PARCEL_LID"].astype(str) != "0"].copy()
        frames.append(df)

    gee = pd.concat(frames, ignore_index=True)
    gee = gee.drop(columns=["system:index", ".geo", "Year", "clnd_nm"], errors="ignore")
    print(f"  Loaded {len(gee):,} rows after dropping header/null rows")

    # Ensure all 16 class columns are present (fill missing with 0)
    for c in CLASS_CODES:
        if c not in gee.columns:
            print(f"  WARN: class column {c} missing in GEE output — filling with 0")
            gee[c] = 0.0
        gee[c] = pd.to_numeric(gee[c], errors="coerce").fillna(0.0)

    # Check for duplicate PARCEL_LIDs in GEE output
    n_dup = gee["PARCEL_LID"].duplicated().sum()
    if n_dup > 0:
        print(f"  WARN: {n_dup:,} duplicate PARCEL_LIDs in GEE output — keeping first")
        gee = gee.drop_duplicates(subset=["PARCEL_LID"], keep="first")

    # Rename class columns: '11' -> 'nlcd_11_open_water_m2', etc.
    rename = {c: f"nlcd_{c}_{NLCD_CLASSES[c]['name']}_m2" for c in CLASS_CODES}
    gee = gee.rename(columns=rename)
    area_cols = list(rename.values())

    # ── Load CONUS universe ──────────────────────────────────────────────────
    print("\nLoading CONUS parcel universe...")
    t0 = time.time()
    parcels = gpd.read_file(PARCEL_GPKG)
    parcels = parcels.drop(columns="geometry")
    parcels["PARCEL_LID"] = parcels["PARCEL_LID"].astype(str)
    print(f"  Loaded {len(parcels):,} parcels in {time.time()-t0:.0f}s")

    # ── Join ─────────────────────────────────────────────────────────────────
    print("\nJoining GEE NLCD class areas to CONUS universe...")
    keep_cols = ["PARCEL_LID", "SITE_STATE", "state_for_batch",
                 "acres", "parcel_area_m2", "size_bin"]
    merged = parcels[keep_cols].merge(
        gee[["PARCEL_LID", "Total_Area", *area_cols]],
        on="PARCEL_LID", how="left",
    )

    # Flag unmatched parcels (no GEE record)
    merged["flag_nlcd_no_value"] = merged["Total_Area"].isna()
    n_unmatched = int(merged["flag_nlcd_no_value"].sum())
    print(f"  Matched:     {len(merged) - n_unmatched:,}")
    print(f"  Unmatched:   {n_unmatched:,}")
    if n_unmatched > 0:
        miss = merged.loc[merged["flag_nlcd_no_value"],
                          ["PARCEL_LID", "state_for_batch", "size_bin"]]
        print(f"  Unmatched by state:\n{miss['state_for_batch'].value_counts().to_string()}")
        # Fill NaN class columns with 0 so downstream math works
        for c in area_cols:
            merged[c] = merged[c].fillna(0.0)
        merged["Total_Area"] = merged["Total_Area"].fillna(0.0)

    # ── Compute usable area per parcel ───────────────────────────────────────
    print("\nComputing usable area per parcel...")
    merged["total_nlcd_area_m2"] = merged[area_cols].sum(axis=1)
    # GEE Total_Area vs sum of class cols: both are reported by GEE but class
    # totals are what we multiply. Keep Total_Area for coverage diagnostic only.

    # Coverage ratio: how much of the parcel area did NLCD classify?
    # Low values (< 0.90) suggest the parcel extends outside the NLCD raster
    # extent, which should be rare for CONUS but possible at coastlines.
    merged["nlcd_coverage_ratio"] = np.where(
        merged["parcel_area_m2"] > 0,
        merged["total_nlcd_area_m2"] / merged["parcel_area_m2"],
        np.nan,
    )

    usable = np.zeros(len(merged), dtype="float64")
    for code in CLASS_CODES:
        col = rename[code]
        usable += merged[col].values * NLCD_CLASSES[code]["solar_avail"]
    merged["usable_area_nlcd_m2"] = usable
    merged["usable_area_nlcd_ac"] = merged["usable_area_nlcd_m2"] / 4046.856

    # ── Write ────────────────────────────────────────────────────────────────
    out_csv = OUT_DIR / "nlcd_full_population.csv"
    merged.to_csv(out_csv, index=False)
    print(f"\nWrote {out_csv}")

    # ── Summary ──────────────────────────────────────────────────────────────
    n = len(merged)
    n_zero = int((merged["usable_area_nlcd_m2"] == 0).sum())
    total_ac = merged["usable_area_nlcd_ac"].sum()
    low_cov = int((merged["nlcd_coverage_ratio"] < 0.90).sum())

    print(f"\n── NLCD Full-Population Summary ──────────────────────")
    print(f"  Total parcels:             {n:,}")
    print(f"  Fully excluded (= 0):      {n_zero:,}  ({n_zero/n*100:.1f}%)")
    print(f"  Unmatched (no NLCD data):  {n_unmatched:,}")
    print(f"  Low NLCD coverage (<0.90): {low_cov:,}  ({low_cov/n*100:.1f}%)")
    print(f"  Total NLCD usable area:    {total_ac:,.0f} ac  ({total_ac/1e6:.3f}M ac)")

    print("\n  By size bin:")
    merged["size_bin"] = pd.Categorical(
        merged["size_bin"], categories=["tiny","small","medium","large","xlarge"], ordered=True
    )
    summary = merged.groupby("size_bin", observed=True).agg(
        n=("PARCEL_LID", "count"),
        nlcd_zero=("usable_area_nlcd_m2", lambda x: (x == 0).sum()),
        total_nlcd_ac=("usable_area_nlcd_ac", "sum"),
        mean_nlcd_ac=("usable_area_nlcd_ac", "mean"),
        median_nlcd_ac=("usable_area_nlcd_ac", "median"),
    ).reset_index()
    print(summary.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))

    # Class-wise contribution to total usable area — shows which classes dominate
    print("\n  Class-wise contribution to total usable area:")
    contrib = []
    for code in CLASS_CODES:
        col = rename[code]
        area_m2 = merged[col].sum()
        avail = NLCD_CLASSES[code]["solar_avail"]
        usable_ac = area_m2 * avail / 4046.856
        contrib.append({
            "class": code,
            "name": NLCD_CLASSES[code]["name"],
            "solar_avail": avail,
            "total_area_M_ac": area_m2 / 4046.856 / 1e6,
            "usable_ac_M": usable_ac / 1e6,
            "pct_of_usable": usable_ac / total_ac * 100,
        })
    contrib_df = pd.DataFrame(contrib).sort_values("usable_ac_M", ascending=False)
    print(contrib_df.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))

    # Quick comparison to old sample-based totals (if present)
    cmp_path = BASE / "Scripts/method_comparison/outputs/full_population_comparison.csv"
    if cmp_path.exists():
        old = pd.read_csv(cmp_path)
        if "nlcd_total_mean_ac" in old.columns:
            old_mean = old["nlcd_total_mean_ac"].sum()
            old_median = old["nlcd_total_median_ac"].sum() if "nlcd_total_median_ac" in old.columns else float("nan")
            print(f"\n── Comparison to old sample-based estimate ──")
            print(f"  Full-population exact:          {total_ac/1e6:,.3f}M ac")
            print(f"  Old sample × N (mean-based):    {old_mean/1e6:,.3f}M ac")
            if not np.isnan(old_median):
                print(f"  Old sample × N (median-based):  {old_median/1e6:,.3f}M ac")
            print(f"  Ratio (exact / sample-mean):    {total_ac/old_mean:.3f}")

    print("\nDone.")


if __name__ == "__main__":
    main()
