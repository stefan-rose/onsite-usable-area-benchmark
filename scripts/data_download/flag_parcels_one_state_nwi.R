# flag_parcels_one_state_nwi.R
#
# Invoked per-state by download_and_flag_nwi.sh.
#
# Args:
#   1. State postal code (e.g., "TX")
#   2. Path to NWI state GeoPackage (contains Wetlands layer)
#   3. Output CSV path (PARCEL_LID, flag_nwi)
#
# Logic:
#   - Parcel subset: parcels in this state + parcels whose bbox intersects
#     the state bbox (to catch state-adjacent parcels, since NWI state
#     downloads extend beyond state borders by design).
#   - Project to EPSG:5070 (CONUS Albers).
#   - Valid NWI polygons only (st_make_valid).
#   - Any parcel intersecting any NWI polygon -> flag_nwi = TRUE.
#
# Note on wetland types: NWI "Wetlands" layer includes deepwater habitats
# (E1UB, L1UB types). Lopez 2023 treats these equivalently to wetlands for
# wind siting exclusion purposes. We use ALL NWI polygons — no type filter.

suppressPackageStartupMessages({
  library(sf)
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

PROJ_CRS <- 5070

log <- function(msg) cat(sprintf("  [flag/%s] %s\n", STATE, msg))

t_all <- Sys.time()

# ---------------------------------------------------------------------------
# Load parcels for this state + adjacent (bbox-based)
# ---------------------------------------------------------------------------
log(sprintf("Loading parcels from %s", basename(PARCELS_GPKG)))
parcels_all <- sf::st_read(PARCELS_GPKG, quiet = TRUE) %>%
  sf::st_transform(PROJ_CRS)

# Quickly pull state parcels to establish bbox
state_parcels <- parcels_all %>% dplyr::filter(SITE_STATE == STATE)
if (nrow(state_parcels) == 0) {
  log(sprintf("No parcels with SITE_STATE == %s — writing empty flag set", STATE))
  readr::write_csv(tibble::tibble(PARCEL_LID = character(), flag_nwi = logical()), OUT_CSV)
  quit(save = "no")
}

# Expand by small pad so we also evaluate adjacent out-of-state parcels that
# fall inside the NWI coverage extent (NWI state downloads include adjacent
# quad coverage beyond state lines).
bb <- sf::st_bbox(state_parcels)
pad <- 10000  # 10 km pad
bb_expanded <- bb + c(-pad, -pad, pad, pad)
bb_poly <- sf::st_as_sfc(sf::st_bbox(bb_expanded, crs = PROJ_CRS))

parcels <- parcels_all[sf::st_intersects(parcels_all, bb_poly, sparse = FALSE)[,1], ] %>%
  dplyr::select(PARCEL_LID)
log(sprintf("%d state parcels; %d parcels within %d km pad (intersect set)",
            nrow(state_parcels), nrow(parcels), pad / 1000))

# ---------------------------------------------------------------------------
# Load NWI wetland polygons, crop to parcel bbox to cut geometry count
# ---------------------------------------------------------------------------
layers <- sf::st_layers(GPKG)
# Layer-name conventions vary by state and vintage:
#   "AL_Wetlands", "AR_wetlands", "Wetlands", "<state>_wetlands" ...
# Pick the main Wetlands polygon layer, excluding Historic/Project/Riparian/
# Metadata sidecars and the state-boundary polygon (which uses the state's
# full name, e.g. "Arkansas", and has only 1 feature).
candidates <- layers$name
# Drop obvious sidecars (case-insensitive)
drop <- grepl("Historic|Project|Riparian|Metadata", candidates, ignore.case = TRUE)
candidates <- candidates[!drop]
# Keep only names that match 'wetland' (case-insensitive, optional suffix s)
matches <- candidates[grepl("wetland", candidates, ignore.case = TRUE)]
if (length(matches) == 0) {
  cat("Available layers:\n"); print(layers)
  stop("No Wetlands-like layer found in GPKG: ", GPKG)
}
# If multiple still match, prefer the one with the largest feature count
if (length(matches) > 1) {
  fcounts <- layers$features[match(matches, layers$name)]
  matches <- matches[which.max(fcounts)]
}
LYR <- matches[[1]]
log(sprintf("NWI layer: %s", LYR))

# Use GDAL-level spatial filtering at read time: build a WKT polygon in the
# NWI layer's native CRS (NAD83 Albers or similar) and pass as wkt_filter.
# This lets GPKG's internal rtree skip loading features outside the bbox
# instead of loading ~0.6-5M polygons only to st_crop them.
# Step 1: discover the NWI CRS without loading geometries.
nwi_info <- sf::st_layers(GPKG)
nwi_crs <- nwi_info$crs[[ which(nwi_info$name == LYR)[1] ]]
# Step 2: build bbox polygon in PROJ_CRS then reproject to nwi_crs.
bb_in_nwi <- sf::st_transform(bb_poly, nwi_crs)
wkt <- sf::st_as_text(sf::st_geometry(bb_in_nwi)[[1]])

t0 <- Sys.time()
nwi <- sf::st_read(GPKG, layer = LYR, wkt_filter = wkt, quiet = TRUE)
log(sprintf("  %d NWI features loaded via wkt_filter (%.1fs)",
            nrow(nwi), as.numeric(Sys.time() - t0, units = "secs")))

nwi <- sf::st_transform(nwi, PROJ_CRS)
log(sprintf("  %d NWI features after reprojection (no additional crop needed)", nrow(nwi)))
if (nrow(nwi) == 0) {
  log("No NWI features in parcel bbox — all flags FALSE for this state")
  out <- tibble::tibble(PARCEL_LID = parcels$PARCEL_LID, flag_nwi = FALSE)
  readr::write_csv(out, OUT_CSV)
  log(sprintf("Wrote %s", OUT_CSV))
  quit(save = "no")
}

nwi <- sf::st_make_valid(nwi)

# ---------------------------------------------------------------------------
# Intersect parcels with NWI polygons
# ---------------------------------------------------------------------------
t0 <- Sys.time()
log("Running st_intersects …")
hits <- sf::st_intersects(parcels, nwi, sparse = TRUE)
flag <- lengths(hits) > 0L
log(sprintf("  done in %.1fs; %d / %d parcels flagged (%.2f%%)",
            as.numeric(Sys.time() - t0, units = "secs"),
            sum(flag), length(flag), 100 * mean(flag)))

out <- tibble::tibble(PARCEL_LID = parcels$PARCEL_LID, flag_nwi = flag)
readr::write_csv(out, OUT_CSV)
log(sprintf("Wrote %s", OUT_CSV))
log(sprintf("Total time: %.1fs",
            as.numeric(Sys.time() - t_all, units = "secs")))
