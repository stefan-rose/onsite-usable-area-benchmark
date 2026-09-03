#!/usr/bin/env python3
"""
Task 1D (part 1 of 2): NLCD wind usable area — percentage-only method.

Applies per-class wind availability percentages to the NLCD class areas in
the full-population CSV. This is the primary NLCD wind estimate, parallel to
the NLCD solar method (for apples-to-apples methodology comparison).

Wind availability percentages are from
`Communications/Paper/Applied Energy/nlcd_availability_reference.md`
(see manuscript §3 and Appendix A).

NO binary exclusions applied here — those are handled in the R companion script
`08_nlcd_wind_binary_exclusions.R` as a sensitivity layer.

Inputs:
  Scripts/method_comparison/outputs/full_run_nlcd_2026_04_23/nlcd_full_population.csv

Outputs:
  Scripts/applied_energy_paper/outputs/nlcd_wind/
    nlcd_wind_percentage_only.csv     (per-parcel usable area, wind)
    nlcd_wind_percentage_only_summary.csv  (CONUS total + size-bin decomposition)
    run_log.txt
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

import numpy as np
import pandas as pd

# Path configuration: load BASE and named input paths from config.toml at
# the repo root (falls back to config.example.toml if config.toml is absent).
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
from _config import BASE  # noqa: E402
REPO = BASE  # backwards-compat alias used by this script
NLCD_CSV = REPO / "Scripts/method_comparison/outputs/full_run_nlcd_2026_04_23/nlcd_full_population.csv"
OUT_DIR = REPO / "Scripts/applied_energy_paper/outputs/nlcd_wind"
OUT_DIR.mkdir(parents=True, exist_ok=True)

M2_PER_ACRE = 4046.8564224
SIZE_BIN_ORDER = ["tiny", "small", "medium", "large", "xlarge"]

# Per-class wind availability (fraction), from nlcd_availability_reference.md
WIND_AVAIL = {
    "nlcd_11_open_water_m2":                   0.00,
    "nlcd_12_perennial_ice_snow_m2":           0.00,
    "nlcd_21_developed_open_space_m2":         0.20,
    "nlcd_22_developed_low_intensity_m2":      0.10,
    "nlcd_23_developed_medium_intensity_m2":   0.05,
    "nlcd_24_developed_high_intensity_m2":     0.05,
    "nlcd_31_barren_land_m2":                  0.80,
    "nlcd_41_deciduous_forest_m2":             0.10,
    "nlcd_42_evergreen_forest_m2":             0.05,
    "nlcd_43_mixed_forest_m2":                 0.10,
    "nlcd_52_shrub_scrub_m2":                  0.70,
    "nlcd_71_grassland_herbaceous_m2":         0.70,
    "nlcd_81_pasture_hay_m2":                  0.70,
    "nlcd_82_cultivated_crops_m2":             0.70,
    "nlcd_90_woody_wetlands_m2":               0.00,
    "nlcd_95_emergent_herbaceous_wetlands_m2": 0.00,
}


def log(msg: str, lines: list[str]) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    lines.append(line)


def main() -> int:
    lines: list[str] = []
    log(f"Loading {NLCD_CSV}", lines)
    df = pd.read_csv(NLCD_CSV)
    log(f"Loaded {len(df):,} parcels", lines)

    missing = [c for c in WIND_AVAIL if c not in df.columns]
    if missing:
        log(f"ERROR: missing NLCD columns: {missing}", lines)
        return 1

    usable_m2 = np.zeros(len(df), dtype=np.float64)
    for col, avail in WIND_AVAIL.items():
        usable_m2 += df[col].fillna(0.0).to_numpy() * avail

    out = df[["PARCEL_LID", "SITE_STATE", "acres", "parcel_area_m2",
              "size_bin", "total_nlcd_area_m2", "usable_area_nlcd_m2", "usable_area_nlcd_ac"]].rename(
        columns={"usable_area_nlcd_m2": "usable_area_nlcd_solar_m2",
                 "usable_area_nlcd_ac": "usable_area_nlcd_solar_ac"}).copy()
    out["usable_area_nlcd_wind_m2"] = usable_m2
    out["usable_area_nlcd_wind_ac"] = usable_m2 / M2_PER_ACRE

    # Diagnostic: count parcels where wind > solar.
    # This is EXPECTED for agriculture-dominated parcels because the methods doc
    # assigns Cultivated Crops and Pasture/Hay higher wind (70%) than solar (60%).
    # Documented rationale: wind turbines coexist well with row crops (Diffendorfer
    # et al. 2019; van Haaren & Fthenakis 2011).
    n_wind_gt_solar = int((out["usable_area_nlcd_wind_m2"] > out["usable_area_nlcd_solar_m2"] + 1e-6).sum())
    excess_ac = float((out["usable_area_nlcd_wind_m2"] - out["usable_area_nlcd_solar_m2"]).clip(lower=0).sum()) / M2_PER_ACRE
    log(f"Diagnostic: {n_wind_gt_solar:,} parcels have wind > solar "
        f"(total excess {excess_ac:,.0f} ac). Expected for agriculture-dominated parcels.", lines)

    total_wind_ac = out["usable_area_nlcd_wind_ac"].sum()
    total_solar_ac = out["usable_area_nlcd_solar_ac"].sum()
    log(f"CONUS total: NLCD wind (pct-only) = {total_wind_ac:,.0f} ac  "
        f"(NLCD solar = {total_solar_ac:,.0f} ac; ratio = {total_wind_ac/total_solar_ac:.3f})", lines)

    parcel_csv = OUT_DIR / "nlcd_wind_percentage_only.csv"
    out.to_csv(parcel_csv, index=False)
    log(f"Wrote {parcel_csv}", lines)

    # Size-bin decomposition
    bin_rows = []
    for sb in SIZE_BIN_ORDER:
        sub = out[out["size_bin"] == sb]
        bin_rows.append({
            "size_bin": sb,
            "n_parcels": len(sub),
            "nlcd_wind_ac": round(sub["usable_area_nlcd_wind_ac"].sum(), 0),
            "nlcd_solar_ac": round(sub["usable_area_nlcd_solar_ac"].sum(), 0),
            "wind_solar_ratio": (
                round(sub["usable_area_nlcd_wind_ac"].sum() / sub["usable_area_nlcd_solar_ac"].sum(), 3)
                if sub["usable_area_nlcd_solar_ac"].sum() > 0 else 0.0
            ),
        })
    bin_rows.append({
        "size_bin": "CONUS_total",
        "n_parcels": len(out),
        "nlcd_wind_ac": round(total_wind_ac, 0),
        "nlcd_solar_ac": round(total_solar_ac, 0),
        "wind_solar_ratio": round(total_wind_ac / total_solar_ac, 3) if total_solar_ac > 0 else 0.0,
    })
    summary_csv = OUT_DIR / "nlcd_wind_percentage_only_summary.csv"
    pd.DataFrame(bin_rows).to_csv(summary_csv, index=False)
    log(f"Wrote {summary_csv}", lines)

    (OUT_DIR / "run_log.txt").write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
