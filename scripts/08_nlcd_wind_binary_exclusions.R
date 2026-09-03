# Task 1D (part 2 of 2): NLCD wind — percentage + binary exclusions sensitivity.
#
# Applies five binary exclusions from the internal methods doc to the
# percentage-only output of 07_nlcd_wind_percentage_only.py:
#
#   1. parcel_area_m2 < 4046.86  (parcel < 1 ac)        [from CSV column]
#   2. Urban Areas intersect                             [Data/wind_exclusions/Urban_Areas]
#   3. DoD / FAA Special Use Airspace intersect          [Data/wind_exclusions/FAA_SUA]
#   4. USFWS Critical Habitat (POLY only) intersect     [Data/wind_exclusions/Critical_Hab_POLY]
#   5. FAA Airport AIRPORT_BUFFER_M buffer intersect     [Data/wind_exclusions/Airports]
#
# Any flag -> usable_area = 0.
#
# Airport buffer rationale (see literature_check_binary_exclusions.md, 2026-04-29):
# Lopez 2023 uses 14 CFR Part 77.9 runway-length tiers (6.1 km long runways,
# 3.0 km short runways, 1.5 km heliports). A runway-count-weighted average is
# ~3.6 km. The closest defensible single-buffer proxy is 3 km, which is now
# the headline value. The 5 km previous value is preserved in
# _archive_5km_buffer_2026_04_29/ and a full 1/3/5/8/10 km sweep lives in
# outputs/nlcd_wind/airport_buffer_sensitivity/.
#
# Output: Scripts/applied_energy_paper/outputs/nlcd_wind/
#   nlcd_wind_percentage_plus_binary.csv
#   nlcd_wind_percentage_plus_binary_summary.csv
#   nlcd_wind_exclusion_marginal_effect.csv
#   run_log.txt

suppressPackageStartupMessages({
  library(sf)
  library(dplyr)
  library(readr)
  library(tibble)
  library(purrr)
})

# Path configuration: load BASE and named input paths from config.toml at
# the repo root (falls back to config.example.toml if config.toml is absent).
.script_dir <- if (length(grep("^--file=", commandArgs(trailingOnly = FALSE))) > 0) {
  dirname(normalizePath(sub("^--file=", "", grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)[1])))
} else if (!is.null(sys.frame(1)$ofile)) {
  dirname(normalizePath(sys.frame(1)$ofile))
} else { file.path(getwd(), "scripts") }
source(file.path(.script_dir, "_config.R"))
REPO <- BASE  # backwards-compat alias used by this script
PARCELS_GPKG <- file.path(REPO, "Scripts/applied_energy_paper/intermediate/parcels_conus_2026_04_23.gpkg")
PCT_ONLY_CSV <- file.path(REPO, "Scripts/applied_energy_paper/outputs/nlcd_wind/nlcd_wind_percentage_only.csv")
OUT_DIR <- file.path(REPO, "Scripts/applied_energy_paper/outputs/nlcd_wind")
dir.create(OUT_DIR, showWarnings = FALSE, recursive = TRUE)

M2_PER_ACRE      <- 4046.8564224
PROJ_CRS         <- 5070  # CONUS Albers Equal Area (meters). Use for all spatial ops.
AIRPORT_BUFFER_M <- 3000  # Headline value. See methods note above. (Prev 5000.)

log_lines <- character()
logln <- function(msg) {
  ts <- format(Sys.time(), "%H:%M:%S")
  line <- sprintf("[%s] %s", ts, msg)
  message(line)
  log_lines[[length(log_lines) + 1]] <<- line
}

# ---------------------------------------------------------------------------
# Load inputs
# ---------------------------------------------------------------------------
logln(sprintf("Loading percentage-only CSV: %s", PCT_ONLY_CSV))
pct <- readr::read_csv(PCT_ONLY_CSV, show_col_types = FALSE)
logln(sprintf("  %d parcels, %.0f ac total wind (percentage-only)",
              nrow(pct), sum(pct$usable_area_nlcd_wind_ac)))

logln(sprintf("Loading parcel geometries: %s", PARCELS_GPKG))
parcels <- sf::st_read(PARCELS_GPKG, quiet = TRUE) %>%
  dplyr::select(PARCEL_LID) %>%
  sf::st_transform(PROJ_CRS)
logln(sprintf("  %d parcel geometries", nrow(parcels)))

# Parcel universe = intersection of both.
parcels <- parcels %>% dplyr::filter(PARCEL_LID %in% pct$PARCEL_LID)
logln(sprintf("  %d parcels after join to CSV", nrow(parcels)))

