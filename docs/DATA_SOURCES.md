# Data sources

Every input dataset used in the pipeline, with provenance and access instructions. **No input data are redistributed in this repository** — obtain each dataset from the linked source and configure your local paths in `config.toml` (see `config.example.toml`).

All spatial operations occur in EPSG:5070 (NAD83 / CONUS Albers Equal Area). Where a source dataset is delivered in a different CRS, reproject on ingest.

---

## Parcel universe

### M-FIND: Manufacturing Facility Identification Nationwide Dataset

- **Version used:** v1.1
- **DOI:** [10.5281/zenodo.21827821](https://doi.org/10.5281/zenodo.21827821)
- **Description:** 305,123 U.S. manufacturing parcels (CONUS), derived from proprietary parcel fabrics with NAICS-based sector filtering.
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
| Open | `composite_exclusions_open.tif` | `composite_exclusions_wind_open.tif` |
| Reference | `composite_exclusions_reference.tif` | `composite_exclusions_wind_reference.tif` |
| Limited | `composite_exclusions_limited.tif` | `composite_exclusions_wind_limited.tif` |
| Parcel-fabric (revPJ) | `composite_exclusions_pj.tif` | *not produced* |

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
- **Format used:** State-level shapefile/geodatabase downloads.
- **Pipeline usage:** Consumed by `scripts/data_download/flag_parcels_one_state_nwi*.R` to produce per-parcel NWI flags (any-intersection and coverage-fraction variants). Merged CONUS flag file: `intermediate/wind_flags/flag_nwi.csv`.

---

## Slope

### SRTM 1-arcsec DEM (default) or 3DEP where higher resolution needed

- **SRTM 1-arcsec:** <https://earthexplorer.usgs.gov/> (SRTM 1 Arc-Second Global).
- **3DEP (higher resolution alternative):** <https://apps.nationalmap.gov/downloader/>
- **Threshold used:** slope > 25% (14° or steeper) flags a parcel for wind exclusion.
- **Pipeline usage:** Downloaded and flagged per-tile via `scripts/data_download/flag_parcels_one_tile_slope.R`; merged into `intermediate/wind_flags/flag_slope_gt25.csv`.

---

## Airport locations

### HIFLD Public Use Airports

- **Provider:** Homeland Infrastructure Foundation-Level Data (HIFLD).
- **URL:** <https://hifld-geoplatform.hub.arcgis.com/> (search "Public Use Airports").
- **Pipeline usage:** Buffered to 3 km (canonical) around each airport point; parcels overlapping the buffer are flagged for wind exclusion. Sensitivity radii (1, 2, 4, 5 km) are used in `scripts/09_airport_buffer_sensitivity.R`.

---

## DoD restricted airspace

### Department of Defense Special Use Airspace

- **Provider:** FAA / DoD (published via HIFLD).
- **URL:** <https://hifld-geoplatform.hub.arcgis.com/> (search "Special Use Airspace").
- **Pipeline usage:** Restricted-airspace polygons are used to flag parcels for wind exclusion.

---

## USFWS Critical Habitat

- **Provider:** U.S. Fish and Wildlife Service.
- **URL:** <https://ecos.fws.gov/ecp/report/table/critical-habitat.html>
- **Pipeline usage:** Any-intersection flag; parcels overlapping designated critical habitat are excluded from the NLCD wind binary result.

---

## Urban areas

### U.S. Census Bureau Urban Areas

- **Provider:** U.S. Census Bureau (TIGER/Line).
- **URL:** <https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html> (Urban Areas layer).
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
| SRTM/3DEP slope | `data_download/` → script 10 | Yes (USGS) |
| HIFLD Public Use Airports | scripts 08, 09 | Yes (HIFLD) |
| DoD Special Use Airspace | script 08 | Yes (HIFLD) |
| USFWS Critical Habitat | script 08 | Yes (USFWS) |
| Census Urban Areas | script 08 | Yes (Census) |

All ancillary datasets are public; the parcel geometries are the only proprietary input, and access is governed by the M-FIND terms on Zenodo.
