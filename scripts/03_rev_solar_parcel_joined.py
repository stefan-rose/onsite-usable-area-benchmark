"""
reV solar usable-area zonal statistics for the Parcel-Joined (reV-PJ) scenario.

reV-PJ uses the original NLR parcel-joined percent-inclusion raster, which was
produced by NLR specifically for the prior manufacturing parcel universe.
In the Applied Energy paper, reV-PJ is demoted to a diagnostic subsection (it
was formerly the headline "NLR Original" scenario); we keep it in the runs so
we can report method-of-aggregation sensitivity against the Open/Reference/
Limited composites.

Inputs
  - Scripts/applied_energy_paper/intermediate/parcels_conus_2026_04_23.gpkg
      (305,123 CONUS parcels; built by 01_build_parcel_universe_2026_04_23.py)
  - Data/reV Exclusions/conus_percent_inclusion_all_parcels.tif  (nodata = 0 is invalid,
      but 0 is also the value for "fully excluded" in the composite rasters. In this
      raster, 0 was observed historically to mean "outside the valid extent" — we
      follow the same convention as the original 05_rev_full_run.py and treat 0
      as nodata via an explicit -9999 override in zonal_stats, then zero-out any
      NaN mean in usable_area_rev_m2 for reporting.)

Outputs
  Scripts/method_comparison/outputs/full_run_pj_2026_04_23/rev_<STATE>.csv  (checkpoints)
  Scripts/method_comparison/outputs/full_run_pj_2026_04_23/rev_full_population.csv

Run
  cd Scripts/method_comparison
  pixi run python -u ../applied_energy_paper/03_rev_solar_parcel_joined.py
  pixi run python -u ../applied_energy_paper/03_rev_solar_parcel_joined.py --dry-run RI

Author: Stefan Rose / PNNL
Dataset version: 2026_04_23 (post FIPS fix)
"""

from __future__ import annotations

import argparse
import sys
import time
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterstats import zonal_stats

warnings.filterwarnings("ignore", category=UserWarning)
sys.stdout.reconfigure(line_buffering=True)

# ─── Paths ──────────────────────────────────────────────────────────────────

BASE         = Path("/Users/rose501/Library/CloudStorage/OneDrive-PNNL/Desktop/IEDO")
PARCEL_GPKG  = BASE / "Scripts/applied_energy_paper/intermediate/parcels_conus_2026_04_23.gpkg"
REV_RASTER   = BASE / "Data/reV Exclusions/conus_percent_inclusion_all_parcels.tif"
OUT_BASE     = BASE / "Scripts/method_comparison/outputs"

# reV-PJ raster convention (per 05_rev_full_run.py):
#   Nodata override = -9999 (preserves pixel value 0 = fully excluded as valid).
#   In this raster 0 means "fully excluded"; there is no 255 sentinel.
REV_NODATA_OVERRIDE = -9999

RASTER_CRS         = "EPSG:5070"
CENTROID_ONLY_BINS = {"tiny", "small"}
DATASET_TAG        = "2026_04_23"


# ─── Helpers ────────────────────────────────────────────────────────────────

def sample_centroids(gdf_sub: gpd.GeoDataFrame, raster_path: Path) -> np.ndarray:
    centroids = gdf_sub.to_crs(RASTER_CRS).geometry.centroid
    xs = centroids.x.values
    ys = centroids.y.values
    with rasterio.open(raster_path) as src:
        vals = np.array(
            [v[0] for v in src.sample(zip(xs, ys), indexes=1)],
            dtype="float64",
        )
    return vals


