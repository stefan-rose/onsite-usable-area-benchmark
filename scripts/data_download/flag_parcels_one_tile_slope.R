# flag_parcels_one_tile_slope.R
#
# Invoked per-tile by download_and_flag_slope.sh.
#
# Args:
#   1. Tile id (e.g., "n40w080") — for logging
#   2. Path to slope >= threshold mask tif (Byte, 1 = slope>=25%, 0 = otherwise,
#      255 = nodata) — in the original DEM CRS (EPSG:4269 / NAD83 geographic)
#   3. Output CSV path for this tile's parcel flags
#
# Output CSV contains only parcels with flag_slope_gt25 == TRUE for this tile
# (plus header). The final merge step in the shell script combines across
# tiles using "any tile sees a hit" logic.

suppressPackageStartupMessages({
  library(sf)
  library(terra)
  library(dplyr)
  library(readr)
  library(tibble)
  library(exactextractr)
})
# Geographic queries on invalid parcel geoms are common (self-intersections).
# Use planar/GEOS semantics for this script (matches 08_nlcd_wind_binary_exclusions.R).
sf::sf_use_s2(FALSE)

args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 3)
TILE     <- args[[1]]
MASK_TIF <- args[[2]]
OUT_CSV  <- args[[3]]

REPO <- "/Users/rose501/Library/CloudStorage/OneDrive-PNNL/Desktop/IEDO"
PARCELS_GPKG <- file.path(REPO,
  "Scripts/applied_energy_paper/intermediate/parcels_conus_2026_04_23.gpkg")

log <- function(msg) cat(sprintf("  [slope/%s] %s\n", TILE, msg))

t_all <- Sys.time()

# ---------------------------------------------------------------------------
# Load mask and its bbox in WGS84 (geographic)
# ---------------------------------------------------------------------------
r <- terra::rast(MASK_TIF)
# Tile size / CRS sanity
log(sprintf("mask raster: %d x %d, CRS %s",
            terra::ncol(r), terra::nrow(r),
            strsplit(terra::crs(r, proj = TRUE), " ")[[1]][1]))
ev <- unname(as.vector(terra::ext(r)))  # drop names to avoid xmin.xmin nesting in c()
# Expand tile bbox slightly to catch parcels straddling edges
bb_poly_geo <- sf::st_as_sfc(sf::st_bbox(c(xmin = ev[1] - 0.01,
                                            xmax = ev[2] + 0.01,
                                            ymin = ev[3] - 0.01,
                                            ymax = ev[4] + 0.01),
                                          crs = 4326))

# ---------------------------------------------------------------------------
# Load parcels overlapping tile (in WGS84 for filtering, then to raster CRS)
# ---------------------------------------------------------------------------
parcels_all <- sf::st_read(PARCELS_GPKG, quiet = TRUE)
# Fast bbox-pre-filter in the original CRS before transform — avoids running
# st_transform over the entire CONUS universe and sidesteps invalid-geom crashes.
parcels_orig_crs <- sf::st_crs(parcels_all)
bb_poly_src <- sf::st_transform(bb_poly_geo, parcels_orig_crs)
bb_src <- sf::st_bbox(bb_poly_src)
ctr <- suppressWarnings(sf::st_coordinates(sf::st_centroid(sf::st_geometry(parcels_all))))
in_bb <- !is.na(ctr[,1]) & !is.na(ctr[,2]) &
         ctr[,1] >= bb_src["xmin"] & ctr[,1] <= bb_src["xmax"] &
         ctr[,2] >= bb_src["ymin"] & ctr[,2] <= bb_src["ymax"]
parcels <- parcels_all[in_bb, c("PARCEL_LID")]
log(sprintf("parcels overlapping tile bbox (centroid test): %d / %d",
            nrow(parcels), nrow(parcels_all)))

if (nrow(parcels) == 0) {
  # Empty output: header only
  readr::write_csv(tibble::tibble(PARCEL_LID = character(), flag_slope_gt25 = logical()),
                   OUT_CSV)
  log("no parcels in tile — wrote empty flag file")
  quit(save = "no")
}

# Repair invalid geometries before the reprojection.
parcels <- sf::st_make_valid(parcels)
# Reproject parcels into raster CRS for exact_extract
parcels <- sf::st_transform(parcels, terra::crs(r))

# ---------------------------------------------------------------------------
# exact_extract: fraction of parcel cells with mask == 1.
# "any cell >=25% slope" threshold: flag = TRUE iff max cell value == 1 in the parcel.
# ---------------------------------------------------------------------------
log("exact_extract over parcels")
t0 <- Sys.time()
# Use 'max' summarization: mask is binary {0,1,NA}, so max > 0 iff any hit.
# exact_extract supports 'max' out of the box and handles NA.
vals <- exactextractr::exact_extract(r, parcels, "max", progress = FALSE)
dt <- round(as.numeric(Sys.time() - t0, units = "secs"), 1)
log(sprintf("  done in %ss", dt))

flag <- !is.na(vals) & vals > 0
hits <- tibble::tibble(
  PARCEL_LID = parcels$PARCEL_LID,
  flag_slope_gt25 = flag
) %>% dplyr::filter(flag_slope_gt25)  # Only write TRUE rows; merge handles FALSEs.

readr::write_csv(hits, OUT_CSV)
log(sprintf("parcels flagged by this tile: %d; wrote %s", nrow(hits), OUT_CSV))
log(sprintf("total time: %.1fs", as.numeric(Sys.time() - t_all, units = "secs")))
