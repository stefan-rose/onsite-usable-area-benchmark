# Task 1D revision (2026-04-29; NWI completed 2026-04-30):
#   1. Switch headline NLCD pct+binary airport buffer from 5 km -> 3 km.
#   2. Add slope >25% as a new binary exclusion (Lopez 2023 Reference terrain layer).
#   3. Add USFWS National Wetlands Inventory (NWI) as a new binary exclusion.
#
# This script is the *final* integrator. It depends on preprocessed inputs:
#   - Archived 5 km pct+binary CSV (for non-airport flags + pct-only wind ac)
#   - Airport 3 km flag recomputed here (cheap — 19,243 points, ~4s st_intersects)
#   - Slope >25% parcel flag table from 11_slope_exclusion.R
#   - NWI parcel flag table from 12_nwi_exclusion.R (rasterize method; see
#     data_download/flag_parcels_one_state_nwi_raster.R)
#
# Final headline output:
#   nlcd_wind_percentage_plus_binary.csv         (305,123 parcels, all flags)
#   nlcd_wind_percentage_plus_binary_summary.csv (size-bin decomposition)
#   nlcd_wind_exclusion_marginal_effect.csv      (per-exclusion marginal)
#   run_log.txt
#
# Provenance: preserves the archived 5 km run at _archive_5km_buffer_2026_04_29/,
# and the per-layer flag tables under intermediate/wind_flags/ so reruns cheap.
#
# ---------------------------------------------------------------------------
# FRAMING NOTES FOR PAPER (2026-04-30 validation)
# ---------------------------------------------------------------------------
# Two outputs are computed here, philosophically distinct from reV scenarios:
#
#   A) 5-LAYER binary (lt_1ac, urban, dod_sua, usfws, airport_3km):
#      Headline for Task 1D. ~1.31 M ac. Philosophically closest to reV
#      Reference (0.79 M ac on same parcels) in order of magnitude, but
#      parcel-level agreement is poor (kappa = 0.157); the methods identify
#      different subsets of parcels as developable. Do NOT claim 5-layer
#      "approximates" or "reproduces" reV Reference — it produces a
#      comparable-magnitude estimate via different semantics.
#
#   B) 7-LAYER binary (A + slope_gt25 + nwi):
#      Stricter filter. ~0.14 M ac. Philosophically paired with reV Limited
#      (0.24 M ac). Again, parcel-level agreement is near-random (kappa = 0.013).
#      Spot-check (validation/parcel_spotcheck/nwi_only_spotcheck_findings.md)
#      confirmed that large-parcel NWI-only flags in arid west are dominated
#      by real intermittent-lake / salt-flat features that NLCD mislabels as
#      Barren. NWI is therefore a correction, not just a restriction, for
#      these cases.
#
# HOW TO REPORT IN PAPER:
#   - Report BOTH 5-layer and 7-layer as scenarios at different restriction
#     levels, NOT as estimates-of-truth.
#   - Frame 7-layer as "strict binary exclusion" or "strict parcel-level
#     permittability filter", not as "available wind potential."
#   - Pair 5-layer <-> reV Reference and 7-layer <-> reV Limited in any
#     side-by-side comparison, but flag that magnitude alignment is
#     coincidental at the total level; parcel-level composition differs.
#   - Do NOT headline the raw 9.5x reduction from 5->7 layers without
#     immediately noting: (a) binary-parcel semantics amplify small features,
#     (b) NWI also corrects NLCD's underclassification of arid intermittent
#     wetlands, (c) the "true" developable fraction depends on whether
#     sub-parcel siting flexibility exists (permitting reality).
#   - Cite the parcel spot-check in the methods/discussion.
# ---------------------------------------------------------------------------

suppressPackageStartupMessages({
  library(sf)
  library(dplyr)
  library(readr)
  library(tibble)
  library(purrr)
})

REPO <- "/Users/rose501/Library/CloudStorage/OneDrive-PNNL/Desktop/IEDO"

