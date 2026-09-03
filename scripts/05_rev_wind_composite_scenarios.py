"""
reV onshore wind usable-area zonal statistics for three composite scenarios.

Mirrors 02_rev_solar_composite_scenarios.py architecture — the wind rasters
use the same conventions as the solar composites (EPSG:5070, nodata=255,
~92 m resolution). Scenarios: Open, Reference, Limited at 115 m hub height /
170 m rotor diameter (NLR reV standard onshore wind configuration).

Inputs
  - Scripts/applied_energy_paper/intermediate/parcels_conus_2026_04_23.gpkg
      (305,123 CONUS parcels; built by 01_build_parcel_universe_2026_04_23.py)
  - Data/reV Exclusions/Wind/lbw_<scenario>_115hh_170rd.tif
      (Open, Reference, Limited composite exclusion rasters; nodata=255)

Outputs
  Scripts/method_comparison/outputs/full_run_wind_<scenario>_2026_04_23/
      rev_<STATE>.csv           (per-state checkpoints)
      rev_full_population.csv   (final merged result)

Design note: we apply no additional binary exclusions here (< 1 ac parcel,
urban, airport buffer, DoD, USFWS). The reV rasters already encode DoD,
critical habitat, and urban at the raster level. The < 1 ac and airport
buffer exclusions properly belong to the NLCD wind method (Task 1D), not
the reV wind method. A `flag_wind_below_1ac` column is included for
traceability but does not modify usable_area_rev_ac.

Run
  cd Scripts/method_comparison
  pixi run python -u ../applied_energy_paper/05_rev_wind_composite_scenarios.py
  pixi run python -u ../applied_energy_paper/05_rev_wind_composite_scenarios.py --dry-run RI
  pixi run python -u ../applied_energy_paper/05_rev_wind_composite_scenarios.py --scenarios open

Author: Stefan Rose / PNNL
Dataset version: 2026_04_23 (post FIPS fix)
Wind config: 115 m hub height / 170 m rotor diameter (NLR reV standard)
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

# Path configuration: load BASE and named input paths from config.toml at
# the repo root (falls back to config.example.toml if config.toml is absent).
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
from _config import BASE  # noqa: E402
PARCEL_GPKG  = BASE / "Scripts/applied_energy_paper/intermediate/parcels_conus_2026_04_23.gpkg"
REV_DIR      = BASE / "Data/reV Exclusions/Wind"
OUT_BASE     = BASE / "Scripts/method_comparison/outputs"

SCENARIOS = {
    "open":      REV_DIR / "lbw_open_115hh_170rd.tif",
    "reference": REV_DIR / "lbw_reference_115hh_170rd.tif",
    "limited":   REV_DIR / "lbw_limited_115hh_170rd.tif",
}

# Same raster conventions as solar composites
REV_NODATA_OVERRIDE = 255
RASTER_CRS          = "EPSG:5070"
CENTROID_ONLY_BINS  = {"tiny", "small"}
DATASET_TAG         = "2026_04_23"
ONE_ACRE_M2         = 4046.856  # for flag_wind_below_1ac


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
    # nodata=255 → NaN (outside raster extent or truly missing)
    vals[vals == REV_NODATA_OVERRIDE] = np.nan
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
    state_results["usable_area_rev_ac"] = state_results["usable_area_rev_m2"] / ONE_ACRE_M2
    state_results["flag_rev_low_pixel_count"] = (
        state_results["rev_pixel_count"].notna() & (state_results["rev_pixel_count"] < 3)
    )
    # Diagnostic: parcel too small for utility-scale wind (< 1 acre). Traceability flag only;
    # does NOT modify usable_area_rev_ac. NLCD wind method is where binary exclusions live.
    state_results["flag_wind_below_1ac"] = state_results["parcel_area_m2"] < ONE_ACRE_M2

    elapsed = time.time() - t_state
    n_zero  = int((state_results["usable_area_rev_m2"] == 0).sum())
    print(f"  {state}: {n:,} parcels | {n_zero:,} fully excluded | "
          f"{n_centroid_fallback} centroid fallbacks | {elapsed:.0f}s")
    return state_results


def run_scenario(scenario: str, raster_path: Path, gdf: gpd.GeoDataFrame,
                 out_dir: Path) -> None:
    print(f"\n{'='*70}")
    print(f"  Scenario: reV Wind {scenario.capitalize()}  ({raster_path.name})")
    print(f"{'='*70}")
    if not raster_path.exists():
        print(f"  !! Missing raster, skipping: {raster_path}")
        return

    final_csv = out_dir / "rev_full_population.csv"
    if final_csv.exists():
        print(f"  Already complete — skipping (delete {final_csv} to rerun)")
        return
    out_dir.mkdir(parents=True, exist_ok=True)

    states = sorted(gdf["state_for_batch"].dropna().unique())
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

        elapsed  = time.time() - t_scenario
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
    n_below_1ac = int(final["flag_wind_below_1ac"].sum())
    total_ac   = final["usable_area_rev_ac"].sum()

    print(f"\n── reV Wind {scenario.capitalize()} Summary ─────────────────────────────")
    print(f"  Total parcels:               {n:,}")
    print(f"  Fully excluded (= 0):        {n_zero:,}  ({n_zero/n*100:.1f}%)")
    print(f"  Outside raster extent:       {n_no_val:,}")
    print(f"  Centroid fallback used:      {n_fallback:,}  ({n_fallback/n*100:.1f}%)")
    print(f"  Parcels < 1 ac (diag only):  {n_below_1ac:,}  ({n_below_1ac/n*100:.1f}%)")
    print(f"  Total reV usable area:       {total_ac:,.0f} ac  ({total_ac/1e6:.3f}M ac)")

    print("\n  By size bin:")
    final["size_bin"] = pd.Categorical(
        final["size_bin"], categories=["tiny","small","medium","large","xlarge"], ordered=True,
    )
    summary = final.groupby("size_bin", observed=True).agg(
        n=("PARCEL_LID", "count"),
        rev_zero=("usable_area_rev_m2", lambda x: (x == 0).sum()),
        total_rev_ac=("usable_area_rev_ac", "sum"),
        median_rev_ac=("usable_area_rev_ac", "median"),
    ).reset_index()
    print(summary.to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    print(f"\n  Scenario runtime: {(time.time()-t_scenario)/60:.1f} min")


# ─── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--scenarios", nargs="+", choices=list(SCENARIOS.keys()),
        default=list(SCENARIOS.keys()),
        help="Which wind scenarios to run (default: all three).",
    )
    ap.add_argument(
        "--dry-run", nargs="+", metavar="STATE",
        help="Run only on the given 2-letter state abbrevs; writes to a _dryrun_ dir.",
    )
    args = ap.parse_args()
    dry = bool(args.dry_run)
    dry_states = set(args.dry_run) if dry else None
    scenarios_to_run = args.scenarios

    print(f"Dataset version: {DATASET_TAG}")
    print(f"Parcel source:   {PARCEL_GPKG}")
    print(f"Wind config:     115 m hub height / 170 m rotor diameter")
    if dry:
        print(f"DRY RUN mode. States: {sorted(dry_states)}  Scenarios: {scenarios_to_run}")
    else:
        print(f"Scenarios: {scenarios_to_run}")

    print("\nLoading CONUS parcel GPKG...")
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
    t_all = time.time()
    for scenario in scenarios_to_run:
        out_dir = OUT_BASE / f"full_run_wind_{scenario}_{DATASET_TAG}{suffix}"
        run_scenario(scenario, SCENARIOS[scenario], gdf, out_dir)

    print(f"\n{'='*70}")
    print(f"All scenarios complete. Total runtime: {(time.time()-t_all)/60:.1f} min")
    print("Done.")


if __name__ == "__main__":
    main()
