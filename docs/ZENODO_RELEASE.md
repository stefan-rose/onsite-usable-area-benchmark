# Zenodo dataset release

This page explains how the files in the Zenodo dataset release are produced
from this repository, and how to check them.

The release is *Parcel-level usable area for on-site solar and wind at U.S.
manufacturing parcels: NLCD and reV benchmark* (v1.0),
[doi:10.5281/zenodo.24354306](https://doi.org/10.5281/zenodo.24354306). It contains:

| File | Content |
|---|---|
| `onsite_usable_area_parcels_v1.0.csv` | One row per parcel: 305,123 rows, 56 columns |
| `summary_by_size_bin_v1.0.csv` | Usable acres by method and parcel-size bin, including reV Parcel Joined |
| `summary_by_state_v1.0.csv` | Usable acres by method and state, including reV Parcel Joined |
| `README.txt`, `CODEBOOK.txt` | Description, variable definitions, provenance |
| `MD5SUMS.txt` | Checksums |

There are two levels of reproduction:

- **A. Check the released files.** Needs only the Zenodo files and this repository.
- **B. Rebuild the files from the inputs.** Needs the licensed parcel polygons.

## A. Check the released files (no licensed data needed)

1. Download all files from the Zenodo record into one folder.
2. Check the checksums from inside that folder:

   ```bash
   md5sum -c MD5SUMS.txt            # Linux
   md5 -r * | sort -k2              # macOS: compare with MD5SUMS.txt by eye
   ```

3. Clone this repository, install the environment, and compare the released
   totals with the paper's headline figure data (`figures/data/fig_headline_totals.csv`):

   ```bash
   git clone https://github.com/stefan-rose/onsite-usable-area-benchmark.git
   cd onsite-usable-area-benchmark
   pixi install
   pixi run verify-zenodo /path/to/zenodo/folder
   ```

   The script recomputes all 13 national totals (solar and wind, every method
   and scenario shown in the figure) from the released per-parcel file and
   prints `mismatches 0` when they agree with the paper at 4 decimals
   (million acres). reV Parcel Joined is released as aggregates only, so its
   total comes from the size-bin summary.

Facility attributes (location, NAICS) are not repeated in the release. Join
to [M-FIND v1.1](https://doi.org/10.5281/zenodo.21827821) on `obs_id`; see
`CODEBOOK.txt` for how the identifier columns work.

## B. Rebuild the files from the inputs

A full rebuild needs inputs that cannot be redistributed:

- **LightBox SmartParcels polygons** (licensed). The parcel universe and every
  zonal statistic are computed on these polygons.
- **The parcel-to-facility crosswalk** (`aggregated_facility_level_site_list_2026_04_23.csv`).
  It links LightBox parcel IDs to M-FIND `obs_id` values, so it carries the
  licensed parcel key.

The public inputs are listed in [`DATA_SOURCES.md`](DATA_SOURCES.md): M-FIND
v1.1, NLCD 2021 (extracted with Google Earth Engine), the NLR reV 2024 solar
and wind composite exclusion rasters, and the federal layers used for the
binary wind flags.

With those inputs in place, set up the paths as described in the main
[README](../README.md#path-configuration), then run the scripts below in
order. [`PIPELINE.md`](PIPELINE.md) lists the inputs and outputs of each one.

| Step | Command | Produces (used by script 14) |
|---|---|---|
| Parcel universe | `pixi run build-universe` | 305,123-parcel GeoPackage |
| reV solar | `pixi run rev-solar` | Open, Reference, Limited solar runs |
| reV solar Parcel Joined | `pixi run rev-solar-pj` | revPJ run (FY26 raster) |
| NLCD solar | `pixi run nlcd-solar` | NLCD class areas and solar usable area |
| reV wind, 115/170 | `pixi run python scripts/05_rev_wind_composite_scenarios.py --turbine bespoke_115hh_170rd_grid90` | Open, Reference, Limited |
| reV wind, 80/77 | `pixi run python scripts/05_rev_wind_composite_scenarios.py --turbine ge_80hh_77rd` | Open, Reference, Limited |
| reV wind, smaller turbines | `pixi run python scripts/05_rev_wind_composite_scenarios.py --turbine <id> --scenarios reference` for `vestas_60hh_47rd`, `npower_37hh_21rd`, `bergey_24hh_10rd` | Reference |
| Forest sensitivity | `pixi run forest-sens` | Solar forest-availability scenarios |
| NLCD wind | `pixi run nlcd-wind-pct`, then `pixi run nlcd-wind-5layer`, then `pixi run nlcd-wind-7layer` | Wind usable area and the seven binary flags (the NWI and slope flags need the `scripts/data_download/` helpers first) |
| Build the release | `pixi run python -u scripts/14_build_zenodo_release.py --version 1.0` | The Zenodo files, in `outputs/zenodo_release/v1.0/` |

Script 14 reads the outputs above and keys each parcel to M-FIND v1.1
`obs_id` values. It drops the LightBox parcel ID, and it copies `README.txt`
and `CODEBOOK.txt` from `docs/zenodo_release/`. It then runs the release
checks and writes the results to `CHECKS_v1.0.txt`:

- every `obs_id` is in M-FIND v1.1 (file checksum verified);
- parcel area matches M-FIND;
- national and size-bin totals match `figures/data/`;
- the NLCD variants are internally consistent;
- no licensed parcel ID appears in the output.

The script exits with an error if any check fails. Per-parcel reV Parcel
Joined values are left out because that raster is built on the licensed
parcel fabric. They appear only in the two summary files.

A full rebuild takes several hours; see the wall-clock note in
[`PIPELINE.md`](PIPELINE.md#expected-wall-clock-cost).
