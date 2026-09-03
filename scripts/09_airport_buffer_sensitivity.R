# Task 1D extension: Airport buffer sensitivity for NLCD wind pct + binary.
#
# Motivation: in the baseline pct+binary run (08_nlcd_wind_binary_exclusions.R),
# the FAA airport 5 km buffer is the single largest binary exclusion
# (1.26M ac zeroed if applied alone; 621k ac zeroed exclusively). A reviewer
# will ask how sensitive NLCD pct+binary totals are to that 5 km choice.
#
# This script sweeps the airport buffer distance across:
#   {1, 3, 5 (baseline), 8, 10} km
# and, for each, recomputes:
#   - total NLCD wind pct+binary usable area (CONUS)
#   - size-bin decomposition
#   - parcels flagged by airport (any, exclusive)
#   - acres zeroed if airport alone applied, and exclusively
#
# Efficiency: we reuse the existing flag_urban / flag_dod_sua / flag_usfws /
# flag_lt_1ac columns from the baseline pct+binary output. Only flag_airport
# changes with buffer distance. That means:
#   - load baseline pct+binary CSV once (has flags + pct-only wind ac)
#   - load airport point layer once, reproject to EPSG:5070
#   - for each buffer distance: st_buffer -> st_intersects -> recompute usable
#
# Output: Scripts/applied_energy_paper/outputs/nlcd_wind/airport_buffer_sensitivity/
#   airport_buffer_sensitivity_totals.csv
#   airport_buffer_sensitivity_by_size_bin.csv
#   airport_buffer_sensitivity_marginal.csv
#   run_log.txt

suppressPackageStartupMessages({
  library(sf)
  library(dplyr)
  library(readr)
  library(tibble)
  library(purrr)
})

REPO <- "/Users/rose501/Library/CloudStorage/OneDrive-PNNL/Desktop/IEDO"
PARCELS_GPKG <- file.path(REPO, "Scripts/applied_energy_paper/intermediate/parcels_conus_2026_04_23.gpkg")
PCT_BIN_CSV  <- file.path(REPO, "Scripts/applied_energy_paper/outputs/nlcd_wind/nlcd_wind_percentage_plus_binary.csv")
AIRPORTS_SHP <- file.path(REPO, "Data/wind_exclusions/Airports/Airports.shp")
OUT_DIR <- file.path(REPO, "Scripts/applied_energy_paper/outputs/nlcd_wind/airport_buffer_sensitivity")
dir.create(OUT_DIR, showWarnings = FALSE, recursive = TRUE)

M2_PER_ACRE <- 4046.8564224
PROJ_CRS    <- 5070  # CONUS Albers Equal Area (meters)
BUFFERS_M   <- c(1000, 3000, 5000, 8000, 10000)
BASELINE_M  <- 5000

SIZE_BIN_ORDER <- c("tiny", "small", "medium", "large", "xlarge")

log_lines <- character()
logln <- function(msg) {
  ts <- format(Sys.time(), "%H:%M:%S")
  line <- sprintf("[%s] %s", ts, msg)
  message(line)
  log_lines[[length(log_lines) + 1]] <<- line
}

# ---------------------------------------------------------------------------
# Load baseline pct+binary output (contains all non-airport flags + pct-only wind ac)
# ---------------------------------------------------------------------------
logln(sprintf("Loading baseline pct+binary CSV: %s", PCT_BIN_CSV))
base <- readr::read_csv(PCT_BIN_CSV, show_col_types = FALSE)
logln(sprintf("  %d parcels loaded", nrow(base)))

# Sanity-check baseline totals
baseline_pct_only_ac <- sum(base$usable_area_nlcd_wind_ac)
baseline_pct_bin_ac  <- sum(base$usable_area_nlcd_wind_bin_ac)
logln(sprintf("  baseline pct-only total:   %.0f ac", baseline_pct_only_ac))
logln(sprintf("  baseline pct+binary total: %.0f ac (5 km buffer)", baseline_pct_bin_ac))

