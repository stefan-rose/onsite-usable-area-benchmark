# Data sources

Every input dataset used in the pipeline, with provenance and access instructions. **No input data are redistributed in this repository** — obtain each dataset from the linked source and configure your local paths in `config.toml` (see `config.example.toml`).

All spatial operations occur in EPSG:5070 (NAD83 / CONUS Albers Equal Area). Where a source dataset is delivered in a different CRS, reproject on ingest.

---

## Parcel universe

### M-FIND: Manufacturing Facility Identification Nationwide Dataset

- **Version used:** v1.1
- **DOI:** [10.5281/zenodo.21827821](https://doi.org/10.5281/zenodo.21827821)
- **Description:** 340,229 U.S. manufacturing facility records, matched to proprietary parcel fabrics with NAICS-based sector filtering. The 338,904 CONUS records collapse to the 305,123-parcel universe.
- **CONUS selection:** use the state part of `FIPS_CODE`, zero-padded to five digits (`02` = AK, `15` = HI). Do not use the `STATE` field. In v1.1 it is blank for 87 AK/HI records, and two records in WA and ID are labeled AK. Filtering on `STATE` gives 338,989 facilities and 305,207 parcels instead.
- **License:** See Zenodo record. Downstream redistribution is subject to the upstream terms of the LightBox and Land Records parcel fabrics from which M-FIND is derived.
- **Fields consumed:** `PARCEL_LID`, parcel geometry, `SITE_STATE`, parcel area (m²), acres, size bin.

M-FIND defines the parcel identifiers (`PARCEL_LID`) used throughout this pipeline. The underlying proprietary geometries are not redistributable; users with LightBox/Land Records licenses can regenerate exact per-parcel results, and users without licenses can reproduce aggregate results from the intermediate parquets shipped alongside a future Zenodo archive of this repository.

---

## reV composite exclusion rasters

### NLR reV composite exclusions (solar and wind)

- **Provider:** National Laboratory of the Rockies (NLR).
- **Release:** Distributed alongside the NLR renewable-energy technical-potential supply-curve series. Solar and wind composites for three siting-stringency scenarios (Open, Reference, Limited) plus the parcel-fabric variant (revPJ, solar only).
- **Resolution:** 90 m; percent-inclusion rasters valued in [0, 1] (integer-scaled in some releases).
- **Provenance:** See Lopez et al. 2024 (NREL/TP-91900) for the current parameterization; the exclusion dictionaries accompanying each raster define the layer set and setback distances.

**Filenames referenced by the pipeline (adjust paths in `config.toml`):**

| Scenario | Solar | Wind |
|---|---|---|
| Open | `composite_exclusions_open.tif` | `lbw_open_exclusions.tif` (one layer for all turbines) |
| Reference | `composite_exclusions_reference.tif` | `lbw_reference_exclusions_<hh>hh_<rd>rd.tif` for 115/170, 80/77, 60/47, 37/21, 24/10 |
| Limited | `composite_exclusions_limited.tif` | `lbw_limited_exclusions_<hh>hh_<rd>rd.tif` for 115/170, 80/77 |
| Parcel-fabric (revPJ) | `conus_percent_inclusion_all_parcels_fy26.tif` (FY26 release) | *not produced* |

**Wind public release:** all eight 90 m wind rasters are on OEDI, submission 11697: Ramos, D., and NLR Geospatial Data Science (2026), *CONUS Land-based Wind Composite Siting Exclusion TIFFs 2024: reV Open, Reference, and Limited Siting Scenarios*, <https://data.openei.org/submissions/11697>. Single-band float32, 90 m, ESRI:102008, nodata 255. The OEDI files have the same pixels, grid and nodata as the files named in `config.example.toml` (all eight compared on 2026-11-18); only the descriptive metadata tags differ. Download them and point the `[inputs.rev_wind*]` paths in `config.toml` at them.

---

## NLCD 2021

### National Land Cover Database 2021

- **Provider:** U.S. Geological Survey / Multi-Resolution Land Characteristics (MRLC) Consortium.
- **URL:** <https://www.mrlc.gov/data/nlcd-2021-land-cover-conus>
- **Resolution:** 30 m.
- **License:** Public domain (U.S. federal data).

The pipeline consumes per-parcel per-class NLCD area extractions performed in Google Earth Engine. The GEE `reduceRegions` call partitions cells by fractional coverage against the parcel polygon boundary. Extraction is external to this repository; see the header of `scripts/04_nlcd_full_population_solar.py` for the expected input schema (17 state-batch CSVs with one row per parcel and one column per NLCD class code).

---

## NWI wetlands

### National Wetlands Inventory

- **Provider:** U.S. Fish and Wildlife Service.
- **URL:** <https://www.fws.gov/program/national-wetlands-inventory>
- **Format used:** State geopackages from <https://documentst.ecosphere.fws.gov/wetlands/data/State-Downloads/>.
- **Accessed:** 2026-04-29/30.
- **Pipeline usage:** Consumed by `scripts/data_download/flag_parcels_one_state_nwi*.R` to produce per-parcel NWI flags (any-intersection and coverage-fraction variants). Merged CONUS flag file: `intermediate/wind_flags/flag_nwi.csv`.

---

## Slope

### USGS 3DEP 1 arc-second DEM

- **Source:** USGS 3D Elevation Program, 1 arc-second tiles, `current` release, streamed from `s3://prd-tnm/StagedProducts/Elevation/1/TIFF/current/` (see `scripts/data_download/download_and_flag_slope.sh`).
- **Accessed:** 2026-04-29 (871 tiles).
- **Threshold used:** slope > 25% (14° or steeper) flags a parcel for wind exclusion.
- **Pipeline usage:** Downloaded and flagged per-tile via `scripts/data_download/flag_parcels_one_tile_slope.R`; merged into `intermediate/wind_flags/flag_slope_gt25.csv`.

---

## Airport locations

### FAA Airports

- **Provider:** FAA Aeronautical Information Services (AIS), `Airports` layer (published every 56 days).
- **Release used:** cycle effective 2024-09-05 to 2024-10-31 (accessed 2024-09-05). 20,230 points.
- **Contents:** all landing-facility types are used: 13,300 aerodromes, 6,223 heliports, 545 seaplane bases and 162 others. 14,919 are private use. No type filter is applied.
- **Pipeline usage:** Buffered to 3 km (canonical) around each airport point; parcels overlapping the buffer are flagged for wind exclusion. Sensitivity radii (1, 3, 5, 8, 10 km) are used in `scripts/09_airport_buffer_sensitivity.R`.

---

## Special Use Airspace

### FAA Special Use Airspace (all types)

- **Provider:** FAA Aeronautical Information Services (AIS), `Special Use Airspace` layer (published every 56 days).
- **Release used:** cycle effective 2026-03-19 to 2026-05-14 (accessed 2026-03-19). 1,539 polygons.
- **Pipeline usage:** All SUA polygons are used, with no type filter: MOA 722, restricted (R) 547, warning (W) 212, alert (A) 40, prohibited (P) 13, danger (D) 5. Parcels intersecting any of them are flagged for wind exclusion.

---

## USFWS Critical Habitat

- **Provider:** U.S. Fish and Wildlife Service.
- **URL:** <https://ecos.fws.gov/ecp/report/table/critical-habitat.html> (national download `crithab_all_layers.zip`; polygon layer only).
- **Accessed:** 2024-09-17.
- **Pipeline usage:** Any-intersection flag; parcels overlapping designated critical habitat are excluded from the NLCD wind binary result.

---

## Urban areas

### U.S. Census Bureau Urban Areas

- **Provider:** U.S. Census Bureau (TIGER/Line).
- **URL:** <https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html> (Urban Areas layer).
- **Copy used:** BTS National Transportation Atlas Database `Urban Areas` (2020 Census urban areas, `UACE20`; February 2024 edition, doi:10.21949/1522282), accessed 2024-08-13. 2,645 polygons.
- **Pipeline usage:** Any-intersection flag for wind (urban overlap excludes the parcel from the NLCD wind binary result).

---

## Land use / assessor use-type

The M-FIND parcel-fabric release carries a standardized use-type column derived from the upstream LightBox/Land Records classification. `PARCEL_LID`-keyed use-type joins are performed inside script 03 (revPJ), which is the only pipeline step that consumes use-type. Downstream headline scripts use only the geometry and area from the parcel universe.

---

## Full input inventory (quick reference)

| Dataset | Consumed by | Public? |
|---|---|---|
| M-FIND parcels v1.1 | `01_build_parcel_universe.py` | Yes (Zenodo) |
| reV solar composites (Open/Ref/Lim) | `02_rev_solar_composite_scenarios.py` | Yes (NLR) |
| reV solar revPJ | `03_rev_solar_parcel_joined.py` | Yes (NLR) |
| NLCD 2021 class-area CSVs (GEE-extracted) | `04, 06, 07` | Yes (public inputs; GEE extraction external) |
| reV wind composites (Open/Ref/Lim) | `05_rev_wind_composite_scenarios.py` | Yes (NLR) |
| NWI wetlands | `data_download/` → script 10 | Yes (USFWS) |
| 3DEP slope | `data_download/` → script 10 | Yes (USGS) |
| FAA AIS Airports | scripts 08, 09 | Yes (FAA) |
| FAA AIS Special Use Airspace | script 08 | Yes (FAA) |
| USFWS Critical Habitat | script 08 | Yes (USFWS) |
| Census Urban Areas | script 08 | Yes (Census) |

All ancillary datasets are public; the parcel geometries are the only proprietary input, and access is governed by the M-FIND terms on Zenodo.
