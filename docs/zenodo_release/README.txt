README: Parcel-level usable area for on-site solar and wind at U.S.
manufacturing parcels: NLCD and reV benchmark (version 1.0)
==========================================================================

License: CC BY 4.0
Authors: Stefan Rose (Pacific Northwest National Laboratory)
         Dakota Ramos (National Laboratory of the Rockies)
Paper:   This dataset accompanies Rose, S., Ramos, D. Sizing up on-site
         industrial energy potential: a parcel-level comparison of
         usable-area methods. Applied Energy (under review).


WHAT IT CONTAINS
----------------
The dataset estimates usable land area for ground-mount solar PV and
land-based wind at each of 305,123 manufacturing parcels in the
contiguous United States. These parcels host 338,904 facilities in
M-FIND v1.1. Two estimators are compared:

  1. NLCD land-cover-proportion method. NLCD 2021 class areas in each
     parcel are weighted by class-specific availability percentages.
     Wind is given three ways: percentages only, with a 5-layer binary
     parcel screen, and with a 7-layer binary parcel screen.
  2. reV composite exclusion method. Parcel area is multiplied by the
     mean inclusion fraction of the NLR reV 2024 composite exclusion
     raster. Results are given for the Open, Reference and Limited
     siting scenarios. Wind is given for up to five turbine
     configurations (hub height / rotor diameter, m: 115/170, 80/77,
     60/47, 37/20.7, 24/9.6).

The per-parcel file also includes:
  - the 16 NLCD class areas, so users can apply their own availability
    percentages;
  - the binary exclusion flags;
  - a forest-availability sensitivity for NLCD solar;
  - reV quality-assurance flags.


FILES
-----
  onsite_usable_area_parcels_v1.0.csv  One row per parcel: 56 columns,
                                       305,123 rows (~92 MB)
  summary_by_size_bin_v1.0.csv         Usable acres by method and
                                       parcel-size bin, including reV
                                       Parcel Joined
  summary_by_state_v1.0.csv            Usable acres by method and state,
                                       including reV Parcel Joined
  CODEBOOK.txt                         Variable definitions, units,
                                       provenance, handling notes
  MD5SUMS.txt                          Checksums


IDENTIFIERS AND LICENSED DATA
-----------------------------
Parcel polygons come from LightBox SmartParcels under license and are
NOT redistributed. The file includes no LightBox parcel identifier and no
coordinates.

Each row is keyed to public M-FIND v1.1 facility identifiers instead:
  - primary_obs_id is the key;
  - mfind_obs_ids lists every facility on the parcel;
  - mfind_colocation_group_id gives the M-FIND colocation group.

Join to M-FIND v1.1 (https://doi.org/10.5281/zenodo.21827821) on obs_id
for facility location and NAICS codes. Usable area is a parcel quantity.
Do not sum it across co-located facilities.

The reV Parcel Joined layer is built on the LightBox parcel fabric. Its
results are therefore given as size-bin and state aggregates only.


INPUTS
------
  - NLCD 2021 Land Cover, doi:10.5066/P9JZ7AO3.
  - NLR reV 2024 supply-curve composite exclusions (Lopez et al. 2025,
    doi:10.2172/2500362):
      solar: OEDI submission 8319,
             https://data.openei.org/submissions/8319;
      wind:  wind composite exclusions provided by NLR; public release
             on OEDI pending.
  - TIGER/Line 2023 Urban Areas, FAA Special Use Airspace, FAA airport
    facilities, USFWS Critical Habitat, USFWS National Wetlands
    Inventory, USGS 3DEP.


REPRODUCIBILITY
---------------
The analysis code is at
https://github.com/stefan-rose/onsite-usable-area-benchmark. The file
docs/ZENODO_RELEASE.md in that repository gives step-by-step instructions
to check these files and to rebuild them.

Checking needs only these files and the repository:
scripts/validation/verify_zenodo_release.py recomputes the paper's
national totals from the per-parcel file.

scripts/14_build_zenodo_release.py builds these files from the pipeline
outputs and runs a set of checks:
  - identifier coverage against M-FIND v1.1;
  - parcel area against M-FIND;
  - national and size-bin totals against the paper's figure data;
  - internal consistency of the NLCD variants.

The pipeline itself needs the licensed parcel polygons, so a full
rebuild is not possible without them.


CITATION
--------
Please cite both the paper and this dataset, and M-FIND for the facility
inventory:

  Rose, S., Ramos, D. (2026). Parcel-level usable area for on-site solar
  and wind at U.S. manufacturing parcels: NLCD and reV benchmark (v1.0)
  [Data set]. Zenodo. doi:10.5281/zenodo.24354306

  Billings, B., Rose, S., et al. (2026). M-FIND: The Manufacturing
  Facility Inventory National Dataset (v1.1) [Data set]. Zenodo.
  doi:10.5281/zenodo.21827821


FUNDING
-------
This work was authored in part by the National Laboratory of the Rockies
for the U.S. Department of Energy (DOE) under Contract No.
DE-AC36-08GO28308, and in part by Pacific Northwest National Laboratory,
operated by Battelle Memorial Institute for the DOE under Contract No.
DE-AC05-76RL01830. Funding was provided by the DOE Office of Critical
Minerals and Energy Innovation, Industrial Technologies Office. The views
expressed do not necessarily represent the views of the DOE or the U.S.
Government.