# ---------------------------------------------------------------------------
# Exclusion layer loader — transform to CONUS Albers, union geometries for
# cheap st_intersects, and clean invalid features.
# ---------------------------------------------------------------------------
load_excl <- function(path, name, buffer_m = NULL, crop_to = NULL) {
  logln(sprintf("Loading exclusion layer: %s", name))
  t0 <- Sys.time()
  x <- sf::st_read(path, quiet = TRUE)
  x <- sf::st_transform(x, PROJ_CRS)
  x <- sf::st_make_valid(x)
  # Optional: crop to the parcel universe bbox (expanded by buffer) to cut down
  # the feature count dramatically for layers with global extent (e.g., CritHab
  # has Hawaiian and Pacific territory polygons that will never hit CONUS parcels).
  if (!is.null(crop_to)) {
    bb <- sf::st_bbox(crop_to)
    pad <- ifelse(!is.null(buffer_m) && buffer_m > 0, buffer_m, 0) + 1000
    bb_expanded <- bb + c(-pad, -pad, pad, pad)
    bb_poly <- sf::st_as_sfc(sf::st_bbox(bb_expanded, crs = PROJ_CRS))
    before <- nrow(x)
    x <- suppressWarnings(sf::st_crop(x, bb_poly))
    logln(sprintf("  cropped %d -> %d features", before, nrow(x)))
  }
  if (!is.null(buffer_m) && buffer_m > 0) {
    logln(sprintf("  buffering by %.0f m", buffer_m))
    x <- sf::st_buffer(x, dist = buffer_m)
  }
  logln(sprintf("  %d features ready (%.1fs)", nrow(x),
                as.numeric(Sys.time() - t0, units = "secs")))
  x
}

urban    <- load_excl(file.path(REPO, "Data/wind_exclusions/Urban_Areas/Urban_Areas.shp"),
                      "Urban Areas (TIGER UACE20)",
                      crop_to = parcels)
sua      <- load_excl(file.path(REPO, "Data/wind_exclusions/FAA_SUA/Special_Use_Airspace.shp"),
                      "FAA Special Use Airspace",
                      crop_to = parcels)
crithab  <- load_excl(file.path(REPO, "Data/wind_exclusions/Critical_Hab_POLY/crithab_poly.shp"),
                      "USFWS Critical Habitat (POLY)",
                      crop_to = parcels)
airports <- load_excl(file.path(REPO, "Data/wind_exclusions/Airports/Airports.shp"),
                      sprintf("FAA Airports (%.1f km buffer)", AIRPORT_BUFFER_M / 1000),
                      buffer_m = AIRPORT_BUFFER_M,
                      crop_to = parcels)

# ---------------------------------------------------------------------------
# Spatial flags — st_intersects returns a sparse list; presence = flag.
# ---------------------------------------------------------------------------
flag_intersects <- function(parcels_sf, layer_sf, label) {
  logln(sprintf("Flagging intersections: %s", label))
  hits <- sf::st_intersects(parcels_sf, layer_sf, sparse = TRUE)
  flag <- lengths(hits) > 0L
  logln(sprintf("  %d / %d parcels flagged (%.2f%%)",
                sum(flag), length(flag), 100 * mean(flag)))
  flag
}

parcels$flag_urban   <- flag_intersects(parcels, urban,    "urban")
parcels$flag_dod_sua <- flag_intersects(parcels, sua,      "DoD SUA")
parcels$flag_usfws   <- flag_intersects(parcels, crithab,  "USFWS critical habitat")
parcels$flag_airport <- flag_intersects(parcels, airports,
                                         sprintf("airport %.1f km buffer", AIRPORT_BUFFER_M / 1000))

# ---------------------------------------------------------------------------
# Build parcel-level output
# ---------------------------------------------------------------------------
flags_df <- parcels %>%
  sf::st_drop_geometry() %>%
  dplyr::select(PARCEL_LID, flag_urban, flag_dod_sua, flag_usfws, flag_airport)

out <- pct %>%
  dplyr::left_join(flags_df, by = "PARCEL_LID") %>%
  dplyr::mutate(
    flag_lt_1ac = parcel_area_m2 < 4046.86,
    # any flag -> zero out
    n_flags = as.integer(flag_lt_1ac) + as.integer(flag_urban) +
              as.integer(flag_dod_sua) + as.integer(flag_usfws) +
              as.integer(flag_airport),
    usable_area_nlcd_wind_bin_m2 = ifelse(n_flags > 0, 0, usable_area_nlcd_wind_m2),
    usable_area_nlcd_wind_bin_ac = usable_area_nlcd_wind_bin_m2 / M2_PER_ACRE
  )

