#!/usr/bin/env python3
"""
Task 1E: Forest-class availability sensitivity for NLCD solar usable area.

Recomputes parcel-level NLCD usable area under 5 forest-availability scenarios
while holding all other NLCD class availability percentages constant. Reports
total, size-bin decomposition, and xlarge-bin emphasis.

Scenarios (deciduous / evergreen / mixed):
  S1 Zero-forest           0%  /  0%  /  0%   Lopez 2012 binary exclusion; Hoffacker/CEEC 2015
  S2 Baseline (current)   10%  /  5%  / 15%   Internal methods doc (Janke, Shorabeh, van Haaren, etc.)
  S3 Uniform low          10%  / 10%  / 10%   Simplified alternative
  S4 VA DEQ upper         50%  / 50%  / 50%   Virginia DEQ observed disturbance share — EMPIRICAL, NOT NORMATIVE
  S5 Doubled baseline     20%  / 10%  / 30%   Sensitivity span check

Notes:
  - All non-forest class availability percentages held fixed at reference values
    (see Communications/Paper/Applied Energy/nlcd_availability_reference.md).
  - Classes 12 (perennial ice/snow) and 90/95 (wetlands) assumed 0% for solar.
  - S4 is an EMPIRICAL upper bound from VA observed project footprints; it
    reflects what developers built, not what is technically available. Included
    as a sensitivity ceiling only; narrative treatment TBD.

Inputs:
  Scripts/method_comparison/outputs/full_run_nlcd_2026_04_23/nlcd_full_population.csv

Outputs:
  Scripts/applied_energy_paper/outputs/forest_sensitivity/
    forest_sensitivity_parcel_level.parquet   (per-parcel S1..S5 usable area)
    forest_sensitivity_summary_totals.csv     (CONUS totals per scenario, acres)
    forest_sensitivity_by_size_bin.csv        (size_bin x scenario, acres)
    forest_sensitivity_xlarge_breakdown.csv   (xlarge-bin detail)
    run_log.txt
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO = Path("/Users/rose501/Library/CloudStorage/OneDrive-PNNL/Desktop/IEDO")
NLCD_CSV = REPO / "Scripts/method_comparison/outputs/full_run_nlcd_2026_04_23/nlcd_full_population.csv"
OUT_DIR = REPO / "Scripts/applied_energy_paper/outputs/forest_sensitivity"
OUT_DIR.mkdir(parents=True, exist_ok=True)

M2_PER_ACRE = 4046.8564224

# ---------------------------------------------------------------------------
# Non-forest NLCD availability (% as fraction) — held fixed across scenarios
# Source: Communications/Paper/Applied Energy/nlcd_availability_reference.md
# ---------------------------------------------------------------------------
NON_FOREST_AVAIL = {
    "nlcd_11_open_water_m2":                   0.00,
    "nlcd_12_perennial_ice_snow_m2":           0.00,
    "nlcd_21_developed_open_space_m2":         0.30,
    "nlcd_22_developed_low_intensity_m2":      0.30,
    "nlcd_23_developed_medium_intensity_m2":   0.20,
    "nlcd_24_developed_high_intensity_m2":     0.20,
    "nlcd_31_barren_land_m2":                  0.80,
    "nlcd_52_shrub_scrub_m2":                  0.70,
    "nlcd_71_grassland_herbaceous_m2":         0.70,
    "nlcd_81_pasture_hay_m2":                  0.60,
    "nlcd_82_cultivated_crops_m2":             0.60,
    "nlcd_90_woody_wetlands_m2":               0.00,
    "nlcd_95_emergent_herbaceous_wetlands_m2": 0.00,
}

FOREST_COLS = {
    "deciduous": "nlcd_41_deciduous_forest_m2",
    "evergreen": "nlcd_42_evergreen_forest_m2",
    "mixed":     "nlcd_43_mixed_forest_m2",
}

# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------
SCENARIOS = {
    "S1_zero_forest":     {"deciduous": 0.00, "evergreen": 0.00, "mixed": 0.00,
                           "label": "Zero-forest (Lopez 2012 / CEEC binary)"},
    "S2_baseline":        {"deciduous": 0.10, "evergreen": 0.05, "mixed": 0.15,
                           "label": "Baseline (current methods)"},
    "S3_uniform_10":      {"deciduous": 0.10, "evergreen": 0.10, "mixed": 0.10,
                           "label": "Uniform 10%"},
    "S4_va_deq_upper":    {"deciduous": 0.50, "evergreen": 0.50, "mixed": 0.50,
                           "label": "VA DEQ empirical upper bound (NOT normative)"},
    "S5_doubled":         {"deciduous": 0.20, "evergreen": 0.10, "mixed": 0.30,
                           "label": "Doubled baseline"},
}

SIZE_BIN_ORDER = ["tiny", "small", "medium", "large", "xlarge"]


def log(msg: str, log_lines: list[str]) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    log_lines.append(line)


def main() -> int:
    log_lines: list[str] = []
    log(f"Loading {NLCD_CSV}", log_lines)
    df = pd.read_csv(NLCD_CSV)
    log(f"Loaded {len(df):,} parcels", log_lines)

    # Sanity check: columns present
    required = list(NON_FOREST_AVAIL.keys()) + list(FOREST_COLS.values()) + ["size_bin", "PARCEL_LID"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        log(f"ERROR: missing columns: {missing}", log_lines)
        return 1

    # Sanity check vs baseline: S2 should closely match usable_area_nlcd_ac
    # (any mismatch indicates drift from reference availability values)
    # ---------------------------------------------------------------------
    # Non-forest contribution (constant across scenarios)
    # ---------------------------------------------------------------------
    log("Computing non-forest contribution (m2)", log_lines)
    nonforest_m2 = np.zeros(len(df), dtype=np.float64)
    for col, avail in NON_FOREST_AVAIL.items():
        nonforest_m2 += df[col].fillna(0.0).to_numpy() * avail

    # ---------------------------------------------------------------------
    # Per-scenario forest contribution and total
    # ---------------------------------------------------------------------
    dec = df[FOREST_COLS["deciduous"]].fillna(0.0).to_numpy()
    evg = df[FOREST_COLS["evergreen"]].fillna(0.0).to_numpy()
    mix = df[FOREST_COLS["mixed"]].fillna(0.0).to_numpy()

    out = df[["PARCEL_LID", "SITE_STATE", "acres", "size_bin",
              FOREST_COLS["deciduous"], FOREST_COLS["evergreen"], FOREST_COLS["mixed"]]].copy()
    out["nonforest_usable_m2"] = nonforest_m2

    for sid, params in SCENARIOS.items():
        forest_m2 = (dec * params["deciduous"] +
                     evg * params["evergreen"] +
                     mix * params["mixed"])
        total_m2 = nonforest_m2 + forest_m2
        out[f"{sid}_forest_m2"] = forest_m2
        out[f"{sid}_usable_m2"] = total_m2
        out[f"{sid}_usable_ac"] = total_m2 / M2_PER_ACRE
        total_ac = total_m2.sum() / M2_PER_ACRE
        log(f"  {sid:22s}  total = {total_ac:,.0f} ac  ({params['label']})", log_lines)

    # Sanity: baseline vs stored usable_area_nlcd_ac
    stored_total = df["usable_area_nlcd_ac"].sum()
    baseline_total = out["S2_baseline_usable_ac"].sum()
    delta_pct = 100.0 * (baseline_total - stored_total) / stored_total
    log(f"Sanity: S2 baseline total = {baseline_total:,.0f} ac vs stored {stored_total:,.0f} ac "
        f"(delta {delta_pct:+.3f}%)", log_lines)
    if abs(delta_pct) > 0.5:
        log("WARNING: S2 baseline drift > 0.5% — check NON_FOREST_AVAIL against reference doc", log_lines)

    # ---------------------------------------------------------------------
    # Write parcel-level output
    # ---------------------------------------------------------------------
    parcel_csv = OUT_DIR / "forest_sensitivity_parcel_level.csv"
    out.to_csv(parcel_csv, index=False)
    log(f"Wrote {parcel_csv}", log_lines)

    # ---------------------------------------------------------------------
    # Summary totals (CONUS)
    # ---------------------------------------------------------------------
    summary_rows = []
    for sid, params in SCENARIOS.items():
        total_ac = out[f"{sid}_usable_ac"].sum()
        forest_ac = out[f"{sid}_forest_m2"].sum() / M2_PER_ACRE
        summary_rows.append({
            "scenario_id": sid,
            "scenario_label": params["label"],
            "deciduous_avail_pct": params["deciduous"] * 100,
            "evergreen_avail_pct": params["evergreen"] * 100,
            "mixed_avail_pct":     params["mixed"] * 100,
            "total_usable_ac":     round(total_ac, 0),
            "forest_contrib_ac":   round(forest_ac, 0),
            "forest_share_of_total_pct": round(100.0 * forest_ac / total_ac, 2) if total_ac > 0 else 0.0,
            "delta_vs_baseline_ac": None,  # filled below
            "delta_vs_baseline_pct": None,
        })
    summary = pd.DataFrame(summary_rows)
    baseline_ac = float(summary.loc[summary["scenario_id"] == "S2_baseline", "total_usable_ac"].iloc[0])
    summary["delta_vs_baseline_ac"] = (summary["total_usable_ac"] - baseline_ac).round(0)
    summary["delta_vs_baseline_pct"] = (100.0 * (summary["total_usable_ac"] - baseline_ac) / baseline_ac).round(2)
    summary_path = OUT_DIR / "forest_sensitivity_summary_totals.csv"
    summary.to_csv(summary_path, index=False)
    log(f"Wrote {summary_path}", log_lines)

    # ---------------------------------------------------------------------
    # Size-bin decomposition
    # ---------------------------------------------------------------------
    bin_rows = []
    for sb in SIZE_BIN_ORDER:
        sub = out[out["size_bin"] == sb]
        if sub.empty:
            continue
        row = {"size_bin": sb, "n_parcels": len(sub)}
        for sid in SCENARIOS:
            row[f"{sid}_ac"] = round(sub[f"{sid}_usable_ac"].sum(), 0)
        bin_rows.append(row)
    bins = pd.DataFrame(bin_rows)

    # Append % deltas vs baseline per bin
    for sid in SCENARIOS:
        bins[f"{sid}_delta_pct"] = (
            100.0 * (bins[f"{sid}_ac"] - bins["S2_baseline_ac"]) / bins["S2_baseline_ac"]
        ).round(2)
    bin_path = OUT_DIR / "forest_sensitivity_by_size_bin.csv"
    bins.to_csv(bin_path, index=False)
    log(f"Wrote {bin_path}", log_lines)

    # ---------------------------------------------------------------------
    # XL breakdown: forest composition and per-scenario shares
    # ---------------------------------------------------------------------
    xl = out[out["size_bin"] == "xlarge"].copy()
    if len(xl) > 0:
        xl_forest_raw_m2 = (xl[FOREST_COLS["deciduous"]].sum()
                            + xl[FOREST_COLS["evergreen"]].sum()
                            + xl[FOREST_COLS["mixed"]].sum())
        xl_breakdown = {
            "n_xlarge_parcels": len(xl),
            "xl_deciduous_raw_ac":  round(xl[FOREST_COLS["deciduous"]].sum() / M2_PER_ACRE, 0),
            "xl_evergreen_raw_ac":  round(xl[FOREST_COLS["evergreen"]].sum() / M2_PER_ACRE, 0),
            "xl_mixed_raw_ac":      round(xl[FOREST_COLS["mixed"]].sum() / M2_PER_ACRE, 0),
            "xl_forest_raw_total_ac": round(xl_forest_raw_m2 / M2_PER_ACRE, 0),
        }
        for sid, params in SCENARIOS.items():
            xl_breakdown[f"{sid}_total_ac"]  = round(xl[f"{sid}_usable_ac"].sum(), 0)
            xl_breakdown[f"{sid}_forest_ac"] = round(xl[f"{sid}_forest_m2"].sum() / M2_PER_ACRE, 0)
        xl_path = OUT_DIR / "forest_sensitivity_xlarge_breakdown.csv"
        pd.DataFrame([xl_breakdown]).to_csv(xl_path, index=False)
        log(f"Wrote {xl_path}", log_lines)

    # ---------------------------------------------------------------------
    # Write log
    # ---------------------------------------------------------------------
    log_path = OUT_DIR / "run_log.txt"
    log_path.write_text("\n".join(log_lines) + "\n")
    print(f"\nRun log: {log_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
