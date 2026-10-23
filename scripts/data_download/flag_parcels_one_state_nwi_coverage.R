# flag_parcels_one_state_nwi_coverage.R
#
# Variant of flag_parcels_one_state_nwi_raster.R that computes NWI coverage
# FRACTION per parcel, not just a binary flag. Used for the 2026-04-30
# sample-state diagnostic: are NWI-flagged parcels dominated by wetland
# (like the UT salt-flat case) or are they edge-grazed by small wetland
# polygons (binary-amplification concern)?
#
# Args: same as flag_parcels_one_state_nwi_raster.R.
# Output: CSV with (PARCEL_LID, nwi_coverage_frac, n_cells_nwi, parcel_cells)
#
# Method differs from the flag version ONLY at the exact_extract step:
#   - fun = "sum"          gives total NWI cells per parcel (weighted by
#                          cell-parcel fractional overlap)
#   - fun = "count"        gives total parcel cells (also fractional)
#   - coverage_frac = sum / count (in [0, 1])
#
# Rasterize mode is identical (cell-centroid, no -at). See the flag script
# header for validation notes.

suppressPackageStartupMessages({
  library(sf); library(terra); library(exactextractr)
  library(dplyr); library(readr); library(tibble)
})

args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 3)
STATE   <- args[[1]]
GPKG    <- args[[2]]
OUT_CSV <- args[[3]]

REPO <- Sys.getenv("IEDO_BASE")
if (!nzchar(REPO)) stop("export IEDO_BASE=/path/to/IEDO (data root)")
PARCELS_GPKG <- file.path(REPO,
  "Scripts/applied_energy_paper/intermediate/parcels_conus_2026_04_23.gpkg")
TMP_DIR <- file.path(REPO, "Data/wind_exclusions/NWI/_tmp")
dir.create(TMP_DIR, showWarnings = FALSE, recursive = TRUE)

PROJ_CRS <- 5070
RES_M    <- 30
PAD_M    <- 10000

log <- function(msg) cat(sprintf("  [cov/%s] %s\n", STATE, msg))
t_all <- Sys.time()

# ---------------------------------------------------------------------------
# Parcels
# ---------------------------------------------------------------------------
log(sprintf("Loading parcels from %s", basename(PARCELS_GPKG)))
parcels_all <- sf::st_read(PARCELS_GPKG, quiet = TRUE) %>%
  sf::st_transform(PROJ_CRS)

state_parcels <- parcels_all %>% dplyr::filter(SITE_STATE == STATE)
if (nrow(state_parcels) == 0) {
  log("No parcels — writing empty set")
  readr::write_csv(tibble::tibble(PARCEL_LID=character(), nwi_coverage_frac=numeric(),
                                  n_cells_nwi=numeric(), parcel_cells=numeric()), OUT_CSV)
  quit(save = "no")
}

bb <- sf::st_bbox(state_parcels)
bb_expanded <- bb + c(-PAD_M, -PAD_M, PAD_M, PAD_M)
bb_poly <- sf::st_as_sfc(sf::st_bbox(bb_expanded, crs = PROJ_CRS))

parcels <- parcels_all[sf::st_intersects(parcels_all, bb_poly, sparse=FALSE)[,1], ] %>%
  dplyr::select(PARCEL_LID)
log(sprintf("%d state parcels; %d in %d km pad", nrow(state_parcels), nrow(parcels), PAD_M/1000))

# ---------------------------------------------------------------------------
# NWI layer detection (same logic as flag script)
# ---------------------------------------------------------------------------
nwi_info <- sf::st_layers(GPKG)
candidates <- nwi_info$name
drop <- grepl("Historic|Project|Riparian|Metadata", candidates, ignore.case=TRUE)
candidates <- candidates[!drop]
matches <- candidates[grepl("wetland", candidates, ignore.case=TRUE)]
if (length(matches) > 1) {
  fcounts <- nwi_info$features[match(matches, nwi_info$name)]
  matches <- matches[which.max(fcounts)]
}
LYR <- matches[[1]]
log(sprintf("NWI layer: %s", LYR))

# ---------------------------------------------------------------------------
# Rasterize (two-step: native-CRS rasterize + gdalwarp to EPSG:5070 30 m)
# ---------------------------------------------------------------------------
rast_native <- file.path(TMP_DIR, sprintf("%s_cov_native.tif", STATE))
rast_path   <- file.path(TMP_DIR, sprintf("%s_cov_30m.tif",    STATE))

