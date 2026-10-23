# flag_parcels_one_state_nwi_raster.R
#
# Rasterize-based alternative to flag_parcels_one_state_nwi.R.
#
# Motivation: MN (~2.66M wetland features) wedges sf::st_intersects in heavy
# memory pressure + swapping. Rasterizing to a 30 m binary mask in EPSG:5070
# and running exact_extract(max) is fast, disk-friendly, and scales linearly.
#
# Args:
#   1. State postal code (e.g., "MN")
#   2. Path to NWI state GeoPackage
#   3. Output CSV path (PARCEL_LID, flag_nwi)
#
# Method:
#   1. Load parcels for this state + 10 km pad; project to EPSG:5070.
#   2. Auto-detect the main Wetlands polygon layer (case-insensitive match,
#      excludes Historic/Project/Riparian/Metadata sidecars, picks largest
#      if ties).
#   3. gdal_rasterize the NWI layer to a Byte (0/1) mask at 30 m in
#      EPSG:5070, bounded by the padded parcel bbox. Tile-compressed LZW.
#   4. exact_extract(max) gives 1 iff any rasterized wetland cell touches
#      the parcel polygon.
#   5. Delete the raster.
#
# Notes:
#   - Cell-centroid rasterization (no -at / ALL_TOUCHED). A 30 m cell is 1
#     iff a wetland polygon covers its centroid. Tested on DC (883 parcels):
#     97.5% agreement with vector st_intersects, balanced +/- 2.5% flag-count
#     difference (9 raster-only, 13 vector-only). This cell-centroid mode was
#     preferred over ALL_TOUCHED (-at) because -at produced a systematic
#     one-sided over-flag bias (+21 / 0 in the same DC test).
#   - "flag_nwi = TRUE" means "at least one 30 m cell whose centroid is
#     covered by a wetland polygon overlaps the parcel polygon (via
#     exact_extract fractional coverage > 0)".

suppressPackageStartupMessages({
  library(sf)
  library(terra)
  library(exactextractr)
  library(dplyr)
  library(readr)
  library(tibble)
})

args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 3)
STATE    <- args[[1]]
GPKG     <- args[[2]]
OUT_CSV  <- args[[3]]

REPO <- Sys.getenv("IEDO_BASE")
if (!nzchar(REPO)) stop("export IEDO_BASE=/path/to/IEDO (data root)")
PARCELS_GPKG <- file.path(REPO,
  "Scripts/applied_energy_paper/intermediate/parcels_conus_2026_04_23.gpkg")
TMP_DIR <- file.path(REPO, "Data/wind_exclusions/NWI/_tmp")
dir.create(TMP_DIR, showWarnings = FALSE, recursive = TRUE)

PROJ_CRS <- 5070
RES_M    <- 30    # raster resolution in meters
PAD_M    <- 10000 # 10 km parcel bbox pad

log <- function(msg) cat(sprintf("  [flag/%s] %s\n", STATE, msg))

t_all <- Sys.time()

# ---------------------------------------------------------------------------
# Load parcels for this state + adjacent parcels within 10 km pad
# ---------------------------------------------------------------------------
log(sprintf("Loading parcels from %s", basename(PARCELS_GPKG)))
parcels_all <- sf::st_read(PARCELS_GPKG, quiet = TRUE) %>%
  sf::st_transform(PROJ_CRS)

state_parcels <- parcels_all %>% dplyr::filter(SITE_STATE == STATE)
if (nrow(state_parcels) == 0) {
  log(sprintf("No parcels with SITE_STATE == %s — writing empty flag set", STATE))
  readr::write_csv(tibble::tibble(PARCEL_LID = character(), flag_nwi = logical()), OUT_CSV)
  quit(save = "no")
}

bb <- sf::st_bbox(state_parcels)
bb_expanded <- bb + c(-PAD_M, -PAD_M, PAD_M, PAD_M)
bb_poly <- sf::st_as_sfc(sf::st_bbox(bb_expanded, crs = PROJ_CRS))