ARCHIVE_5KM_CSV <- file.path(REPO,
  "Scripts/applied_energy_paper/outputs/nlcd_wind/_archive_5km_buffer_2026_04_29/nlcd_wind_percentage_plus_binary.csv")
PARCELS_GPKG    <- file.path(REPO,
  "Scripts/applied_energy_paper/intermediate/parcels_conus_2026_04_23.gpkg")
AIRPORTS_SHP    <- file.path(REPO, "Data/wind_exclusions/Airports/Airports.shp")

# Optional per-layer flag tables — added in follow-up scripts.
SLOPE_FLAGS_CSV <- file.path(REPO,
  "Scripts/applied_energy_paper/intermediate/wind_flags/flag_slope_gt25.csv")
NWI_FLAGS_CSV   <- file.path(REPO,
  "Scripts/applied_energy_paper/intermediate/wind_flags/flag_nwi.csv")

OUT_DIR <- file.path(REPO, "Scripts/applied_energy_paper/outputs/nlcd_wind")
dir.create(OUT_DIR, showWarnings = FALSE, recursive = TRUE)

M2_PER_ACRE      <- 4046.8564224
PROJ_CRS         <- 5070
AIRPORT_BUFFER_M <- 3000

SIZE_BIN_ORDER <- c("tiny", "small", "medium", "large", "xlarge")

log_lines <- character()
logln <- function(msg) {
  ts <- format(Sys.time(), "%H:%M:%S")
  line <- sprintf("[%s] %s", ts, msg)
  message(line)
  log_lines[[length(log_lines) + 1]] <<- line
}

# ---------------------------------------------------------------------------
# Load archived 5 km run: pct-only wind ac + non-airport flags
# ---------------------------------------------------------------------------
logln(sprintf("Loading archived 5 km pct+binary CSV: %s", ARCHIVE_5KM_CSV))
base <- readr::read_csv(ARCHIVE_5KM_CSV, show_col_types = FALSE)
logln(sprintf("  %d parcels loaded", nrow(base)))

# Keep only the columns we need; drop old airport flag + old n_flags/wind_bin
base <- base %>%
  dplyr::select(PARCEL_LID, SITE_STATE, acres, parcel_area_m2, size_bin,
                total_nlcd_area_m2,
                usable_area_nlcd_solar_m2, usable_area_nlcd_solar_ac,
                usable_area_nlcd_wind_m2,  usable_area_nlcd_wind_ac,
                flag_urban, flag_dod_sua, flag_usfws, flag_lt_1ac)

# ---------------------------------------------------------------------------
# Recompute airport 3 km flag
# ---------------------------------------------------------------------------
logln("Recomputing airport 3 km buffer flag")
parcels <- sf::st_read(PARCELS_GPKG, quiet = TRUE) %>%
  dplyr::select(PARCEL_LID) %>%
  sf::st_transform(PROJ_CRS) %>%
  dplyr::filter(PARCEL_LID %in% base$PARCEL_LID)
logln(sprintf("  %d parcel geometries", nrow(parcels)))

airports <- sf::st_read(AIRPORTS_SHP, quiet = TRUE) %>%
  sf::st_transform(PROJ_CRS) %>%
  sf::st_make_valid()
logln(sprintf("  %d airport points (raw)", nrow(airports)))

# Crop to parcel bbox padded by buffer
bb <- sf::st_bbox(parcels)
pad <- AIRPORT_BUFFER_M + 1000
bb_expanded <- bb + c(-pad, -pad, pad, pad)
bb_poly <- sf::st_as_sfc(sf::st_bbox(bb_expanded, crs = PROJ_CRS))
airports <- suppressWarnings(sf::st_crop(airports, bb_poly))
logln(sprintf("  %d airport points after CONUS bbox crop", nrow(airports)))

logln(sprintf("  buffering by %d m", AIRPORT_BUFFER_M))
ap_buf <- sf::st_buffer(airports, dist = AIRPORT_BUFFER_M)