def process_state(state: str, state_gdf: gpd.GeoDataFrame, raster_path: Path) -> pd.DataFrame:
    t_state = time.time()
    n = len(state_gdf)

    mask_centroid = state_gdf["size_bin"].isin(CENTROID_ONLY_BINS)
    gdf_centroid  = state_gdf[mask_centroid].copy()
    gdf_zonal     = state_gdf[~mask_centroid].copy()

    results = []
    n_centroid_fallback = 0

    if len(gdf_centroid) > 0:
        vals = sample_centroids(gdf_centroid, raster_path)
        # reV-PJ raster has no 255 sentinel; 0 is valid (fully excluded).
        # Parcels outside raster extent come back as NaN from rasterio sample.
        no_val = np.isnan(vals)
        cent_df = pd.DataFrame({
            "PARCEL_LID":                 gdf_centroid["PARCEL_LID"].values,
            "rev_mean_pct_inclusion":     vals,
            "rev_pixel_count":            1.0,
            "flag_rev_centroid_fallback": True,
            "flag_rev_no_value":          no_val,
        })
        results.append(cent_df)

    if len(gdf_zonal) > 0:
        gdf_zonal_proj = gdf_zonal.to_crs(RASTER_CRS)
        stats = zonal_stats(
            gdf_zonal_proj,
            str(raster_path),
            stats=["mean", "count"],
            nodata=REV_NODATA_OVERRIDE,
            all_touched=False,
        )
        zonal_df = pd.DataFrame(stats)
        zonal_df["PARCEL_LID"] = gdf_zonal["PARCEL_LID"].values
        zonal_df = zonal_df.rename(columns={
            "mean":  "rev_mean_pct_inclusion",
            "count": "rev_pixel_count",
        })
        zonal_df["flag_rev_centroid_fallback"] = False
        zonal_df["flag_rev_no_value"]          = False

        nan_mask = zonal_df["rev_mean_pct_inclusion"].isna()
        n_centroid_fallback = int(nan_mask.sum())
        if nan_mask.any():
            fallback_vals = sample_centroids(gdf_zonal[nan_mask.values], raster_path)
            no_val_fb = np.isnan(fallback_vals)
            zonal_df.loc[nan_mask, "rev_mean_pct_inclusion"]    = fallback_vals
            zonal_df.loc[nan_mask, "rev_pixel_count"]            = 1.0
            zonal_df.loc[nan_mask, "flag_rev_centroid_fallback"] = True
            zonal_df.loc[nan_mask, "flag_rev_no_value"]          = no_val_fb

        zonal_df["flag_rev_no_value"] |= zonal_df["rev_mean_pct_inclusion"].isna()
        results.append(zonal_df)

    state_results = pd.concat(results, ignore_index=True)

    meta_cols = ["PARCEL_LID", "SITE_STATE", "state_for_batch",
                 "acres", "parcel_area_m2", "size_bin"]
    meta = state_gdf[meta_cols].reset_index(drop=True)
    state_results = meta.merge(state_results, on="PARCEL_LID", how="left")

    state_results["usable_area_rev_m2"] = (
        state_results["rev_mean_pct_inclusion"].fillna(0) * state_results["parcel_area_m2"]
    )
    state_results["usable_area_rev_ac"] = state_results["usable_area_rev_m2"] / 4046.856
    state_results["flag_rev_low_pixel_count"] = (
        state_results["rev_pixel_count"].notna() & (state_results["rev_pixel_count"] < 3)
    )

    elapsed = time.time() - t_state
    n_zero  = int((state_results["usable_area_rev_m2"] == 0).sum())
    print(f"  {state}: {n:,} parcels | {n_zero:,} fully excluded | "
          f"{n_centroid_fallback} centroid fallbacks | {elapsed:.0f}s")
    return state_results