xmin <- floor  (bb_expanded[["xmin"]] / RES_M) * RES_M
ymin <- floor  (bb_expanded[["ymin"]] / RES_M) * RES_M
xmax <- ceiling(bb_expanded[["xmax"]] / RES_M) * RES_M
ymax <- ceiling(bb_expanded[["ymax"]] / RES_M) * RES_M

layer_idx <- which(nwi_info$name == LYR)[1]
nwi_crs <- nwi_info$crs[[layer_idx]]
if (is.null(nwi_crs) || is.na(sf::st_crs(nwi_crs)$epsg)) {
  tmp <- sf::st_read(GPKG, layer=LYR,
                     query=sprintf("SELECT * FROM \"%s\" LIMIT 1", LYR), quiet=TRUE)
  nwi_crs <- sf::st_crs(tmp)
}
bb_native <- sf::st_transform(bb_poly, nwi_crs)
bb_n <- sf::st_bbox(bb_native)
native_crs_obj <- sf::st_crs(nwi_crs)
if (is.na(native_crs_obj$IsGeographic)) native_crs_obj$IsGeographic <- FALSE
native_res <- if (isTRUE(native_crs_obj$IsGeographic)) RES_M/111320 else RES_M

cmd1 <- sprintf(
  paste0("gdal_rasterize -burn 1 -init 0 -ot Byte ",
         "-tr %.8f %.8f -te %.8f %.8f %.8f %.8f -l %s ",
         "-co COMPRESS=LZW -co TILED=YES -co BIGTIFF=IF_SAFER -q %s %s"),
  native_res, native_res,
  bb_n[["xmin"]], bb_n[["ymin"]], bb_n[["xmax"]], bb_n[["ymax"]],
  shQuote(LYR), shQuote(GPKG), shQuote(rast_native))

log("Step 1/2: gdal_rasterize …")
t0 <- Sys.time()
if (system(cmd1) != 0L) stop("gdal_rasterize failed for ", STATE)
log(sprintf("  %.1f MB in %.1fs", file.info(rast_native)$size/1e6,
            as.numeric(Sys.time()-t0, units="secs")))

cmd2 <- sprintf(
  paste0("gdalwarp -overwrite -t_srs EPSG:%d -tr %d %d -te %.0f %.0f %.0f %.0f ",
         "-r near -ot Byte -dstnodata 255 ",
         "-co COMPRESS=LZW -co TILED=YES -co BIGTIFF=IF_SAFER -q %s %s"),
  PROJ_CRS, RES_M, RES_M, xmin, ymin, xmax, ymax,
  shQuote(rast_native), shQuote(rast_path))

log("Step 2/2: gdalwarp …")
t0 <- Sys.time()
if (system(cmd2) != 0L) stop("gdalwarp failed for ", STATE)
log(sprintf("  %.1f MB in %.1fs", file.info(rast_path)$size/1e6,
            as.numeric(Sys.time()-t0, units="secs")))
unlink(rast_native)

# ---------------------------------------------------------------------------
# exact_extract: sum + count to get coverage fraction
# ---------------------------------------------------------------------------
r <- terra::rast(rast_path)
log("exact_extract(sum, count) …")
t0 <- Sys.time()
both <- exactextractr::exact_extract(r, parcels, fun=c("sum","count"), progress=FALSE)
dt <- as.numeric(Sys.time()-t0, units="secs")
# `both` is a data.frame with columns sum, count
n_cells_nwi  <- both$sum
parcel_cells <- both$count
frac <- ifelse(parcel_cells > 0, n_cells_nwi/parcel_cells, NA_real_)

log(sprintf("  done in %.1fs; median coverage = %.3f; mean = %.3f",
            dt, median(frac, na.rm=TRUE), mean(frac, na.rm=TRUE)))
log(sprintf("  %% parcels with coverage > 0:   %.2f", 100*mean(frac > 0, na.rm=TRUE)))
log(sprintf("  %% parcels with coverage > 5%%: %.2f",  100*mean(frac > 0.05, na.rm=TRUE)))
log(sprintf("  %% parcels with coverage > 50%%:%.2f",  100*mean(frac > 0.50, na.rm=TRUE)))

out <- tibble::tibble(PARCEL_LID = parcels$PARCEL_LID,
                      nwi_coverage_frac = frac,
                      n_cells_nwi = n_cells_nwi,
                      parcel_cells = parcel_cells)
readr::write_csv(out, OUT_CSV)
log(sprintf("Wrote %s", OUT_CSV))

unlink(rast_path)
log(sprintf("Total %.1fs", as.numeric(Sys.time()-t_all, units="secs")))
