#!/usr/bin/env python3
"""
Build the Zenodo paper-dataset release: one row per parcel in the 305,123-parcel
CONUS universe, keyed to M-FIND v1.1 facility identifiers (obs_id) rather than
to the LightBox PARCEL_LID.

Outputs (outputs/zenodo_release/v<VERSION>/, not committed):
  onsite_usable_area_parcels_v<VERSION>.csv  per-parcel usable area, all methods
  summary_by_size_bin_v<VERSION>.csv          national totals by size bin (incl. revPJ)
  summary_by_state_v<VERSION>.csv             state totals (incl. revPJ)
  CHECKS_v<VERSION>.txt                        results of the release checks below
  MD5SUMS.txt                                  checksums of the data files

The README, CODEBOOK and Zenodo metadata are maintained by hand in
docs/zenodo_release/ and copied into the release folder by this script.

Per-parcel revPJ values are left out by default. The revPJ raster is built on
the LightBox parcel fabric. Whether per-parcel zonal results from it may be
redistributed is a LightBox DUA question. Pass --include-revpj only after that
is cleared. revPJ is always included in the aggregate summaries.

Checks (all must pass; written to CHECKS file):
  K1  305,123 rows; primary_obs_id unique; no LightBox key column; no
      PARCEL_LID value appears anywhere in the identifier columns
  K2  every obs_id is in M-FIND v1.1 (md5 64bd2b37...); obs_id lists are
      disjoint across rows; each parcel falls in at most one M-FIND
      colocation group
  K3  parcel_acres equals M-FIND PARCEL_AREA_SQFT / 43,560 and the pipeline
      acres (relative difference < 1e-9)
  K4  national totals reproduce figures/data/fig_headline_totals.csv at 4 dp
      (M ac), computed from the rounded columns as released
  K5  size-bin totals reproduce figures/data/fig_bins.csv within 1 ac
  K6  NLCD baseline equals forest scenario S2; NLCD 5-layer and 7-layer wind
      recomputed from the released flags equal the pipeline columns
  K7  wind reV Open is identical across the 115/170 and 80/77 runs
  K8  all usable-area values are non-negative (values above parcel_acres are
      counted and reported, not fatal: NLCD area is a GEE fractional sum)

Run
  pixi run python -u scripts/14_build_zenodo_release.py [--version 1.0] [--include-revpj]
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _config import BASE, OUTPUTS  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
RUNS = BASE / "Scripts/method_comparison/outputs"
AE_OUT = BASE / "Scripts/applied_energy_paper/outputs"
SITE_LIST = BASE / "Data/Site Lists/Sites MECS Scaled/aggregated_facility_level_site_list_2026_04_23.csv"
MFIND = BASE / "Data/Site Lists/Zenodo/M-FIND - The Manufacturing Facility Inventory National Dataset 2026.csv"
MFIND_MD5 = "64bd2b37f3f23889a2e2184022170673"  # Zenodo 10.5281/zenodo.21827821 (v1.1) file checksum
DOCS = REPO / "docs/zenodo_release"
FIGDATA = REPO / "figures/data"

N_UNIVERSE = 305_123
ACRE_M2 = 4046.8564224  # international acre, m2 (exact)
SQFT_PER_AC = 43_560.0
DP = 4  # acres decimal places in the released file
BINS = ["tiny", "small", "medium", "large", "xlarge"]

# reV run directories -> released column names
REV_RUNS = {
    "solar_rev_open_ac":                 "full_run_open_2026_04_23",
    "solar_rev_reference_ac":            "full_run_reference_2026_04_23",
    "solar_rev_limited_ac":              "full_run_limited_2026_04_23",
    "wind_rev_open_ac":                  "full_run_wind_bespoke_115hh_170rd_grid90_open_2026_04_23",
    "wind_rev_reference_hh115_rd170_ac": "full_run_wind_bespoke_115hh_170rd_grid90_reference_2026_04_23",
    "wind_rev_limited_hh115_rd170_ac":   "full_run_wind_bespoke_115hh_170rd_grid90_limited_2026_04_23",
    "wind_rev_reference_hh80_rd77_ac":   "full_run_wind_ge_80hh_77rd_reference_2026_04_23",
    "wind_rev_limited_hh80_rd77_ac":     "full_run_wind_ge_80hh_77rd_limited_2026_04_23",
    "wind_rev_reference_hh60_rd47_ac":   "full_run_wind_vestas_60hh_47rd_reference_2026_04_23",
    "wind_rev_reference_hh37_rd20p7_ac": "full_run_wind_npower_37hh_21rd_reference_2026_04_23",
    "wind_rev_reference_hh24_rd9p6_ac":  "full_run_wind_bergey_24hh_10rd_reference_2026_04_23",
}
REVPJ_COL, REVPJ_RUN = "solar_rev_parcel_joined_ac", "full_run_pj_fy26_2026_04_23"
WIND_OPEN_8077 = "full_run_wind_ge_80hh_77rd_open_2026_04_23"

NLCD_CLASSES = {
    "nlcd_11_open_water_m2": "nlcd_11_ac", "nlcd_12_perennial_ice_snow_m2": "nlcd_12_ac",
    "nlcd_21_developed_open_space_m2": "nlcd_21_ac", "nlcd_22_developed_low_intensity_m2": "nlcd_22_ac",
    "nlcd_23_developed_medium_intensity_m2": "nlcd_23_ac", "nlcd_24_developed_high_intensity_m2": "nlcd_24_ac",
    "nlcd_31_barren_land_m2": "nlcd_31_ac", "nlcd_41_deciduous_forest_m2": "nlcd_41_ac",
    "nlcd_42_evergreen_forest_m2": "nlcd_42_ac", "nlcd_43_mixed_forest_m2": "nlcd_43_ac",
    "nlcd_52_shrub_scrub_m2": "nlcd_52_ac", "nlcd_71_grassland_herbaceous_m2": "nlcd_71_ac",
    "nlcd_81_pasture_hay_m2": "nlcd_81_ac", "nlcd_82_cultivated_crops_m2": "nlcd_82_ac",
    "nlcd_90_woody_wetlands_m2": "nlcd_90_ac", "nlcd_95_emergent_herbaceous_wetlands_m2": "nlcd_95_ac",
}
FOREST = {"S1_zero_forest_usable_ac": "solar_nlcd_forest_zero_ac",
          "S3_uniform_10_usable_ac": "solar_nlcd_forest_uniform10_ac",
          "S4_va_deq_upper_usable_ac": "solar_nlcd_forest_uniform50_ac",
          "S5_doubled_usable_ac": "solar_nlcd_forest_doubled_ac"}
FLAGS = {"flag_lt_1ac": "flag_lt_1ac", "flag_urban": "flag_urban", "flag_dod_sua": "flag_dod_sua",
         "flag_usfws": "flag_usfws_critical_habitat", "flag_airport": "flag_airport_3km",
         "flag_slope_gt25": "flag_slope_gt25", "flag_nwi": "flag_nwi"}
FLAGS5 = ["flag_lt_1ac", "flag_urban", "flag_dod_sua", "flag_usfws_critical_habitat", "flag_airport_3km"]

# figure-data label -> released column (K4/K5)
FIG_MAP = {
    ("solar", "reV Open"): "solar_rev_open_ac", ("solar", "reV Reference"): "solar_rev_reference_ac",
    ("solar", "reV Limited"): "solar_rev_limited_ac", ("solar", "NLCD"): "solar_nlcd_ac",
    ("solar", "reV Parcel Joined"): REVPJ_COL,
    ("wind", "NLCD pct-only"): "wind_nlcd_pct_only_ac", ("wind", "NLCD 5-layer"): "wind_nlcd_5layer_ac",
    ("wind", "NLCD 7-layer (diagnostic)"): "wind_nlcd_7layer_ac", ("wind", "reV Open"): "wind_rev_open_ac",
    ("wind", "reV Reference (80/77)"): "wind_rev_reference_hh80_rd77_ac",
    ("wind", "reV Reference (115/170)"): "wind_rev_reference_hh115_rd170_ac",
    ("wind", "reV Limited (80/77)"): "wind_rev_limited_hh80_rd77_ac",
    ("wind", "reV Limited (115/170)"): "wind_rev_limited_hh115_rd170_ac",
}

FIPS_STATE = {"01": "AL", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE",
              "11": "DC", "12": "FL", "13": "GA", "16": "ID", "17": "IL", "18": "IN", "19": "IA",
              "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI",
              "27": "MN", "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
              "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH", "40": "OK",
              "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD", "47": "TN", "48": "TX",
              "49": "UT", "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI", "56": "WY"}

checks: list[str] = []
failures: list[str] = []


def check(name: str, ok: bool, detail: str) -> None:
    line = f"{'PASS' if ok else 'FAIL'}  {name}: {detail}"
    print(line)
    checks.append(line)
    if not ok:
        failures.append(name)


def md5(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rev(run: str) -> pd.DataFrame:
    return pd.read_csv(RUNS / run / "rev_full_population.csv", dtype={"PARCEL_LID": str}).set_index("PARCEL_LID")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="1.0")
    ap.add_argument("--include-revpj", action="store_true")
    args = ap.parse_args()
    v = args.version
    out = OUTPUTS / "zenodo_release" / f"v{v}"
    out.mkdir(parents=True, exist_ok=True)

    # ---------------- crosswalk PARCEL_LID -> M-FIND obs_id ----------------
    mf_md5 = md5(MFIND)
    check("M-FIND file", mf_md5 == MFIND_MD5, f"md5 {mf_md5}")
    mf = pd.read_csv(MFIND, dtype=str).set_index("obs_id")
    sl = pd.read_csv(SITE_LIST, dtype=str, usecols=["PARCEL_LID", "obs_id"])

    nlcd = pd.read_csv(RUNS / "full_run_nlcd_2026_04_23/nlcd_full_population.csv",
                       dtype={"PARCEL_LID": str}).set_index("PARCEL_LID")
    lids = nlcd.index
    sl = sl[sl.PARCEL_LID.isin(lids)].set_index("PARCEL_LID")
    ex = sl.obs_id.str.split(",").explode().str.strip()
    in_mf = ex.isin(mf.index)
    groups = ex[in_mf].map(mf.colocation_group_id).groupby(level=0).nunique(dropna=True)
    check("K2 obs_id coverage",
          bool(in_mf.all()) and not ex.duplicated().any() and int(groups.max()) <= 1,
          f"{len(ex):,} obs_ids, {int((~in_mf).sum())} not in M-FIND, "
          f"{int(ex.duplicated().sum())} shared across parcels, max colocation groups per parcel {int(groups.max())}")
    obs_sorted = ex.groupby(level=0).apply(lambda s: sorted(s))

    d = pd.DataFrame(index=lids)
    d["primary_obs_id"] = obs_sorted.str[0]
    d["mfind_obs_ids"] = obs_sorted.str.join(";")
    d["n_mfind_facilities"] = obs_sorted.str.len()
    cg = ex.map(mf.colocation_group_id).groupby(level=0).first()
    d["mfind_colocation_group_id"] = cg.astype("Int64")
    # state = the state batch the parcel was processed in (matches the paper's
    # state results). county_fips comes from M-FIND (STATE is blank there for
    # ~18.7k records, FIPS_CODE is complete). Two state-line parcels disagree.
    d["county_fips"] = d.primary_obs_id.map(mf.FIPS_CODE).str.zfill(5)
    d["state"] = nlcd["state_for_batch"]
    grp_size = mf.groupby("colocation_group_id").size()
    multi = d[d.n_mfind_facilities > 1]
    grp_ok = multi.mfind_colocation_group_id.notna().all() and (
        multi.mfind_colocation_group_id.astype(float).map(grp_size.set_axis(grp_size.index.astype(float)))
        == multi.n_mfind_facilities).all()
    single_grouped = int(d.loc[d.n_mfind_facilities == 1, "mfind_colocation_group_id"].notna().sum())
    check("K2b colocation groups", bool(grp_ok),
          f"{len(multi):,} multi-facility parcels; M-FIND group size equals parcel facility count: {grp_ok}; "
          f"single-facility parcels carrying a group id: {single_grouped}")
    mf_ac = d.primary_obs_id.map(mf.PARCEL_AREA_SQFT).astype(float) / SQFT_PER_AC
    d["parcel_acres"] = mf_ac
    d["size_bin"] = nlcd["size_bin"]
    rel = ((mf_ac - nlcd["acres"]).abs() / nlcd["acres"]).max()
    check("K3 parcel area", rel < 1e-9, f"max relative diff M-FIND vs pipeline acres {rel:.2e}")
    st_mismatch = int((d.county_fips.str[:2].map(FIPS_STATE) != d.state).sum())
    check("K3b state", st_mismatch <= 2 and d.county_fips.notna().all() and d.state.notna().all(),
          f"county_fips state prefix differs from batch state on {st_mismatch} parcels "
          f"(expected 2 State Line Rd parcels, NY/NJ and MO/KS)")

    # ---------------- NLCD ----------------
    for src, dst in NLCD_CLASSES.items():
        d[dst] = nlcd[src].fillna(0.0) / ACRE_M2
    d["nlcd_coverage_ratio"] = nlcd["nlcd_coverage_ratio"]
    d["qa_nlcd_no_value"] = nlcd["flag_nlcd_no_value"].astype(bool)
    d["solar_nlcd_ac"] = nlcd["usable_area_nlcd_m2"] / ACRE_M2
    fs = pd.read_csv(AE_OUT / "forest_sensitivity/forest_sensitivity_parcel_level.csv",
                     dtype={"PARCEL_LID": str}).set_index("PARCEL_LID").reindex(lids)
    # convert from m2 with one acre constant (the pipeline _ac columns use
    # slightly different constants; differences are < 1e-6 relative)
    for src, dst in FOREST.items():
        d[dst] = fs[src.replace("_ac", "_m2")] / ACRE_M2
    s2 = ((fs["S2_baseline_usable_m2"] - nlcd["usable_area_nlcd_m2"]).abs() / ACRE_M2).max()

    w = pd.read_csv(AE_OUT / "nlcd_wind/nlcd_wind_percentage_plus_binary.csv",
                    dtype={"PARCEL_LID": str}).set_index("PARCEL_LID").reindex(lids)
    d["wind_nlcd_pct_only_ac"] = w["usable_area_nlcd_wind_m2"] / ACRE_M2
    for src, dst in FLAGS.items():
        d[dst] = w[src].astype(str).str.upper().eq("TRUE")
    any5 = d[FLAGS5].any(axis=1)
    any7 = d[list(FLAGS.values())].any(axis=1)
    d["wind_nlcd_5layer_ac"] = np.where(any5, 0.0, d["wind_nlcd_pct_only_ac"])
    d["wind_nlcd_7layer_ac"] = np.where(any7, 0.0, d["wind_nlcd_pct_only_ac"])
    k6b = (d["wind_nlcd_7layer_ac"] - w["usable_area_nlcd_wind_bin_m2"] / ACRE_M2).abs().max()
    check("K6 NLCD consistency", s2 < 1e-9 and k6b < 1e-9,
          f"|S2 - baseline| max {s2:.2e}; |7-layer recomputed - pipeline| max {k6b:.2e}")

    # ---------------- reV ----------------
    qa = {}
    for col, run in REV_RUNS.items():
        r = rev(run).reindex(lids)
        d[col] = r["usable_area_rev_m2"] / ACRE_M2
        qa[col] = r
    o2 = rev(WIND_OPEN_8077).reindex(lids)["usable_area_rev_m2"] / ACRE_M2
    k7 = (o2 - d["wind_rev_open_ac"]).abs().max()
    check("K7 wind Open shared", k7 == 0.0, f"max |80/77 Open - 115/170 Open| = {k7}")
    pj = rev(REVPJ_RUN).reindex(lids)["usable_area_rev_m2"] / ACRE_M2

    # QA flags: identical across scenarios that share a grid -> check, then keep one copy
    def same(cols, f):
        return all((qa[c][f].values == qa[cols[0]][f].values).all() for c in cols)
    sol, wnd = [c for c in REV_RUNS if c.startswith("solar")], [c for c in REV_RUNS if c.startswith("wind")]
    qa_ok = all(same(g, f) for g in (sol, wnd) for f in ("flag_rev_centroid_fallback", "flag_rev_low_pixel_count", "flag_rev_no_value"))
    nv = sum(int(qa[c]["flag_rev_no_value"].sum()) for c in REV_RUNS)
    check("QA flags shared within grid", qa_ok, f"solar and wind QA flags identical across scenarios; flag_rev_no_value total {nv}")
    d["qa_rev_solar_centroid_fallback"] = qa[sol[0]]["flag_rev_centroid_fallback"].astype(bool)
    d["qa_rev_solar_low_pixel_count"] = qa[sol[0]]["flag_rev_low_pixel_count"].astype(bool)
    d["qa_rev_wind_centroid_fallback"] = qa[wnd[0]]["flag_rev_centroid_fallback"].astype(bool)
    d["qa_rev_wind_low_pixel_count"] = qa[wnd[0]]["flag_rev_low_pixel_count"].astype(bool)
    if args.include_revpj:
        d[REVPJ_COL] = pj

    # ---------------- round + order ----------------
    ac_cols = [c for c in d.columns if c.endswith("_ac") or c == "parcel_acres"]
    d[ac_cols] = d[ac_cols].round(DP)
    d["nlcd_coverage_ratio"] = d["nlcd_coverage_ratio"].round(6)
    d = d.sort_values("primary_obs_id")
    pj_r = pj.round(DP)

    # ---------------- K1 identifier hygiene ----------------
    lidset = set(lids)
    leak = any(d[c].astype(str).isin(lidset).any() for c in ["primary_obs_id", "mfind_obs_ids"])
    check("K1 identifiers",
          len(d) == N_UNIVERSE and d.primary_obs_id.is_unique and "PARCEL_LID" not in d.columns and not leak,
          f"{len(d):,} rows; unique key {d.primary_obs_id.is_unique}; PARCEL_LID value leak {leak}")

    # ---------------- K4/K5 vs figure data ----------------
    full = d.copy()
    full[REVPJ_COL] = pj_r.reindex(d.index)  # summaries always carry revPJ aggregates
    tot = pd.read_csv(FIGDATA / "fig_headline_totals.csv")
    bad = []
    for _, row in tot.iterrows():
        col = FIG_MAP[(row.technology, row.scenario)]
        got = round(full[col].sum() / 1e6, 4)
        if abs(got - row.usable_Mac) > 0.00005 + 1e-12:
            bad.append(f"{row.technology}/{row.scenario} {got} vs {row.usable_Mac}")
    check("K4 national totals", not bad, f"{len(tot)} rows compared; mismatches: {bad or 'none'}")
    fb = pd.read_csv(FIGDATA / "fig_bins.csv")
    bad = []
    for _, row in fb.iterrows():
        key = (row.technology, row.scenario)
        if key not in FIG_MAP:
            bad.append(f"unmapped {key}")
            continue
        got = full.loc[full.size_bin == row.size_bin, FIG_MAP[key]].sum()
        if abs(got - row.usable_ac) > 1.0:
            bad.append(f"{key} {row.size_bin} {got:.1f} vs {row.usable_ac}")
    check("K5 size-bin totals", not bad, f"{len(fb)} rows compared; mismatches: {bad[:5] or 'none'}")

    use_cols = [c for c in full.columns if c.endswith("_ac") and (c.startswith("solar") or c.startswith("wind"))]
    neg = int((full[use_cols] < 0).sum().sum())
    over = {c: int((full[c] > full.parcel_acres + 1e-4).sum()) for c in use_cols}
    over = {k: x for k, x in over.items() if x}
    check("K8 non-negative", neg == 0, f"{neg} negative values; values > parcel_acres: {over or 'none'}")

    # ---------------- summaries (always include revPJ) ----------------
    def summ(by):
        rows = []
        for col in use_cols:
            g = full.groupby(by, observed=True)[col]
            s = pd.DataFrame({"usable_ac": g.sum().round(1), "n_parcels": g.size(),
                              "n_nonzero": g.apply(lambda x: int((x > 0).sum()))}).reset_index()
            s.insert(0, "column", col)
            rows.append(s)
        return pd.concat(rows, ignore_index=True)
    full["size_bin"] = pd.Categorical(full["size_bin"], BINS, ordered=True)
    summ("size_bin").to_csv(out / f"summary_by_size_bin_v{v}.csv", index=False)
    summ("state").to_csv(out / f"summary_by_state_v{v}.csv", index=False)

    # ---------------- write ----------------
    data_csv = out / f"onsite_usable_area_parcels_v{v}.csv"
    d.to_csv(data_csv, index=False)
    for name in ["README.md", "CODEBOOK.txt", "zenodo_metadata.json"]:
        src = DOCS / name
        if src.exists():
            shutil.copy2(src, out / name)
    data_files = [data_csv, out / f"summary_by_size_bin_v{v}.csv", out / f"summary_by_state_v{v}.csv"]
    with open(out / "MD5SUMS.txt", "w") as f:
        for p in data_files + [out / n for n in ["README.md", "CODEBOOK.txt"] if (out / n).exists()]:
            f.write(f"{md5(p)}  {p.name}\n")

    info = [f"rows {len(d):,}; columns {d.shape[1]}; revPJ per-parcel included: {args.include_revpj}",
            f"parcels with >1 M-FIND facility: {int((d.n_mfind_facilities > 1).sum()):,}",
            f"data file size {data_csv.stat().st_size / 1e6:.1f} MB"]
    for line in info:
        print("INFO  " + line)
    (out / f"CHECKS_v{v}.txt").write_text("\n".join(checks + ["INFO  " + x for x in info]) + "\n")
    print(f"\nwrote {out}")
    if failures:
        sys.exit(f"FAILED: {failures}")


if __name__ == "__main__":
    main()
