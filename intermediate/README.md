# intermediate/

Per-parcel intermediate tables (parquet, GeoPackage) produced by the pipeline. **Not tracked in git** — regenerate locally by running the pipeline (see `docs/PIPELINE.md`).

## Expected contents after a full pipeline run

```
intermediate/
├── parcels_conus_2026_04_23.gpkg                  # Script 01, 305,123 parcels
├── parcels_conus_2026_04_23_manifest.txt          # Provenance manifest
├── parcels_conus_rev_solar_composites.parquet     # Script 02
├── parcels_conus_rev_solar_pj.parquet             # Script 03
├── parcels_conus_rev_wind_composites.parquet      # Script 05
├── dem_tiles_needed.txt                           # Slope-download planner
└── wind_flags/                                    # Scripts in data_download/
    ├── flag_nwi.csv
    └── flag_slope_gt25.csv
```

Total size on disk after a full run: approximately 200 MB.
