# Merge per-state NWI flag CSVs into authoritative flag_nwi.csv.
suppressPackageStartupMessages({
  library(dplyr); library(readr); library(purrr); library(sf)
})
REPO <- "/Users/rose501/Library/CloudStorage/OneDrive-PNNL/Desktop/IEDO"
PER_STATE_DIR <- file.path(REPO, "Data/wind_exclusions/NWI")
OUT <- file.path(REPO, "Scripts/applied_energy_paper/intermediate/wind_flags/flag_nwi.csv")
PARCELS_GPKG <- file.path(REPO,
  "Scripts/applied_energy_paper/intermediate/parcels_conus_2026_04_23.gpkg")

files <- list.files(PER_STATE_DIR, pattern = "_nwi_parcel_flags\\.csv$", full.names = TRUE)
cat("Per-state CSVs found:", length(files), "\n")
if (length(files) == 0) stop("No per-state NWI flag files to merge")

all <- purrr::map_dfr(files, function(f) {
  readr::read_csv(f, show_col_types = FALSE, col_types = "cl")
})
cat("Rows (pre-dedup):", nrow(all), "\n")

# A parcel can appear in the pad bbox of multiple states; take OR.
hits <- all %>%
  dplyr::group_by(PARCEL_LID) %>%
  dplyr::summarise(flag_nwi = any(flag_nwi), .groups = "drop")

# Left-join against parcel universe so every parcel has a row; default FALSE.
u <- sf::st_read(PARCELS_GPKG, quiet = TRUE) |>
  sf::st_drop_geometry() |>
  dplyr::select(PARCEL_LID) |>
  dplyr::distinct()
out <- u %>%
  dplyr::left_join(hits, by = "PARCEL_LID") %>%
  dplyr::mutate(flag_nwi = dplyr::coalesce(flag_nwi, FALSE))

cat("Flagged:", sum(out$flag_nwi), "/", nrow(out),
    sprintf(" (%.2f%%)", 100 * mean(out$flag_nwi)), "\n")
readr::write_csv(out, OUT)
cat("Wrote", OUT, "\n")