# ---------------------------------------------------------------------------
# Load parcel geometries
# ---------------------------------------------------------------------------
logln(sprintf("Loading parcel geometries: %s", PARCELS_GPKG))
parcels <- sf::st_read(PARCELS_GPKG, quiet = TRUE) %>%
  dplyr::select(PARCEL_LID) %>%
  sf::st_transform(PROJ_CRS) %>%
  dplyr::filter(PARCEL_LID %in% base$PARCEL_LID)
logln(sprintf("  %d parcel geometries (joined to CSV)", nrow(parcels)))

# ---------------------------------------------------------------------------
# Load airport points (no buffer yet) and crop to parcel bbox + largest buffer
# ---------------------------------------------------------------------------
logln(sprintf("Loading airports: %s", AIRPORTS_SHP))
airports_raw <- sf::st_read(AIRPORTS_SHP, quiet = TRUE) %>%
  sf::st_transform(PROJ_CRS) %>%
  sf::st_make_valid()
logln(sprintf("  %d airport points (raw)", nrow(airports_raw)))

# Crop to parcel bbox padded by max buffer, to cut st_buffer cost.
bb <- sf::st_bbox(parcels)
pad <- max(BUFFERS_M) + 1000
bb_expanded <- bb + c(-pad, -pad, pad, pad)
bb_poly <- sf::st_as_sfc(sf::st_bbox(bb_expanded, crs = PROJ_CRS))
airports_raw <- suppressWarnings(sf::st_crop(airports_raw, bb_poly))
logln(sprintf("  %d airport points after CONUS bbox crop", nrow(airports_raw)))

# ---------------------------------------------------------------------------
# Per-buffer computation
# ---------------------------------------------------------------------------
run_one_buffer <- function(buf_m) {
  logln(sprintf("=== Buffer = %d m ===", buf_m))
  t0 <- Sys.time()

  logln(sprintf("  buffering %d airports by %d m ...", nrow(airports_raw), buf_m))
  ap_buf <- sf::st_buffer(airports_raw, dist = buf_m)

  logln("  intersecting parcels with airport buffer ...")
  hits <- sf::st_intersects(parcels, ap_buf, sparse = TRUE)
  flag_airport_new <- lengths(hits) > 0L

  df <- base %>%
    dplyr::select(PARCEL_LID, size_bin, parcel_area_m2,
                  usable_area_nlcd_wind_ac,
                  flag_urban, flag_dod_sua, flag_usfws, flag_lt_1ac) %>%
    dplyr::mutate(
      flag_airport = flag_airport_new[match(PARCEL_LID, parcels$PARCEL_LID)],
      n_flags_nonair = as.integer(flag_lt_1ac) + as.integer(flag_urban) +
                       as.integer(flag_dod_sua) + as.integer(flag_usfws),
      n_flags = n_flags_nonair + as.integer(flag_airport),
      usable_area_nlcd_wind_bin_ac = ifelse(n_flags > 0, 0,
                                            usable_area_nlcd_wind_ac)
    )

  dt <- round(as.numeric(Sys.time() - t0, units = "secs"), 1)
  logln(sprintf("  done in %.1fs; %d parcels flagged by airport (%.1f%%)",
                dt, sum(df$flag_airport), 100 * mean(df$flag_airport)))
  df
}

runs <- purrr::map(BUFFERS_M, run_one_buffer)
names(runs) <- sprintf("%d_km", BUFFERS_M / 1000)

