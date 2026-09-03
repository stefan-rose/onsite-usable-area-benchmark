# Merge per-tile slope>25% flag CSVs into authoritative flag_slope_gt25.csv.
# Per-tile CSVs contain only TRUE-flag rows; parcels absent from all tiles get FALSE.
suppressPackageStartupMessages({
  library(dplyr); library(readr); library(purrr); library(sf)
})
REPO <- "/Users/rose501/Library/CloudStorage/OneDrive-PNNL/Desktop/IEDO"
PER_TILE_DIR <- file.path(REPO, "Data/wind_exclusions/Slope/_per_tile")
OUT <- file.path(REPO, "Scripts/applied_energy_paper/intermediate/wind_flags/flag_slope_gt25.csv")
PARCELS_GPKG <- file.path(REPO,
  "Scripts/applied_energy_paper/intermediate/parcels_conus_2026_04_23.gpkg")

files <- list.files(PER_TILE_DIR, pattern = "_flags\\.csv$", full.names = TRUE)
files <- files[file.info(files)$size > 0]
cat("Per-tile non-empty CSVs:", length(files), "\n")

u <- sf::st_read(PARCELS_GPKG, quiet = TRUE) |>
  sf::st_drop_geometry() |>
  dplyr::select(PARCEL_LID) |>
  dplyr::distinct()
cat("Parcel universe:", nrow(u), "\n")

if (length(files) == 0) {
  out <- u |> dplyr::mutate(flag_slope_gt25 = FALSE)
} else {
  per_tile <- purrr::map_dfr(files, ~ readr::read_csv(.x, show_col_types = FALSE,
                                                      col_types = "cl"))
  cat("Per-tile TRUE-rows:", nrow(per_tile), "\n")
  hits <- per_tile |>
    dplyr::group_by(PARCEL_LID) |>
    dplyr::summarise(flag_slope_gt25 = any(flag_slope_gt25), .groups = "drop")
  out <- u |> dplyr::left_join(hits, by = "PARCEL_LID") |>
    dplyr::mutate(flag_slope_gt25 = dplyr::coalesce(flag_slope_gt25, FALSE))
}

cat("Flagged:", sum(out$flag_slope_gt25), "/", nrow(out),
    sprintf(" (%.2f%%)", 100 * mean(out$flag_slope_gt25)), "\n")
readr::write_csv(out, OUT)
cat("Wrote", OUT, "\n")