parcels <- parcels_all[sf::st_intersects(parcels_all, bb_poly, sparse = FALSE)[,1], ] %>%
  dplyr::select(PARCEL_LID)
log(sprintf("%d state parcels; %d parcels within %d km pad (intersect set)",
            nrow(state_parcels), nrow(parcels), PAD_M / 1000))

# ---------------------------------------------------------------------------
# Detect NWI wetlands layer name (same logic as vector version)
# ---------------------------------------------------------------------------
nwi_info <- sf::st_layers(GPKG)
candidates <- nwi_info$name
drop <- grepl("Historic|Project|Riparian|Metadata", candidates, ignore.case = TRUE)
candidates <- candidates[!drop]
matches <- candidates[grepl("wetland", candidates, ignore.case = TRUE)]
if (length(matches) == 0) {
  cat("Available layers:\n"); print(nwi_info)
  stop("No Wetlands-like layer found in GPKG: ", GPKG)
}
if (length(matches) > 1) {
  fcounts <- nwi_info$features[match(matches, nwi_info$name)]
  matches <- matches[which.max(fcounts)]
}
LYR <- matches[[1]]
log(sprintf("NWI layer: %s", LYR))

# ---------------------------------------------------------------------------
# Rasterize the NWI layer to a 30 m binary mask.
#
# gdal_rasterize cannot reproject on the fly (-t_srs is not supported; only
# -a_srs, which assigns without transforming). Approach:
#   1. Detect the NWI layer's native CRS.
#   2. Compute the padded parcel bbox in the NWI native CRS.
#   3. Rasterize in native CRS, snapped to ~RES_M in EPSG:5070 equivalent.
#   4. gdalwarp the raster to EPSG:5070 at RES_M using nearest-neighbor
#      (preserves 0/1 semantics).
#
# Why this is still fast: warping a ~Byte raster with LZW compression is
# much cheaper than reprojecting millions of polygon vertices, and happens
# at raster resolution (not at vector feature count).
# ---------------------------------------------------------------------------
rast_native   <- file.path(TMP_DIR, sprintf("%s_nwi_mask_native.tif", STATE))
rast_path     <- file.path(TMP_DIR, sprintf("%s_nwi_mask_30m.tif",   STATE))

xmin_5070 <- bb_expanded[["xmin"]]; ymin_5070 <- bb_expanded[["ymin"]]
xmax_5070 <- bb_expanded[["xmax"]]; ymax_5070 <- bb_expanded[["ymax"]]

# Snap to RES_M in 5070 space
xmin_5070 <- floor(xmin_5070   / RES_M) * RES_M
ymin_5070 <- floor(ymin_5070   / RES_M) * RES_M
xmax_5070 <- ceiling(xmax_5070 / RES_M) * RES_M
ymax_5070 <- ceiling(ymax_5070 / RES_M) * RES_M

n_cells <- ((xmax_5070 - xmin_5070) / RES_M) * ((ymax_5070 - ymin_5070) / RES_M)
log(sprintf("Final raster extent (EPSG:5070): %.0f x %.0f m at %d m -> %.1fM cells",
            xmax_5070 - xmin_5070, ymax_5070 - ymin_5070, RES_M, n_cells / 1e6))

# Get NWI native CRS + transform the padded bbox there
layer_idx <- which(nwi_info$name == LYR)[1]
nwi_crs   <- nwi_info$crs[[layer_idx]]
if (is.null(nwi_crs) || is.na(sf::st_crs(nwi_crs)$epsg)) {
  # Fall back to using the feature-level CRS from a tiny read
  tmp <- sf::st_read(GPKG, layer = LYR, query = sprintf("SELECT * FROM \"%s\" LIMIT 1", LYR),
                     quiet = TRUE)
  nwi_crs <- sf::st_crs(tmp)
}
bb_native <- sf::st_transform(bb_poly, nwi_crs)
bb_n <- sf::st_bbox(bb_native)
# Pick a native-CRS resolution close to RES_M (works fine for geographic CRS
# because we only rasterize here; final resolution is enforced by gdalwarp).
native_crs_obj <- sf::st_crs(nwi_crs)
if (is.na(native_crs_obj$IsGeographic)) native_crs_obj$IsGeographic <- FALSE
if (isTRUE(native_crs_obj$IsGeographic)) {
  # Degrees; use ~RES_M / 111320 m/deg
  native_res <- RES_M / 111320
} else {
  native_res <- RES_M
}