# ─── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--dry-run", nargs="+", metavar="STATE",
        help="Run only on the given 2-letter state abbrevs; writes to a _dryrun_ dir.",
    )
    args = ap.parse_args()
    dry = bool(args.dry_run)
    dry_states = set(args.dry_run) if dry else None

    print(f"Dataset version: {DATASET_TAG}")
    print(f"Parcel source:   {PARCEL_GPKG}")
    print(f"Raster:          {REV_RASTER}")
    if not REV_RASTER.exists():
        print(f"!! Missing raster: {REV_RASTER}")
        sys.exit(1)
    if dry:
        print(f"DRY RUN mode. States: {sorted(dry_states)}")

    print("Loading CONUS parcel GPKG...")
    t0 = time.time()
    gdf = gpd.read_file(PARCEL_GPKG)
    print(f"  Loaded {len(gdf):,} parcels in {time.time()-t0:.0f}s  CRS: {gdf.crs}")
    gdf["size_bin"] = pd.Categorical(
        gdf["size_bin"],
        categories=["tiny", "small", "medium", "large", "xlarge"],
        ordered=True,
    )

    if dry:
        gdf = gdf[gdf["state_for_batch"].isin(dry_states)].copy()
        print(f"  Dry-run filter → {len(gdf):,} parcels in {sorted(dry_states)}")

    states = sorted(gdf["state_for_batch"].dropna().unique())
    print(f"  {len(states)} states, {len(gdf):,} parcels ready")

    suffix = f"_dryrun_{'_'.join(sorted(dry_states))}" if dry else ""
    out_dir = OUT_BASE / f"full_run_pj_{DATASET_TAG}{suffix}"
    out_dir.mkdir(parents=True, exist_ok=True)
    final_csv = out_dir / "rev_full_population.csv"

    if final_csv.exists():
        print(f"\n── reV-PJ already complete — skipping (delete {final_csv} to rerun) ────")
        return

    print(f"\n{'='*70}\n  Scenario: reV Parcel Joined  ({REV_RASTER.name})\n{'='*70}")

    all_results = []
    t_scenario = time.time()
    for i, state in enumerate(states, 1):
        checkpoint = out_dir / f"rev_{state}.csv"
        if checkpoint.exists():
            print(f"  {state}: already done — loading from checkpoint")
            all_results.append(pd.read_csv(checkpoint, dtype={"PARCEL_LID": str}))
            continue

        state_gdf = gdf[gdf["state_for_batch"] == state].copy()
        state_result = process_state(state, state_gdf, REV_RASTER)
        state_result.to_csv(checkpoint, index=False)
        all_results.append(state_result)

        elapsed  = time.time() - t_scenario
        pct_done = i / len(states)
        eta = (elapsed / pct_done) * (1 - pct_done) / 60
        print(f"    [{i}/{len(states)}  {pct_done*100:.0f}%  ETA ~{eta:.0f} min]")

    print("\nMerging results...")
    final = pd.concat(all_results, ignore_index=True)
    final.to_csv(final_csv, index=False)

    n          = len(final)
    n_zero     = int((final["usable_area_rev_m2"] == 0).sum())
    n_no_val   = int(final["flag_rev_no_value"].sum())
    n_fallback = int(final["flag_rev_centroid_fallback"].sum())
    total_ac   = final["usable_area_rev_ac"].sum()

    print(f"\n── reV-PJ Summary ───────────────────────────────────────")
    print(f"  Total parcels:            {n:,}")
    print(f"  Fully excluded (= 0):     {n_zero:,}  ({n_zero/n*100:.1f}%)")
    print(f"  Outside raster extent:    {n_no_val:,}")
    print(f"  Centroid fallback used:   {n_fallback:,}  ({n_fallback/n*100:.1f}%)")
    print(f"  Total reV usable area:    {total_ac:,.0f} ac  ({total_ac/1e6:.3f}M ac)")
    print("\n  By size bin:")
    summary = final.groupby("size_bin", observed=True).agg(
        n=("PARCEL_LID", "count"),
        rev_zero=("usable_area_rev_m2", lambda x: (x == 0).sum()),
        total_rev_ac=("usable_area_rev_ac", "sum"),
        median_rev_ac=("usable_area_rev_ac", "median"),
    ).reset_index()
    print(summary.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    print(f"\n  Scenario runtime: {(time.time()-t_scenario)/60:.1f} min")
    print("Done.")


if __name__ == "__main__":
    main()
