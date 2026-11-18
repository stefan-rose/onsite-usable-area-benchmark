#!/usr/bin/env python3
"""
Check a downloaded copy of the Zenodo dataset release against the paper.

Needs only the Zenodo files and this repository (no licensed data). For each
of the 13 national totals in figures/data/fig_headline_totals.csv (the data
behind the paper's headline figure), the total is recomputed from the
released per-parcel file and compared at the figure's 4-decimal precision
(million acres). reV Parcel Joined is released as aggregates only, so its
total is taken from the size-bin summary file.

Run
  pixi run verify-zenodo <folder with the Zenodo files> [--version 1.0]

Exits non-zero if any total differs.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[2]
FIG = REPO / "figures/data/fig_headline_totals.csv"

COLS = {
    ("solar", "reV Open"): "solar_rev_open_ac",
    ("solar", "reV Reference"): "solar_rev_reference_ac",
    ("solar", "reV Limited"): "solar_rev_limited_ac",
    ("solar", "NLCD"): "solar_nlcd_ac",
    ("solar", "reV Parcel Joined"): "solar_rev_parcel_joined_ac",
    ("wind", "NLCD pct-only"): "wind_nlcd_pct_only_ac",
    ("wind", "NLCD 5-layer"): "wind_nlcd_5layer_ac",
    ("wind", "NLCD 7-layer (diagnostic)"): "wind_nlcd_7layer_ac",
    ("wind", "reV Open"): "wind_rev_open_ac",
    ("wind", "reV Reference (80/77)"): "wind_rev_reference_hh80_rd77_ac",
    ("wind", "reV Reference (115/170)"): "wind_rev_reference_hh115_rd170_ac",
    ("wind", "reV Limited (80/77)"): "wind_rev_limited_hh80_rd77_ac",
    ("wind", "reV Limited (115/170)"): "wind_rev_limited_hh115_rd170_ac",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("release_dir", type=Path)
    ap.add_argument("--version", default="1.0")
    a = ap.parse_args()
    v = a.version
    p = pd.read_csv(a.release_dir / f"onsite_usable_area_parcels_v{v}.csv", dtype={"county_fips": str})
    s = pd.read_csv(a.release_dir / f"summary_by_size_bin_v{v}.csv")
    bad = 0
    for _, r in pd.read_csv(FIG).iterrows():
        c = COLS[(r.technology, r.scenario)]
        tot = p[c].sum() if c in p.columns else s.loc[s.column == c, "usable_ac"].sum()
        ok = abs(tot / 1e6 - r.usable_Mac) <= 5e-4
        bad += not ok
        print(f"{'OK ' if ok else 'BAD'} {r.technology:5s} {r.scenario:26s} "
              f"{tot / 1e6:.4f} vs paper {r.usable_Mac:.4f} M ac")
    print(f"parcels {len(p):,}; mismatches {bad}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