# Step 1: rasterize in native CRS
cmd1 <- sprintf(
  paste0(
    "gdal_rasterize -burn 1 -init 0 -ot Byte ",
    "-tr %.8f %.8f ",
    "-te %.8f %.8f %.8f %.8f ",
    "-l %s ",
    "-co COMPRESS=LZW -co TILED=YES -co BIGTIFF=IF_SAFER ",
    "-q ",
    "%s %s"),
  native_res, native_res,
  bb_n[["xmin"]], bb_n[["ymin"]], bb_n[["xmax"]], bb_n[["ymax"]],
  shQuote(LYR),
  shQuote(GPKG),
  shQuote(rast_native)
)

log("Step 1/2: gdal_rasterize in NWI native CRS …")
t0 <- Sys.time()
rc <- system(cmd1, intern = FALSE, ignore.stdout = FALSE, ignore.stderr = FALSE)
dt <- as.numeric(Sys.time() - t0, units = "secs")
if (rc != 0L) {
  log(sprintf("gdal_rasterize failed (rc=%d) after %.1fs", rc, dt))
  stop("gdal_rasterize failed for ", STATE)
}
fsize_mb_native <- file.info(rast_native)$size / 1e6
log(sprintf("  native raster %.1f MB in %.1fs", fsize_mb_native, dt))

# Step 2: gdalwarp to EPSG:5070 at RES_M
cmd2 <- sprintf(
  paste0(
    "gdalwarp -overwrite ",
    "-t_srs EPSG:%d ",
    "-tr %d %d -te %.0f %.0f %.0f %.0f ",
    "-r near ",
    "-ot Byte -dstnodata 255 ",
    "-co COMPRESS=LZW -co TILED=YES -co BIGTIFF=IF_SAFER ",
    "-q ",
    "%s %s"),
  PROJ_CRS,
  RES_M, RES_M, xmin_5070, ymin_5070, xmax_5070, ymax_5070,
  shQuote(rast_native),
  shQuote(rast_path)
)

log("Step 2/2: gdalwarp to EPSG:5070 …")
t0 <- Sys.time()
rc <- system(cmd2, intern = FALSE, ignore.stdout = FALSE, ignore.stderr = FALSE)
dt <- as.numeric(Sys.time() - t0, units = "secs")
if (rc != 0L) {
  log(sprintf("gdalwarp failed (rc=%d) after %.1fs", rc, dt))
  stop("gdalwarp failed for ", STATE)
}
fsize_mb <- file.info(rast_path)$size / 1e6
log(sprintf("  final raster %.1f MB in %.1fs", fsize_mb, dt))
unlink(rast_native)  # drop native-CRS intermediate

# ---------------------------------------------------------------------------
# exact_extract: max value per parcel > 0 means at least one NWI cell
# ---------------------------------------------------------------------------
r <- terra::rast(rast_path)
log("Running exact_extract(max) …")
t0 <- Sys.time()
mx <- exactextractr::exact_extract(r, parcels, fun = "max", progress = FALSE)
dt <- as.numeric(Sys.time() - t0, units = "secs")

flag <- !is.na(mx) & mx > 0
log(sprintf("  done in %.1fs; %d / %d parcels flagged (%.2f%%)",
            dt, sum(flag), length(flag), 100 * mean(flag)))

out <- tibble::tibble(PARCEL_LID = parcels$PARCEL_LID, flag_nwi = flag)
readr::write_csv(out, OUT_CSV)
log(sprintf("Wrote %s", OUT_CSV))

# ---------------------------------------------------------------------------
# Clean up raster (NWI GPKG + unzip dir handled by bash driver)
# ---------------------------------------------------------------------------
unlink(rast_path)
log(sprintf("Total time: %.1fs",
            as.numeric(Sys.time() - t_all, units = "secs")))
