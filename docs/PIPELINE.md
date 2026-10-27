# Pipeline

This document lists every pipeline script in run order, its inputs, and its outputs. All scripts assume the environment defined in `pixi.toml` is active (`pixi shell` or `pixi run <cmd>`).

## Convention

- Scripts numbered `00`–`13` form the main pipeline and must be run in order (some dependencies span numbers; see below). Scripts `12` and `13` summarize the reV wind turbine configurations and build the manuscript figure data.
- Figure-generation scripts and validation scripts run after the pipeline completes.
- Numbered scripts load the local data root and input paths from `config.toml` through `scripts/_config.py` (Python) or `scripts/_config.R` (R). Standalone scripts under `scripts/data_download/` and `scripts/validation/` read the `IEDO_BASE` environment variable instead. See the README.

## Main pipeline

### `00_sanity_check_parcel_universe.py`
- **Purpose.** Sanity check on the parcel universe fabric before running the pipeline.
- **Inputs.** Raw parcel fabric (see `docs/DATA_SOURCES.md`).
- **Outputs.** Console diagnostics only.

### `01_build_parcel_universe.py`
- **Purpose.** Build the 305,123-parcel CONUS manufacturing universe from the M-FIND raw parcel fabric. Applies filters (state, area, use-type) and writes the working GeoPackage that all downstream scripts consume.
- **Inputs.** M-FIND raw parcel data (see [M-FIND Zenodo dataset](https://doi.org/10.5281/zenodo.21827821)).
- **Outputs.** `intermediate/parcels_conus_2026_04_23.gpkg` (305,123 rows, EPSG:5070).

### `02_rev_solar_composite_scenarios.py`
- **Purpose.** reV solar usable area for the three composite scenarios (Open, Reference, Limited).
- **Inputs.** `intermediate/parcels_conus_2026_04_23.gpkg`; three reV composite solar exclusion rasters.
- **Outputs.** `intermediate/parcels_conus_rev_solar_composites.parquet` (per-parcel usable area for the three scenarios).

### `03_rev_solar_parcel_joined.py`
- **Purpose.** reV solar usable area for the parcel-fabric-joined variant (revPJ). Diagnostic layer only; see §3.5 of the paper.
- **Inputs.** Parcel universe; revPJ raster.
- **Outputs.** `intermediate/parcels_conus_rev_solar_pj.parquet`.

### `04_nlcd_full_population_solar.py`
- **Purpose.** NLCD solar usable area for the full 305k-parcel universe, using per-class availability percentages from Table 1 of the paper.
- **Inputs.** Per-parcel NLCD 2021 class-area CSVs (17 state-batch files, extracted via Google Earth Engine `reduceRegions`); parcel universe.
- **Outputs.** `outputs/nlcd_full_population.csv`.
- **Note.** GEE extraction is external to this repo; see `docs/DATA_SOURCES.md` for the GEE script asset ID once released.

### `05_rev_wind_composite_scenarios.py`
- **Purpose.** reV wind usable area for the three composite scenarios (Open, Reference, Limited).
- **Inputs.** Parcel universe; three reV composite wind exclusion rasters.
- **Outputs.** `intermediate/parcels_conus_rev_wind_composites.parquet`.

### `06_forest_sensitivity_solar.py`
- **Purpose.** Forest-cover sensitivity for NLCD solar (S1–S4 scenarios). Produces the table underlying the paper's forest-cover sensitivity analysis.
- **Inputs.** Per-parcel NLCD class-area CSVs; parcel universe.
- **Outputs.** `outputs/forest_sensitivity/` (summary totals, size-bin decomposition, xlarge breakdown, parcel-level).

### `07_nlcd_wind_percentage_only.py`
- **Purpose.** NLCD wind usable area with per-class availability weights only (no binary parcel-level exclusions). Baseline for scripts 08 and 10.
- **Inputs.** Per-parcel NLCD class-area CSVs; parcel universe.
- **Outputs.** `outputs/nlcd_wind/nlcd_wind_percentage_only.csv`, `..._summary.csv`.

### `08_nlcd_wind_binary_exclusions.R`
- **Purpose.** Applies the 5-layer NLCD wind binary exclusion set (parcel <1 ac, urban overlap, DoD restricted airspace, USFWS Critical Habitat, airport 3 km buffer) on top of the pct-only baseline.
- **Inputs.** `outputs/nlcd_wind/nlcd_wind_percentage_only.csv`; five binary exclusion layers (see DATA_SOURCES).
- **Outputs.** `outputs/nlcd_wind/nlcd_wind_percentage_plus_binary.csv`, `..._summary.csv`.

### `09_airport_buffer_sensitivity.R`
- **Purpose.** Sensitivity of the 5-layer binary result to airport buffer radius (1, 2, 3, 4, 5 km).
- **Inputs.** Pct-only baseline; airport point layer (HIFLD).
- **Outputs.** `outputs/nlcd_wind/airport_buffer_sensitivity/`.

### `10_rebuild_headline_3km_and_add_slope_nwi.R`
- **Purpose.** Extends the 5-layer binary result with slope >25% and NWI wetlands as the 7-layer diagnostic. Rebuilds the headline table with 3 km airport buffer as canonical.
- **Inputs.** Pct-only baseline; 5-layer binary result; slope flags (`intermediate/wind_flags/flag_slope_gt25.csv`); NWI flags (`intermediate/wind_flags/flag_nwi.csv`). Flag files are produced by scripts in `scripts/data_download/`.
- **Outputs.** Updated `outputs/nlcd_wind/nlcd_wind_percentage_plus_binary*.csv`, marginal-effect table.

### `11_parcel_area_floor_sensitivity.R`
- **Purpose.** Sensitivity of the 5-layer binary to the parcel-area floor (0.5 ac, 1 ac, 5 ac, 10 ac, 107 ac).
- **Inputs.** Pct-only baseline; 5-layer binary flags.
- **Outputs.** `outputs/nlcd_wind/parcel_area_floor_sensitivity/`.

### `12_wind_turbine_config_summaries.py`
- **Purpose.** Summarizes reV wind usable area for every turbine configuration and scenario on disk (national totals, size-bin totals, per-bin intensity, xlarge share, parcel-area-floor envelope). Missing scenarios are reported and skipped.
- **Inputs.** Per-parcel outputs of script `05` for the default turbine (`[inputs.rev_wind]`, 115 m hub height / 170 m rotor) and each additional configuration under `[inputs.rev_wind_turbines.*]` in `config.toml`.
- **Outputs.** Repo-local `outputs/`: `wind_turbine_totals.csv`, `wind_turbine_bins.csv`, `wind_turbine_intensity.csv`, `wind_turbine_xlarge_share.csv`, `wind_turbine_area_floor.csv`, `fig_bin_distribution_with_turbines.csv`.
- **Checks.** C1–C5 are printed (see the script header). C1–C3 failures exit non-zero; C4 and C5 violations are counted, not fatal.
- **Run.** `pixi run wind-turbines`.

### `13_build_manuscript_figure_data.py`
- **Purpose.** Builds the source data for the headline-totals and size-bin figures (Figures 2 and 3) on the 90 m wind grid.
- **Inputs.** `outputs/wind_turbine_bins.csv` and `outputs/wind_turbine_totals.csv` from script `12`; the published size-bin figure CSV (2026-07-31), passed as the first argument, whose solar and NLCD rows are carried through unchanged.
- **Outputs.** `outputs/fig2_bins_grid90.csv` and `outputs/fig1_totals_grid90.csv`, plus tracked copies `figures/data/fig_bins.csv` and `figures/data/fig_headline_totals.csv`. (The `fig1`/`fig2` prefixes in the `outputs/` names predate the current figure order.)
- **Checks.** F1–F4 (see the script header); exits non-zero on failure.
- **Run.** `pixi run fig-data <published_bins.csv>`.

## Figure generation

### `build_fig1_conceptual.py`
- **Purpose.** Figure 1: side-by-side methods-conceptual figure on the Ohio exemplar parcel.
- **Inputs.** Ohio exemplar parcel geometry; three reV solar composite rasters; NLCD 2021 raster window.
- **Outputs.** `figures/fig3_conceptual_ohio.png` and `.pdf`. The file name keeps its earlier `fig3` prefix because the manuscript source includes it under that name.
- **Run.** `pixi run fig1-conceptual`.

### `render_vegalite.py`
- **Purpose.** Renders Figures 2 and 3 from their Vega-Lite specs (`figures/fig_headline_usable_area.vl.json`, `figures/fig_bins.vl.json`) to vector PDF or PNG. Local CSV data referenced by the spec are inlined before rendering.
- **Inputs.** A spec plus the tracked CSV in `figures/data/` it points to.
- **Run.** vl-convert is not part of the pixi environment; use `uv run --with vl-convert-python python scripts/render_vegalite.py SPEC OUT` (tested with vl-convert-python 1.9.0). See `docs/FIGURE_TABLE_MAP.md`.

## Data-download helpers (`scripts/data_download/`)

These scripts download and flag ancillary datasets that feed script 10.

- `download_and_flag_nwi.sh` — orchestrates state-by-state NWI download + flagging.
- `download_and_flag_slope.sh` — orchestrates SRTM/3DEP slope tile download + flagging.
- `flag_parcels_one_state_nwi.R`, `flag_parcels_one_state_nwi_raster.R`, `flag_parcels_one_state_nwi_coverage.R` — per-state NWI flagging in three variants (vector, raster, coverage-fraction).
- `flag_parcels_one_tile_slope.R` — per-tile slope flagging.
- `merge_nwi_flags.R`, `merge_slope_flags.R` — CONUS-level merges of state/tile-level flag files.
- `run_nwi_coverage_sample.sh` — six-state coverage diagnostic (WY, MT, ME, MS, MN, PA).
- `nwi_tmp_watchdog.sh` — cleanup helper for long-running downloads.

## Validation (`scripts/validation/`)

- `compare_5layer_vs_rev_reference.R` — parcel-level comparison of the 5-layer NLCD wind result against reV Reference wind. Underlies the "5-layer within-envelope" claim in §4 of the paper.
- `count_any_usable_by_scenario.py` — counts non-zero-usable-area parcels by method/scenario for the headline "Retained (%)" column in Table 2.
- `compare_wind_open_layers.py` — read-only comparison of a new reV wind Open layer against the published one (whole-raster statistics and point-wise agreement). Usage: `pixi run python -u scripts/validation/compare_wind_open_layers.py OLD NEW OUTDIR`. Nothing in the pipeline uses its outputs.
- `ag_inversion_rev_zero_share_2026-10-26.py` — for parcels where NLCD wind usable area exceeds NLCD solar, reports the share with zero reV wind usable area by turbine and scenario. Console output only.
- `limited_gt_reference_2026-10-26.py` — counts parcels where reV wind Limited usable area exceeds Reference, by turbine configuration. Console output only.
- `rev_wind_gt_solar_parcels_2026-10-26.py` — counts parcels where reV wind usable area exceeds reV solar, by scenario and turbine, and their overlap with the NLCD wind > solar set. Console output only.

## Expected wall-clock cost

On a workstation with 32 GB RAM and a modern SSD:

- Scripts 01, 04, 06, 07: ~30–60 minutes each (per-parcel NLCD aggregations).
- Scripts 02, 03, 05: ~1–2 hours each (reV raster zonal stats on 305k parcels).
- Scripts 08–11: ~15–45 minutes each.
- Data-download helpers: variable, dominated by network throughput for NWI/slope tiles.

Full pipeline: **6–10 hours** end-to-end excluding data downloads.
