"""Build Fig 1 / Fig 2 source CSVs for the manuscript on the 90 m wind grid.

Inputs
  outputs/wind_turbine_bins.csv     (script 12)  reV wind by turbine/scenario/bin
  outputs/wind_turbine_totals.csv   (script 12)  reV wind national totals
  PUBLISHED_FIG2 (argv[1])          published Fig 2 CSV (2026-07-31); solar and
                                    NLCD rows are carried through unchanged

Outputs
  outputs/fig2_bins_grid90.csv      Fig 2 data: solar + NLCD unchanged; reV wind
                                    replaced by the shared 90 m Open and the
                                    115/170 (90 m grid) and 80/77 Ref/Limited rows
  outputs/fig1_totals_grid90.csv    Fig 1 data (national totals, M ac)
Tracked copies of both figure CSVs: figures/data/fig_bins.csv, figures/data/fig_headline_totals.csv

Checks (exit non-zero on failure)
  F1  solar and NLCD wind rows identical to the published CSV
  F2  115/170 and 80/77 Open bins identical (Open carries no turbine setback)
  F3  per-scenario bin sums equal wind_turbine_totals.csv within 1 ac
  F4  shared Open total = 4.414 M ac; 115/170 Ref 0.794, Lim 0.235;
      80/77 Ref 1.241, Lim 0.435 (Table 3, rounded to 3 dp)

Run
  pixi run python -u scripts/13_build_manuscript_figure_data.py <published_fig2.csv>
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
FIGDATA = ROOT / "figures" / "data"  # tracked; read by the figure specs
BINS = ["tiny", "small", "medium", "large", "xlarge"]
G90 = "bespoke_115hh_170rd_grid90"
GE = "ge_80hh_77rd"


def main() -> None:
    pub = pd.read_csv(sys.argv[1])
    bins = pd.read_csv(OUT / "wind_turbine_bins.csv")
    tot = pd.read_csv(OUT / "wind_turbine_totals.csv")
    fails: list[str] = []

    keep = pub[(pub.technology == "solar") | pub.scenario.str.startswith("NLCD")].copy()

    def rev(turb: str, scen: str, label: str) -> pd.DataFrame:
        d = bins[(bins.turbine == turb) & (bins.scenario == scen)].set_index("size_bin")
        return pd.DataFrame({"technology": "wind", "scenario": label,
                             "size_bin": BINS, "usable_ac": [round(d.usable_ac[b], 1) for b in BINS]})

    # F2
    o1 = bins[(bins.turbine == G90) & (bins.scenario == "open")].usable_ac.values
    o2 = bins[(bins.turbine == GE) & (bins.scenario == "open")].usable_ac.values
    if not (len(o1) == 5 and (abs(o1 - o2) < 1e-6).all()):
        fails.append("F2 Open bins differ between 115/170 grid90 and 80/77")

    wind = pd.concat([
        rev(G90, "open", "reV Open"),
        rev(GE, "reference", "reV Reference (80/77)"),
        rev(G90, "reference", "reV Reference (115/170)"),
        rev(GE, "limited", "reV Limited (80/77)"),
        rev(G90, "limited", "reV Limited (115/170)"),
    ])
    fig2 = pd.concat([keep, wind], ignore_index=True)
    fig2["bin_order"] = fig2.size_bin.map({b: i for i, b in enumerate(BINS)})

    # F1
    chk = fig2.merge(pub, on=["technology", "scenario", "size_bin"], suffixes=("", "_pub"))
    chk = chk[(chk.technology == "solar") | chk.scenario.str.startswith("NLCD")]
    if len(chk) != len(keep) or (chk.usable_ac - chk.usable_ac_pub).abs().max() > 0:
        fails.append("F1 solar/NLCD rows changed")

    # F3 / F4
    expect = {("reV Open", G90, "open"): 4.414,
              ("reV Reference (115/170)", G90, "reference"): 0.794,
              ("reV Limited (115/170)", G90, "limited"): 0.235,
              ("reV Reference (80/77)", GE, "reference"): 1.241,
              ("reV Limited (80/77)", GE, "limited"): 0.435}
    rows = []
    for (label, turb, scen), e in expect.items():
        s = fig2[(fig2.technology == "wind") & (fig2.scenario == label)].usable_ac.sum()
        t = tot[(tot.turbine == turb) & (tot.scenario == scen)].total_Mac.iloc[0] * 1e6
        if abs(s - t) > 1.0:
            fails.append(f"F3 {label}: bins {s:.1f} vs totals {t:.1f}")
        if round(t / 1e6, 3) != e:
            fails.append(f"F4 {label}: {t/1e6:.4f} != {e}")
        print(f"  {label:26s} bins={s/1e6:.4f}  totals={t/1e6:.4f}  table={e}")
        rows.append((label, t / 1e6))

    fig2.to_csv(OUT / "fig2_bins_grid90.csv", index=False)
    FIGDATA.mkdir(parents=True, exist_ok=True)
    fig2.to_csv(FIGDATA / "fig_bins.csv", index=False)  # tracked copy
    f1 = (fig2.groupby(["technology", "scenario"], sort=False).usable_ac.sum() / 1e6).round(4).reset_index()
    f1.columns = ["technology", "scenario", "usable_Mac"]
    f1.to_csv(OUT / "fig1_totals_grid90.csv", index=False)
    f1.to_csv(FIGDATA / "fig_headline_totals.csv", index=False)  # tracked copy
    print(f1.to_string(index=False))

    print("\nChecks:", "ALL PASS" if not fails else "FAILURES")
    for f in fails:
        print("  FAIL", f)
    if fails:
        sys.exit(1)


if __name__ == "__main__":
    main()
