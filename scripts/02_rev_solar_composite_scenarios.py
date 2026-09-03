"""
reV solar usable-area zonal statistics for the composite-exclusion scenarios.

Scenarios (Lopez et al. 2024, NLR TP-6A20-91900):
  reV Open      — Least restrictive. Physical obstacles + legally protected lands.
  reV Reference — Moderate. Existing ordinances, regulatory setbacks, USFS/BLM.
  reV Limited   — Most restrictive. Max setbacks, 90th-pct ordinances, habitat/defense.

Inputs
  - Scripts/applied_energy_paper/intermediate/parcels_conus_2026_04_23.gpkg
      (305,123 CONUS parcels; built by 01_build_parcel_universe_2026_04_23.py)
  - Data/reV Exclusions/composite_exclusions_{open,reference,limited}.tif  (nodata=255)

Design
  - Load the compact CONUS parcel GPKG once; process one state at a time.
  - tiny + small parcels (<1 ac) sampled at centroid (raster is 90m; polygons this small
    rarely contain a pixel centre).
  - medium / large / xlarge use rasterstats.zonal_stats with centroid fallback.
  - All three scenarios processed sequentially. Per-scenario per-state checkpoints
    make the run safe to interrupt/restart.

Outputs (per scenario)
  Scripts/method_comparison/outputs/full_run_<scenario>_2026_04_23/rev_<STATE>.csv  (checkpoints)
  Scripts/method_comparison/outputs/full_run_<scenario>_2026_04_23/rev_full_population.csv

Run
  cd Scripts/method_comparison
  pixi run python -u ../applied_energy_paper/02_rev_solar_composite_scenarios.py

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

# ─── Paths & scenarios ──────────────────────────────────────────────────────

BASE         = Path("/Users/rose501/Library/CloudStorage/OneDrive-PNNL/Desktop/IEDO")
PARCEL_GPKG  = BASE / "Scripts/applied_energy_paper/intermediate/parcels_conus_2026_04_23.gpkg"
REV_DIR      = BASE / "Data/reV Exclusions"
OUT_BASE     = BASE / "Scripts/method_comparison/outputs"

SCENARIOS = {
    "open":      REV_DIR / "composite_exclusions_open.tif",
    "reference": REV_DIR / "composite_exclusions_reference.tif",
    "limited":   REV_DIR / "composite_exclusions_limited.tif",
}

REV_NODATA         = 255.0
RASTER_CRS         = "EPSG:5070"
CENTROID_ONLY_BINS = {"tiny", "small"}
DATASET_TAG        = "2026_04_23"


# ─── Helpers ────────────────────────────────────────────────────────────────

def sample_centroids(gdf_sub: gpd.GeoDataFrame, raster_path: Path) -> np.ndarray:
    """Point-sample raster at parcel centroids. 255 = outside extent."""
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

    # Centroid-only (tiny + small)
    if len(gdf_centroid) > 0:
        vals = sample_centroids(gdf_centroid, raster_path)
        no_val = vals == REV_NODATA
        vals[no_val] = np.nan
        cent_df = pd.DataFrame({
            "PARCEL_LID":                 gdf_centroid["PARCEL_LID"].values,
            "rev_mean_pct_inclusion":     vals,
            "rev_pixel_count":            1.0,
            "flag_rev_centroid_fallback": True,
            "flag_rev_no_value":          no_val,
        })
        results.append(cent_df)

    # Zonal stats (medium/large/xlarge)
    if len(gdf_zonal) > 0:
        gdf_zonal_proj = gdf_zonal.to_crs(RASTER_CRS)
        stats = zonal_stats(
            gdf_zonal_proj,
            str(raster_path),
            stats=["mean", "count"],
            nodata=REV_NODATA,
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

        # Centroid fallback for polygons with no intersecting pixel centre
        nan_mask = zonal_df["rev_mean_pct_inclusion"].isna()
        n_centroid_fallback = int(nan_mask.sum())
        if nan_mask.any():
            fallback_vals = sample_centroids(gdf_zonal[nan_mask.values], raster_path)
            no_val_fb = fallback_vals == REV_NODATA
            fallback_vals[no_val_fb] = np.nan
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
    n_zero = int((state_results["usable_area_rev_m2"] == 0).sum())
    print(f"  {state}: {n:,} parcels | {n_zero:,} fully excluded | "
          f"{n_centroid_fallback} centroid fallbacks | {elapsed:.0f}s")
    return state_results


# ─── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--dry-run",
        nargs="+",
        metavar="STATE",
        help="Run only on the given 2-letter state abbrevs (e.g. --dry-run RI) "
             "and write to a _dryrun_ output dir instead of the full-run dir.",
    )
    ap.add_argument(
        "--scenarios",
        nargs="+",
        choices=list(SCENARIOS.keys()),
        help="Subset of scenarios to run (default: all three).",
    )
    args = ap.parse_args()

    scenarios_to_run = {k: SCENARIOS[k] for k in (args.scenarios or list(SCENARIOS.keys()))}
    dry = bool(args.dry_run)
    dry_states = set(args.dry_run) if dry else None

    print(f"Dataset version: {DATASET_TAG}")
    print(f"Parcel source:   {PARCEL_GPKG}")
    if dry:
        print(f"DRY RUN mode. States: {sorted(dry_states)}  Scenarios: {list(scenarios_to_run)}")
    print("Loading CONUS parcel GPKG...")
    t0 = time.time()
    gdf = gpd.read_file(PARCEL_GPKG)
    print(f"  Loaded {len(gdf):,} parcels in {time.time()-t0:.0f}s  CRS: {gdf.crs}")
    # Ensure size_bin is categorical with the expected ordering
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

    t_all = time.time()
    for scenario, raster_path in scenarios_to_run.items():
        suffix = f"_dryrun_{'_'.join(sorted(dry_states))}" if dry else ""
        out_dir = OUT_BASE / f"full_run_{scenario}_{DATASET_TAG}{suffix}"
        out_dir.mkdir(parents=True, exist_ok=True)
        final_csv = out_dir / "rev_full_population.csv"

        if final_csv.exists():
            print(f"\n── {scenario.upper()} already complete — skipping ────────────")
            continue

        print(f"\n{'='*70}\n  Scenario: reV {scenario.capitalize()}  ({raster_path.name})\n{'='*70}")
        if not raster_path.exists():
            print(f"  !! Missing raster: {raster_path}")
            continue

        all_results = []
        t_scenario = time.time()
        for i, state in enumerate(states, 1):
            checkpoint = out_dir / f"rev_{state}.csv"
            if checkpoint.exists():
                print(f"  {state}: already done — loading from checkpoint")
                all_results.append(pd.read_csv(checkpoint, dtype={"PARCEL_LID": str}))
                continue

            state_gdf = gdf[gdf["state_for_batch"] == state].copy()
            state_result = process_state(state, state_gdf, raster_path)
            state_result.to_csv(checkpoint, index=False)
            all_results.append(state_result)

            elapsed = time.time() - t_scenario
            pct_done = i / len(states)
            eta = (elapsed / pct_done) * (1 - pct_done) / 60
            print(f"    [{i}/{len(states)}  {pct_done*100:.0f}%  ETA ~{eta:.0f} min]")

        print(f"\nMerging {scenario} results...")
        final = pd.concat(all_results, ignore_index=True)
        final.to_csv(final_csv, index=False)

        n          = len(final)
        n_zero     = int((final["usable_area_rev_m2"] == 0).sum())
        n_no_val   = int(final["flag_rev_no_value"].sum())
        n_fallback = int(final["flag_rev_centroid_fallback"].sum())
        total_ac   = final["usable_area_rev_ac"].sum()

        print(f"\n── reV {scenario.capitalize()} Summary ─────────────────────────────")
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

    print(f"\n{'='*70}\nAll scenarios complete. Total runtime: {(time.time()-t_all)/60:.1f} min")
    print("Done.")


if __name__ == "__main__":
    main()
