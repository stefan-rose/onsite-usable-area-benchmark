# outputs/

Aggregate CSVs and summary tables produced by the pipeline. **Not tracked in git** — regenerate locally by running the pipeline (see `docs/PIPELINE.md`).

## Expected contents after a full pipeline run

```
outputs/
├── nlcd_full_population.csv                       # Script 04
├── forest_sensitivity/                            # Script 06
│   ├── forest_sensitivity_summary_totals.csv
│   ├── forest_sensitivity_by_size_bin.csv
│   ├── forest_sensitivity_xlarge_breakdown.csv
│   └── forest_sensitivity_parcel_level.csv
└── nlcd_wind/                                     # Scripts 07, 08, 09, 10, 11
    ├── nlcd_wind_percentage_only.csv
    ├── nlcd_wind_percentage_only_summary.csv
    ├── nlcd_wind_percentage_plus_binary.csv
    ├── nlcd_wind_percentage_plus_binary_summary.csv
    ├── nlcd_wind_exclusion_marginal_effect.csv
    ├── nlcd_wind_flag_counts.csv
    ├── airport_buffer_sensitivity/
    └── parcel_area_floor_sensitivity/
```

See `docs/FIGURE_TABLE_MAP.md` for which manuscript table each file underlies.
