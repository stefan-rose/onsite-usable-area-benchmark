"""
Wind turbine-configuration summaries for the Applied Energy manuscript.

Reads the per-parcel outputs written by 05_rev_wind_composite_scenarios.py
for every turbine configuration and scenario present on disk, and writes:

  OUTPUTS/wind_turbine_totals.csv        national totals, nonzero parcels,
                                          retained share, NLCD/reV ratios
  OUTPUTS/wind_turbine_bins.csv          size-bin totals (Table bins / Fig 2)
  OUTPUTS/wind_turbine_intensity.csv     per-bin mean inclusion and zero share
  OUTPUTS/wind_turbine_xlarge_share.csv  xlarge share of each total
  OUTPUTS/wind_turbine_area_floor.csv    parcel-area-floor sensitivity of
                                          NLCD 5-layer vs each reV Reference
  OUTPUTS/fig_bin_distribution_with_turbines.csv
                                          Fig 2 source CSV with turbine rows
                                          appended (published rows unchanged)

Conventions match the headline run exactly: no parcel-area floor, no cap,
one row per PARCEL_LID (asserted). Missing scenarios are reported and skipped,
so the script can run before the NLR Open/Limited layers arrive.

Checks (printed, and the script exits non-zero if any fails):
  C1  headline 115/170 totals reproduce Table 3 (4.417 / 0.794 / 0.235 M ac;
      80,850 / 6,255 / 1,176 nonzero parcels)
  C2  headline bin totals reproduce the published Fig 2 CSV within 0.1 ac
  C3  every per-parcel file has 305,123 unique PARCEL_LIDs
  C4  per-parcel monotonicity Open >= Reference >= Limited within each turbine
      (where scenarios exist); violations are counted, not fatal
  C5  per-parcel ordering across turbines within a scenario on the same
      90 m grid (smaller rotor >= larger); violations counted, not fatal

Run
  pixi run python -u scripts/12_wind_turbine_config_summaries.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _config import BASE, OUTPUTS, REV_WIND_TURBINES  # noqa: E402

OUT_BASE = BASE / "Scripts/method_comparison/outputs"
DATASET_TAG = "2026_04_23"
DEFAULT_TURBINE = "bespoke_115hh_170rd"
SCENARIOS = ["open", "reference", "limited"]
BINS = ["tiny", "small", "medium", "large", "xlarge"]
N_UNIVERSE = 305_123
ACRE_M2 = 4046.856

# Published Fig 2 source (rows for NLCD and solar are carried through unchanged).
FIG2_CSV = BASE / "Communications/Paper/Applied Energy/notes/fig_bin_distribution.csv"
# NLCD 5-layer wind national total (Table 3). Turbine-agnostic; used only
# for the NLCD / reV ratio column. Floor sensitivity of NLCD itself is
# script 11 (R).
NLCD5_TOTAL_MAC = 1.309348  # unrounded 1,309,348 ac (Table 3 prints 1.309); rounded value gives 1.0548 vs 1.0551 for GE

# Turbine order: smallest to largest rotor (used for C5).
ORDER = sorted(REV_WIND_TURBINES, key=lambda t: REV_WIND_TURBINES[t]["rotor_diameter_m"])

failures: list[str] = []


def out_dir(turbine: str, scenario: str) -> Path:
    ttag = "" if turbine == DEFAULT_TURBINE else f"{turbine}_"
    return OUT_BASE / f"full_run_wind_{ttag}{scenario}_{DATASET_TAG}" / "rev_full_population.csv"


def load(turbine: str, scenario: str) -> pd.DataFrame | None:
    p = out_dir(turbine, scenario)
    if not p.exists():
        print(f"  [skip] {turbine} {scenario}: {p.parent.name} not found")
        return None
    d = pd.read_csv(p, dtype={"PARCEL_LID": str},
                    usecols=["PARCEL_LID", "acres", "parcel_area_m2", "size_bin",
                             "rev_mean_pct_inclusion", "usable_area_rev_ac",
                             "flag_rev_no_value"])
    n_unique = d["PARCEL_LID"].nunique()
    if len(d) != N_UNIVERSE or n_unique != N_UNIVERSE:
        failures.append(f"C3 {turbine} {scenario}: rows {len(d)}, unique {n_unique}")
    return d.set_index("PARCEL_LID")


def label(turbine: str) -> str:
    t = REV_WIND_TURBINES[turbine]
    rd = t["rotor_diameter_m"]
    rd = int(rd) if float(rd).is_integer() else rd
    grid = ", 90 m grid" if turbine.endswith("_grid90") else ""
    return f"{t['hub_height_m']}/{rd}{grid}"


def main() -> None:
    print("Loading per-parcel outputs")
    data: dict[tuple[str, str], pd.DataFrame] = {}
    for t in ORDER:
        for s in SCENARIOS:
            d = load(t, s)
            if d is not None:
                data[(t, s)] = d

    # ── totals ──────────────────────────────────────────────────────────
    rows = []
    for (t, s), d in data.items():
        tot = d["usable_area_rev_ac"].sum()
        nz = int((d["usable_area_rev_ac"] > 0).sum())
        rows.append(dict(
            turbine=t, config=label(t), scenario=s,
            hub_height_m=REV_WIND_TURBINES[t]["hub_height_m"],
            rotor_diameter_m=REV_WIND_TURBINES[t]["rotor_diameter_m"],
            total_Mac=tot / 1e6, nonzero_parcels=nz,
            retained_pct=100 * nz / N_UNIVERSE,
            outside_extent=int(d["flag_rev_no_value"].sum()),
            nlcd5_over_rev=NLCD5_TOTAL_MAC / (tot / 1e6) if tot > 0 else np.nan,
        ))
    totals = pd.DataFrame(rows)
    # Within-turbine Open/Limited span, where both exist.
    span = {}
    for t in ORDER:
        if (t, "open") in data and (t, "limited") in data:
            span[t] = (data[(t, "open")]["usable_area_rev_ac"].sum()
                       / data[(t, "limited")]["usable_area_rev_ac"].sum())
    totals["open_over_limited"] = totals["turbine"].map(span)
    totals.to_csv(OUTPUTS / "wind_turbine_totals.csv", index=False)
    print("\nTotals")
    print(totals.to_string(index=False, float_format=lambda x: f"{x:,.4f}"))

    # C1: headline reproduces Table 3
    expect = {"open": (4.417, 80_850), "reference": (0.794, 6_255), "limited": (0.235, 1_176)}
    for s, (mac, nz) in expect.items():
        r = totals[(totals.turbine == DEFAULT_TURBINE) & (totals.scenario == s)]
        if r.empty:
            failures.append(f"C1 headline {s} missing")
            continue
        if round(r.total_Mac.iloc[0], 3) != mac or r.nonzero_parcels.iloc[0] != nz:
            failures.append(f"C1 headline {s}: {r.total_Mac.iloc[0]:.4f} M ac, "
                            f"{r.nonzero_parcels.iloc[0]} nonzero (expected {mac}, {nz})")

    # ── bins ────────────────────────────────────────────────────────────
    brows = []
    for (t, s), d in data.items():
        g = d.groupby("size_bin")["usable_area_rev_ac"].sum().reindex(BINS, fill_value=0)
        for b, v in g.items():
            brows.append(dict(turbine=t, config=label(t), scenario=s, size_bin=b, usable_ac=v))
    bins = pd.DataFrame(brows)
    bins.to_csv(OUTPUTS / "wind_turbine_bins.csv", index=False)

    # xlarge share
    xs = (bins.pivot_table(index=["turbine", "config", "scenario"], columns="size_bin",
                           values="usable_ac", aggfunc="sum")
          .reindex(columns=BINS))
    xs["xlarge_share_pct"] = 100 * xs["xlarge"] / xs[BINS].sum(axis=1)
    xs.reset_index().to_csv(OUTPUTS / "wind_turbine_xlarge_share.csv", index=False)

    # C2: headline bins reproduce published Fig 2 CSV
    pub = pd.read_csv(FIG2_CSV)
    name = {"open": "reV Open", "reference": "reV Reference", "limited": "reV Limited"}
    for s in SCENARIOS:
        if (DEFAULT_TURBINE, s) not in data:
            continue
        mine = bins[(bins.turbine == DEFAULT_TURBINE) & (bins.scenario == s)].set_index("size_bin")["usable_ac"]
        theirs = pub[(pub.technology == "wind") & (pub.scenario == name[s])].set_index("size_bin")["usable_ac"]
        diff = (mine - theirs.reindex(mine.index)).abs().max()
        if not diff <= 0.1:
            failures.append(f"C2 headline {s} bins differ from Fig 2 CSV by {diff:.2f} ac")

    # ── intensity (unweighted mean inclusion and zero share by bin) ─────
    irows = []
    for (t, s), d in data.items():
        frac = d["rev_mean_pct_inclusion"].fillna(0)
        for b in BINS:
            m = d["size_bin"] == b
            irows.append(dict(turbine=t, config=label(t), scenario=s, size_bin=b,
                              n=int(m.sum()),
                              mean_inclusion_pct=100 * frac[m].mean(),
                              area_weighted_inclusion_pct=100 * d.loc[m, "usable_area_rev_ac"].sum()
                              / d.loc[m, "acres"].sum(),
                              zero_share_pct=100 * (d.loc[m, "usable_area_rev_ac"] == 0).mean()))
    pd.DataFrame(irows).to_csv(OUTPUTS / "wind_turbine_intensity.csv", index=False)

    # ── parcel-area floor applied to each reV Reference (diagnostic) ────
    # The manuscript's tbl:area-floor applies floors to NLCD 5-layer; that
    # table is produced by script 11 (R). Here we record the 5D x 3D array
    # envelope per turbine so the GE-matched floor row can be added there.
    env = []
    for t in ORDER:
        rd = REV_WIND_TURBINES[t]["rotor_diameter_m"]
        env.append(dict(turbine=t, config=label(t), rotor_diameter_m=rd,
                        envelope_5Dx3D_ac=(5 * rd) * (3 * rd) / ACRE_M2))
    pd.DataFrame(env).to_csv(OUTPUTS / "wind_turbine_area_floor.csv", index=False)

    # ── C4 monotonicity within turbine ──────────────────────────────────
    print("\nC4 monotonicity (Open >= Ref >= Limited), tolerance 1e-6 ac")
    for t in ORDER:
        for a, b in [("open", "reference"), ("reference", "limited")]:
            if (t, a) in data and (t, b) in data:
                va = data[(t, a)]["usable_area_rev_ac"]
                vb = data[(t, b)]["usable_area_rev_ac"].reindex(va.index)
                bad = vb > va + 1e-6
                n = int(bad.sum())
                print(f"  {t:28s} {a:>9s} >= {b:<9s} violations: {n:,} "
                      f"(excess {(vb - va)[bad].sum():,.0f} ac)")

    # ── C5 ordering across turbines within scenario ─────────────────────
    print("\nC5 cross-turbine ordering (smaller rotor >= larger rotor), tolerance 1e-6 ac")
    # Same-grid comparisons only: the April 115/170 layers are on a ~92.1 m
    # grid, all other configurations on the 10/6 90 m grid, so the 90 m-grid
    # 115/170 layer stands in for the headline here. (Cross-grid comparison
    # GE vs April 115/170 Reference gives 259 parcel violations, 889 ac, all
    # resampling artefacts; same-grid gives 0.)
    main_order = [t for t in ORDER if t != DEFAULT_TURBINE]
    for s in SCENARIOS:
        present = [t for t in main_order if (t, s) in data]
        for small, large in zip(present, present[1:]):
            va = data[(small, s)]["usable_area_rev_ac"]
            vb = data[(large, s)]["usable_area_rev_ac"].reindex(va.index)
            n = int((vb > va + 1e-6).sum())
            print(f"  {s:9s} {small:22s} >= {large:22s} violations: {n:,}")

    # ── grid check: April 115/170 vs 90 m-grid 115/170 ──────────────────
    print("\nGrid check: April lbw (~92.1 m) vs 10/6 (90 m) 115/170")
    for s in SCENARIOS:
        a, b = (DEFAULT_TURBINE, s), ("bespoke_115hh_170rd_grid90", s)
        if a in data and b in data:
            ta, tb = data[a]["usable_area_rev_ac"], data[b]["usable_area_rev_ac"].reindex(data[a].index)
            print(f"  {s:9s} April {ta.sum():,.0f} ac | 90 m {tb.sum():,.0f} ac | ratio {tb.sum()/ta.sum():.4f} | "
                  f"nonzero {int((ta>0).sum()):,} vs {int((tb>0).sum()):,} | "
                  f"per-parcel corr {np.corrcoef(ta, tb)[0,1]:.4f}")

    # ── Fig 2 CSV with turbine rows (published rows unchanged) ──────────
    extra = []
    for (t, s), d in data.items():
        if t == DEFAULT_TURBINE or t.endswith("_grid90") or t not in ("ge_80hh_77rd",):
            continue
        g = bins[(bins.turbine == t) & (bins.scenario == s)]
        for _, r in g.iterrows():
            extra.append(dict(technology="wind", scenario=f"{name[s]} ({label(t)})",
                              size_bin=r.size_bin, usable_ac=round(r.usable_ac, 1)))
    fig2 = pd.concat([pub, pd.DataFrame(extra)], ignore_index=True)
    fig2.to_csv(OUTPUTS / "fig_bin_distribution_with_turbines.csv", index=False)

    print("\nChecks:", "ALL PASS" if not failures else "FAILURES")
    for f in failures:
        print("  FAIL", f)
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
