# Parcel-level usable area for on-site solar and wind at U.S. manufacturing parcels: NLCD and reV benchmark

Version 1.0 · License CC BY 4.0

Stefan Rose (Pacific Northwest National Laboratory) and Dakota Ramos (National Laboratory of the Rockies)

This dataset accompanies the paper *Sizing up on-site industrial energy potential: a parcel-level comparison of usable-area methods* (Rose and Ramos, *Applied Energy*, under review). <!-- TODO: add the paper DOI after publication. -->

## What it contains

The dataset estimates usable land area for ground-mount solar PV and land-based wind at each of 305,123 manufacturing parcels in the contiguous United States. These parcels host 338,904 facilities in M-FIND v1.1. Two estimators are compared:

- **NLCD land-cover-proportion method.** NLCD 2021 class areas in each parcel are weighted by class-specific availability percentages. Wind is given three ways: percentages only, with a 5-layer binary parcel screen, and with a 7-layer binary parcel screen.
- **reV composite exclusion method.** Parcel area is multiplied by the mean inclusion fraction of the NLR reV 2024 composite exclusion raster. Results are given for the Open, Reference and Limited siting scenarios. Wind is given for five turbine configurations (hub height / rotor diameter, m: 115/170, 80/77, 60/47, 37/20.7, 24/9.6).

The per-parcel file also includes:

- the 16 NLCD class areas, so users can apply their own availability percentages;
- the binary exclusion flags;
- a forest-availability sensitivity for NLCD solar;
- reV quality-assurance flags.

| File | Content |
|---|---|
| `onsite_usable_area_parcels_v1.0.csv` | One row per parcel: 56 columns, 305,123 rows (~92 MB) |
| `summary_by_size_bin_v1.0.csv` | Usable acres by method and parcel-size bin, including reV Parcel Joined |
| `summary_by_state_v1.0.csv` | Usable acres by method and state, including reV Parcel Joined |
| `CODEBOOK.txt` | Variable definitions, units, provenance, handling notes |
| `MD5SUMS.txt` | Checksums |

## Identifiers and licensed data

Parcel polygons come from LightBox SmartParcels under license and are **not** redistributed. The file includes no LightBox parcel identifier and no coordinates.

Each row is keyed to public M-FIND v1.1 facility identifiers instead:

- `primary_obs_id` is the key;
- `mfind_obs_ids` lists every facility on the parcel;
- `mfind_colocation_group_id` gives the M-FIND colocation group.

Join to [M-FIND v1.1](https://doi.org/10.5281/zenodo.21827821) on `obs_id` for facility location and NAICS codes. Usable area is a parcel quantity. Do not sum it across co-located facilities.

The reV Parcel Joined layer is built on the LightBox parcel fabric. Its results are therefore given as size-bin and state aggregates only.

## Inputs

- NLCD 2021 Land Cover, doi:10.5066/P9JZ7AO3.
- NLR reV 2024 supply-curve composite exclusions (Lopez et al. 2025, doi:10.2172/2500362):
  - solar: [OEDI submission 8319](https://data.openei.org/submissions/8319);
  - wind: OEDI submission, URL to be added. <!-- TODO: add the OEDI wind URL/DOI once NLR publishes it; update the 8319 file names once the 90 m composites are posted. -->
- TIGER/Line 2023 Urban Areas, FAA Special Use Airspace, FAA airport facilities, USFWS Critical Habitat, USFWS National Wetlands Inventory, USGS 3DEP.

## Reproducibility

The analysis code is at <https://github.com/stefan-rose/onsite-usable-area-benchmark>, release v1.0.0. <!-- TODO: confirm the tag name and add its commit hash once the tag is created. -->

`scripts/14_build_zenodo_release.py` builds these files from the pipeline outputs and runs a set of checks:

- identifier coverage against M-FIND v1.1;
- parcel area against M-FIND;
- national and size-bin totals against the paper's figure data;
- internal consistency of the NLCD variants.

The pipeline itself needs the licensed parcel polygons, so it cannot be re-run without them.

## Citation

Please cite both the paper and this dataset, and M-FIND for the facility inventory:

- Rose, S., Ramos, D. (2026). Parcel-level usable area for on-site solar and wind at U.S. manufacturing parcels: NLCD and reV benchmark (v1.0) [Data set]. Zenodo. doi:TODO
- Billings, B., Rose, S., et al. (2026). M-FIND: The Manufacturing Facility Inventory National Dataset (v1.1) [Data set]. Zenodo. doi:10.5281/zenodo.21827821

## Funding

This work was authored in part by the National Laboratory of the Rockies for the U.S. Department of Energy (DOE) under Contract No. DE-AC36-08GO28308, and in part by Pacific Northwest National Laboratory, operated by Battelle Memorial Institute for the DOE under Contract No. DE-AC05-76RL01830. Funding was provided by the DOE Office of Critical Minerals and Energy Innovation, Industrial Technologies Office. The views expressed do not necessarily represent the views of the DOE or the U.S. Government.