logln("  intersecting parcels with airport 3 km buffer")
t0 <- Sys.time()
hits <- sf::st_intersects(parcels, ap_buf, sparse = TRUE)
airport_flag <- tibble(
  PARCEL_LID = parcels$PARCEL_LID,
  flag_airport = lengths(hits) > 0L
)
dt <- round(as.numeric(Sys.time() - t0, units = "secs"), 1)
logln(sprintf("  done in %.1fs; %d / %d parcels flagged by airport 3 km (%.2f%%)",
              dt, sum(airport_flag$flag_airport), nrow(airport_flag),
              100 * mean(airport_flag$flag_airport)))

# ---------------------------------------------------------------------------
# Optional: slope >25% and NWI flags — only joined if the prereq CSVs exist.
# If missing, headline output is "pre-slope/NWI" and a note is written.
# ---------------------------------------------------------------------------
maybe_load_flag <- function(path, colname) {
  if (!file.exists(path)) {
    logln(sprintf("WARN: %s not found — %s flag will be set to FALSE", path, colname))
    return(NULL)
  }
  x <- readr::read_csv(path, show_col_types = FALSE)
  if (!all(c("PARCEL_LID", colname) %in% names(x))) {
    stop(sprintf("Flag CSV %s missing columns (expected PARCEL_LID and %s)", path, colname))
  }
  logln(sprintf("  loaded %d rows from %s", nrow(x), basename(path)))
  x %>% dplyr::select(PARCEL_LID, !!colname := all_of(colname))
}

slope_flag <- maybe_load_flag(SLOPE_FLAGS_CSV, "flag_slope_gt25")
nwi_flag   <- maybe_load_flag(NWI_FLAGS_CSV,   "flag_nwi")

# ---------------------------------------------------------------------------
# Combine — join all flag tables, default missing to FALSE
# ---------------------------------------------------------------------------
out <- base %>%
  dplyr::left_join(airport_flag, by = "PARCEL_LID")

if (!is.null(slope_flag)) {
  out <- dplyr::left_join(out, slope_flag, by = "PARCEL_LID")
} else {
  out$flag_slope_gt25 <- FALSE
}
if (!is.null(nwi_flag)) {
  out <- dplyr::left_join(out, nwi_flag, by = "PARCEL_LID")
} else {
  out$flag_nwi <- FALSE
}

out <- out %>%
  dplyr::mutate(
    flag_urban       = dplyr::coalesce(flag_urban, FALSE),
    flag_dod_sua     = dplyr::coalesce(flag_dod_sua, FALSE),
    flag_usfws       = dplyr::coalesce(flag_usfws, FALSE),
    flag_lt_1ac      = dplyr::coalesce(flag_lt_1ac, FALSE),
    flag_airport     = dplyr::coalesce(flag_airport, FALSE),
    flag_slope_gt25  = dplyr::coalesce(flag_slope_gt25, FALSE),
    flag_nwi         = dplyr::coalesce(flag_nwi, FALSE),
    n_flags = as.integer(flag_lt_1ac) + as.integer(flag_urban) +
              as.integer(flag_dod_sua) + as.integer(flag_usfws) +
              as.integer(flag_airport) + as.integer(flag_slope_gt25) +
              as.integer(flag_nwi),
    usable_area_nlcd_wind_bin_m2 = ifelse(n_flags > 0, 0, usable_area_nlcd_wind_m2),
    usable_area_nlcd_wind_bin_ac = usable_area_nlcd_wind_bin_m2 / M2_PER_ACRE
  )

# ---------------------------------------------------------------------------
# Totals and sanity checks
# ---------------------------------------------------------------------------
total_pct_only_ac <- sum(out$usable_area_nlcd_wind_ac)
total_bin_ac      <- sum(out$usable_area_nlcd_wind_bin_ac)
logln(sprintf("Percentage-only total:   %.0f ac", total_pct_only_ac))
logln(sprintf("After binary exclusions: %.0f ac", total_bin_ac))
logln(sprintf("Zeroed by exclusions:    %.0f ac (%.1f%%)",
              total_pct_only_ac - total_bin_ac,
              100 * (total_pct_only_ac - total_bin_ac) / total_pct_only_ac))

