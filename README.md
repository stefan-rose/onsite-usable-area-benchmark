# Onsite Usable Area Benchmark

Analysis code and figure-generation scripts for:

> **Sizing up on-site industrial energy potential: a parcel-level comparison of usable-area methods.**
> Rose, S., Ramos, D. (2026). *Applied Energy* (under review).
> Paper DOI: *forthcoming*.

This repository contains the analysis pipeline that produces every quantitative result, table, and figure in the paper. It compares two parcel-level usable-area estimators for onsite generation:

- **NLCD land-cover-proportion method** — weights each parcel's 30 m NLCD 2021 class areas by technology-specific availability percentages.
- **reV composite exclusion method** — applies coverage-fraction-weighted zonal statistics to three 90 m NLR reV composite exclusion rasters (Open, Reference, Limited) plus a fourth parcel-fabric variant (revPJ).

Both methods run over an identical 305,123-parcel CONUS manufacturing universe.

## Quickstart

```bash
# 1. Clone
git clone https://github.com/stefan-rose/onsite-usable-area-benchmark.git
cd onsite-usable-area-benchmark

# 2. Set up the environment (pixi manages both Python and R packages)
pixi install

# 3. Configure local paths (input data locations)
printf '[paths]\nbase = "/your/path/to/IEDO"\n' > config.toml
# (see docs/DATA_SOURCES.md for where to obtain each dataset)

# 4. Run the pipeline (see docs/PIPELINE.md for the full script order)
pixi run python scripts/01_build_parcel_universe.py
pixi run python scripts/02_rev_solar_composite_scenarios.py
# ...etc.
```

## Repository layout

```
.
├── LICENSE                          BSD-3-Clause
├── README.md                        This file
├── CITATION.cff                     Machine-readable citation
├── pixi.toml                        Python + R environment specification
├── config.example.toml              Template for local path configuration
├── docs/
│   ├── PIPELINE.md                  Script run order + expected outputs
│   ├── DATA_SOURCES.md              Every input dataset with DOI/URL
│   └── FIGURE_TABLE_MAP.md          Manuscript figure/table → script mapping
├── figures/                         Vega-Lite specs, rendered PDFs, and figure data
│   └── data/                        Aggregate CSVs behind the figures (committed)
├── scripts/                         14 numbered pipeline scripts (00–13) + figure scripts
│   ├── data_download/               NWI + slope tile download & flagging helpers
│   └── validation/                  Cross-method validation scripts
├── outputs/                         Aggregate CSVs (not committed; reproduced locally)
└── intermediate/                    Per-parcel tables (not committed; reproduced locally)
```

## Input data

Underlying data are **not redistributed in this repository**. See [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) for provenance and access instructions. In brief:

- **Parcel geometries** — the 305,123-parcel CONUS manufacturing universe is a derived product of proprietary parcel fabrics (LightBox, Land Records). The **M-FIND dataset** (Zenodo DOI [10.5281/zenodo.21827821](https://doi.org/10.5281/zenodo.21827821), v1.1) is the reproducibility anchor and defines the parcel identifiers used throughout.
- **reV composite exclusion rasters** — released by NLR; see DATA_SOURCES.md for the current supply-curve release.
- **NLCD 2021** — public, U.S. Geological Survey / MRLC.
- **NWI wetlands, slope (SRTM/3DEP), airport buffers, DoD restricted airspace, USFWS Critical Habitat, urban areas** — all public federal or state datasets; sources listed individually.

## Path configuration

All pipeline scripts load their input paths from a single `config.toml` at the repo root, via the shared helpers `scripts/_config.py` (Python) and `scripts/_config.R` (R). To run on a new machine:

1. Create `config.toml` containing only `[paths]` and `base = "/your/path/to/IEDO"`. Alternatively, export `IEDO_BASE=/your/path/to/IEDO`.
2. Add any `[inputs.*]` overrides to `config.toml` only if your data layout differs from the defaults in `config.example.toml`.

`config.toml` is gitignored, so your local paths never enter version control. The helpers read `config.example.toml` and merge `config.toml` over it. `IEDO_BASE` overrides `paths.base`. Standalone scripts under `scripts/data_download/` and `scripts/validation/` read `IEDO_BASE` directly.

**Current caveat.** Scripts `00`–`11` still write their outputs under `<base>/Scripts/...` (for example `<base>/Scripts/method_comparison/outputs/`) rather than to the repo-local `outputs/` directory. This preserves the original inter-script dependency layout (each script reads the previous script's outputs from that same rooted location). Overriding `paths.base` propagates to all of those locations consistently. Scripts `12` and `13` already use the repo-local `outputs/` directory (`OUTPUTS` in `_config`), and script `13` also writes tracked copies of the figure data to `figures/data/`. A future refactor will migrate the remaining output tree into the repo.

## Reproducibility notes

- **Environment.** Library versions are pinned via `pixi.toml`. Regenerating the environment on a fresh machine should produce byte-identical numeric outputs from the same inputs.
- **NLCD class-area extraction** is performed in Google Earth Engine (see script 04 header). The GEE reduceRegions call uses fractional-coverage cell assignment; results are deterministic for a fixed asset ID.
- **Random seeds** — no stochastic components in the pipeline; all operations are deterministic given fixed inputs.
- **Spatial projection** — all spatial operations occur in EPSG:5070 (NAD83 / CONUS Albers Equal Area).
- **Wall-clock cost.** A full pipeline rebuild on a workstation with 32 GB RAM takes approximately 6–10 hours dominated by raster zonal statistics on the 305k-parcel universe.

## Citation

If you use this code or its outputs, please cite both the paper and this repository. See `CITATION.cff`.

## License

BSD 3-Clause License. See `LICENSE`.

## Contact

Stefan Rose — Pacific Northwest National Laboratory — stefan.rose@pnnl.gov