# ---------------------------------------------------------------------------
# Totals table
# ---------------------------------------------------------------------------
totals <- purrr::map2_dfr(BUFFERS_M, runs, function(buf_m, df) {
  tot_ac <- sum(df$usable_area_nlcd_wind_bin_ac)
  n_air  <- sum(df$flag_airport)
  # Exclusive = only airport flag triggers
  excl_only <- df$flag_airport & (df$n_flags_nonair == 0L)
  # Alone = ac that would be zeroed if this were the only exclusion applied
  # (regardless of whether other flags also fire)
  tibble(
    buffer_km = buf_m / 1000,
    n_parcels_flagged_airport = n_air,
    pct_parcels_flagged_airport = round(100 * n_air / nrow(df), 2),
    ac_pct_plus_binary = round(tot_ac, 0),
    delta_ac_vs_5km = round(tot_ac - baseline_pct_bin_ac, 0),
    delta_pct_vs_5km = round(100 * (tot_ac - baseline_pct_bin_ac) / baseline_pct_bin_ac, 2),
    n_parcels_exclusive_airport = sum(excl_only),
    ac_zeroed_airport_alone = round(sum(df$usable_area_nlcd_wind_ac[df$flag_airport]), 0),
    ac_zeroed_airport_exclusive = round(sum(df$usable_area_nlcd_wind_ac[excl_only]), 0)
  )
})
logln("Totals table:")
print(totals)

# ---------------------------------------------------------------------------
# Size-bin decomposition
# ---------------------------------------------------------------------------
bin_df <- purrr::map2_dfr(BUFFERS_M, runs, function(buf_m, df) {
  df %>%
    dplyr::group_by(size_bin) %>%
    dplyr::summarise(
      buffer_km = buf_m / 1000,
      n_parcels = dplyr::n(),
      n_any_flag = sum(n_flags > 0),
      ac_pct_plus_binary = round(sum(usable_area_nlcd_wind_bin_ac), 0),
      .groups = "drop"
    )
}) %>%
  dplyr::mutate(size_bin = factor(size_bin, levels = SIZE_BIN_ORDER)) %>%
  dplyr::arrange(buffer_km, size_bin) %>%
  dplyr::select(buffer_km, size_bin, n_parcels, n_any_flag, ac_pct_plus_binary)

# Wide view: acres pivoted across buffers by size bin
bin_wide <- bin_df %>%
  dplyr::select(size_bin, buffer_km, ac_pct_plus_binary) %>%
  tidyr::pivot_wider(names_from = buffer_km,
                     values_from = ac_pct_plus_binary,
                     names_prefix = "buf_") %>%
  dplyr::arrange(size_bin)

logln("Size-bin decomposition (long):")
print(bin_df)
logln("Size-bin decomposition (wide):")
print(bin_wide)

# ---------------------------------------------------------------------------
# Marginal effect: airport-only vs airport-exclusive across buffers
# ---------------------------------------------------------------------------
marg <- purrr::map2_dfr(BUFFERS_M, runs, function(buf_m, df) {
  excl_only <- df$flag_airport & (df$n_flags_nonair == 0L)
  tibble(
    buffer_km = buf_m / 1000,
    n_parcels_any = sum(df$flag_airport),
    n_parcels_exclusive = sum(excl_only),
    ac_zeroed_if_airport_alone = round(sum(df$usable_area_nlcd_wind_ac[df$flag_airport]), 0),
    ac_zeroed_exclusive = round(sum(df$usable_area_nlcd_wind_ac[excl_only]), 0)
  )
})
logln("Marginal effect (airport only):")
print(marg)

# ---------------------------------------------------------------------------
# Write outputs
# ---------------------------------------------------------------------------
suppressPackageStartupMessages(library(tidyr))
readr::write_csv(totals,   file.path(OUT_DIR, "airport_buffer_sensitivity_totals.csv"))
readr::write_csv(bin_df,   file.path(OUT_DIR, "airport_buffer_sensitivity_by_size_bin_long.csv"))
readr::write_csv(bin_wide, file.path(OUT_DIR, "airport_buffer_sensitivity_by_size_bin_wide.csv"))
readr::write_csv(marg,     file.path(OUT_DIR, "airport_buffer_sensitivity_marginal.csv"))
logln(sprintf("Wrote outputs to %s", OUT_DIR))

writeLines(unlist(log_lines), file.path(OUT_DIR, "run_log.txt"))
