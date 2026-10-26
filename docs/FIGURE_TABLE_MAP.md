# Figure and table mapping

Each manuscript figure and table is produced by (or aggregated from) specific scripts in this repository. Numbering follows the published paper; regenerating a specific figure or table requires the listed script(s) to have run successfully.

## Tables

| Table | Content | Produced by | Notes |
|---|---|---|---|
| 1 | NLCD land-cover availability percentages (solar and wind) | Hand-curated in the manuscript | Anchors documented in Appendix A of the paper. |
| 2 | National headline usable-area totals | Aggregated from scripts `02`, `03`, `04`, `05`, `07`, `08`, `10` | Retained % column produced by `scripts/validation/count_any_usable_by_scenario.py`. |
| 3 | Parcel-size bin decomposition | Aggregated from the same headline output files as Table 2 | Size bins defined in `scripts/01_build_parcel_universe.py`. |
| 4 | Forest-cover sensitivity (S1–S4) | `scripts/06_forest_sensitivity_solar.py` | Output: `outputs/forest_sensitivity/forest_sensitivity_summary_totals.csv`. |
| 5 | Airport buffer sensitivity | `scripts/09_airport_buffer_sensitivity.R` | Output: `outputs/nlcd_wind/airport_buffer_sensitivity/`. |
| 6 | Parcel-area floor sensitivity | `scripts/11_parcel_area_floor_sensitivity.R` | Output: `outputs/nlcd_wind/parcel_area_floor_sensitivity/`. |
| 7 | Marginal effect of each binary exclusion (NLCD wind) | `scripts/10_rebuild_headline_3km_and_add_slope_nwi.R` | Output: `outputs/nlcd_wind/nlcd_wind_exclusion_marginal_effect.csv`. |
| 8 | NWI coverage-fraction distribution (6-state sample) | `scripts/data_download/flag_parcels_one_state_nwi_coverage.R` (per state) → aggregated | Consumed by the discussion in §5.3. |
| 9 | NWI threshold sensitivity | Aggregated from the 6-state coverage output | See discussion in §5.3. |
| 10 | Suggested scenario choice by analytical purpose | Hand-curated in the manuscript | No underlying pipeline output. |
| 11 | NLCD/reV exclusion crosswalk (Appendix B) | Hand-curated in the manuscript from Lopez 2024 exclusion dictionaries | No underlying pipeline output. |

## Figures

| Figure | Content | Produced by | Notes |
|---|---|---|---|
| 1 | Methods conceptual figure on the Ohio exemplar parcel | `scripts/build_fig3.py` | |
| 2 | National headline usable-area totals: reV envelope and NLCD points, log scale, solar and wind | Data: `scripts/13_build_manuscript_figure_data.py` → `figures/data/fig_headline_totals.csv`. Spec: `figures/fig_headline_usable_area.vl.json` | Same values as Table 2. Diagnostic rows (reV Parcel Joined, NLCD 7-layer wind) are not plotted. Values are inlined in the spec by layer. |
| 3 | Usable area by parcel size bin, solar and wind | Data: `scripts/13_build_manuscript_figure_data.py` → `figures/data/fig_bins.csv`. Spec: `figures/fig_bins.vl.json` | Same values as Table 3. Bar totals equal Table 2. |

Figures 2 and 3 are rendered to vector PDF at print size with

```bash
uv run --with vl-convert-python python scripts/render_vegalite.py figures/fig_bins.vl.json figures/fig_bins.pdf
```

`figures/data/` holds national aggregates only (no per-parcel values). Script 13 writes these tracked copies alongside its `outputs/` files.