flag_summary <- tibble(
  flag = c("flag_lt_1ac", "flag_urban", "flag_dod_sua", "flag_usfws",
           "flag_airport_3km", "flag_slope_gt25", "flag_nwi"),
  n_parcels_any = c(sum(out$flag_lt_1ac), sum(out$flag_urban),
                    sum(out$flag_dod_sua), sum(out$flag_usfws),
                    sum(out$flag_airport), sum(out$flag_slope_gt25),
                    sum(out$flag_nwi)),
  pct_parcels_any = round(100 * c(mean(out$flag_lt_1ac), mean(out$flag_urban),
                                  mean(out$flag_dod_sua), mean(out$flag_usfws),
                                  mean(out$flag_airport), mean(out$flag_slope_gt25),
                                  mean(out$flag_nwi)), 2)
)
logln("Per-flag parcel counts:")
print(flag_summary)

# ---------------------------------------------------------------------------
# Marginal exclusion effect (per-layer)
# ---------------------------------------------------------------------------
flag_cols <- c("flag_lt_1ac", "flag_urban", "flag_dod_sua", "flag_usfws",
               "flag_airport", "flag_slope_gt25", "flag_nwi")
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
bin_df <- out %>%
  dplyr::group_by(size_bin) %>%
  dplyr::summarise(
    n_parcels = dplyr::n(),
    n_any_flag = sum(n_flags > 0),
    pct_only_ac = round(sum(usable_area_nlcd_wind_ac), 0),
    pct_plus_bin_ac = round(sum(usable_area_nlcd_wind_bin_ac), 0),
    bin_delta_pct = round(
      100 * (sum(usable_area_nlcd_wind_bin_ac) - sum(usable_area_nlcd_wind_ac)) /
        pmax(sum(usable_area_nlcd_wind_ac), 1e-9), 2),
    .groups = "drop"
  ) %>%
  dplyr::mutate(size_bin = factor(size_bin, levels = SIZE_BIN_ORDER)) %>%
  dplyr::arrange(size_bin) %>%
  dplyr::mutate(size_bin = as.character(size_bin))

total_row <- tibble(
  size_bin = "CONUS_total",
  n_parcels = nrow(out),
  n_any_flag = sum(out$n_flags > 0),
  pct_only_ac = round(total_pct_only_ac, 0),
  pct_plus_bin_ac = round(total_bin_ac, 0),
  bin_delta_pct = round(100 * (total_bin_ac - total_pct_only_ac) / total_pct_only_ac, 2)
)
bin_df <- dplyr::bind_rows(bin_df, total_row)

# ---------------------------------------------------------------------------
# Write outputs — OVERWRITES headline files at OUT_DIR
# ---------------------------------------------------------------------------
readr::write_csv(out,       file.path(OUT_DIR, "nlcd_wind_percentage_plus_binary.csv"))
readr::write_csv(bin_df,    file.path(OUT_DIR, "nlcd_wind_percentage_plus_binary_summary.csv"))
readr::write_csv(marg_rows, file.path(OUT_DIR, "nlcd_wind_exclusion_marginal_effect.csv"))
readr::write_csv(flag_summary, file.path(OUT_DIR, "nlcd_wind_flag_counts.csv"))

logln(sprintf("Wrote %s", file.path(OUT_DIR, "nlcd_wind_percentage_plus_binary.csv")))
writeLines(unlist(log_lines), file.path(OUT_DIR, "run_log_headline_3km.txt"))

cat("\n=== Headline NLCD pct+binary (3 km airport + slope + NWI, if available) ===\n")
cat(sprintf("  Total usable: %.0f ac\n", total_bin_ac))
cat(sprintf("  Flags enabled: airport_3km=TRUE, slope=%s, nwi=%s\n",
            !is.null(slope_flag), !is.null(nwi_flag)))