total_pct_only_ac <- sum(out$usable_area_nlcd_wind_ac)
total_bin_ac      <- sum(out$usable_area_nlcd_wind_bin_ac)
excluded_ac       <- total_pct_only_ac - total_bin_ac
logln(sprintf("Percentage-only total:   %.0f ac", total_pct_only_ac))
logln(sprintf("After binary exclusions: %.0f ac", total_bin_ac))
logln(sprintf("Zeroed by exclusions:    %.0f ac (%.1f%%)",
              excluded_ac, 100 * excluded_ac / total_pct_only_ac))

# ---------------------------------------------------------------------------
# Marginal effect of each exclusion:
#   exclusive-effect  = parcels where ONLY this flag triggers
#   cumulative-effect = parcels where this flag triggers (alone or w/ others)
# Report area zeroed under each column.
# ---------------------------------------------------------------------------
flag_cols <- c("flag_lt_1ac", "flag_urban", "flag_dod_sua", "flag_usfws", "flag_airport")
marg_rows <- purrr::map_dfr(flag_cols, function(fc) {
  this  <- out[[fc]]
  other <- out$n_flags - as.integer(this)
  excl_only <- this & (other == 0L)
  any_hit   <- this
  tibble(
    exclusion = fc,
    n_parcels_any = sum(any_hit),
    n_parcels_exclusive = sum(excl_only),
    ac_zeroed_if_this_alone = round(sum(out$usable_area_nlcd_wind_ac[this]), 0),
    ac_zeroed_exclusive      = round(sum(out$usable_area_nlcd_wind_ac[excl_only]), 0)
  )
})
logln("Marginal exclusion effect:")
print(marg_rows)

# ---------------------------------------------------------------------------
# Size-bin decomposition
# ---------------------------------------------------------------------------
SIZE_BIN_ORDER <- c("tiny", "small", "medium", "large", "xlarge")
bin_df <- out %>%
  dplyr::group_by(size_bin) %>%
  dplyr::summarise(
    n_parcels = dplyr::n(),
    n_any_flag = sum(n_flags > 0),
    pct_only_ac = round(sum(usable_area_nlcd_wind_ac), 0),
    pct_plus_bin_ac = round(sum(usable_area_nlcd_wind_bin_ac), 0),
    bin_delta_pct = round(
      100 * (sum(usable_area_nlcd_wind_bin_ac) - sum(usable_area_nlcd_wind_ac)) /
        pmax(sum(usable_area_nlcd_wind_ac), 1e-9), 2
    ),
    .groups = "drop"
  ) %>%
  dplyr::mutate(size_bin = factor(size_bin, levels = SIZE_BIN_ORDER)) %>%
  dplyr::arrange(size_bin)

# Append CONUS total row
total_row <- tibble(
  size_bin = "CONUS_total",
  n_parcels = nrow(out),
  n_any_flag = sum(out$n_flags > 0),
  pct_only_ac = round(total_pct_only_ac, 0),
  pct_plus_bin_ac = round(total_bin_ac, 0),
  bin_delta_pct = round(100 * (total_bin_ac - total_pct_only_ac) / total_pct_only_ac, 2)
)
bin_df <- dplyr::bind_rows(dplyr::mutate(bin_df, size_bin = as.character(size_bin)), total_row)

# ---------------------------------------------------------------------------
# Write outputs
# ---------------------------------------------------------------------------
readr::write_csv(out,       file.path(OUT_DIR, "nlcd_wind_percentage_plus_binary.csv"))
readr::write_csv(bin_df,    file.path(OUT_DIR, "nlcd_wind_percentage_plus_binary_summary.csv"))
readr::write_csv(marg_rows, file.path(OUT_DIR, "nlcd_wind_exclusion_marginal_effect.csv"))
logln(sprintf("Wrote %s", file.path(OUT_DIR, "nlcd_wind_percentage_plus_binary.csv")))
logln(sprintf("Wrote %s", file.path(OUT_DIR, "nlcd_wind_percentage_plus_binary_summary.csv")))
logln(sprintf("Wrote %s", file.path(OUT_DIR, "nlcd_wind_exclusion_marginal_effect.csv")))

writeLines(unlist(log_lines), file.path(OUT_DIR, "run_log_binary.txt"))
