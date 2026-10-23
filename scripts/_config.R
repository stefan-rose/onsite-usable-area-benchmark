# Central path configuration for the onsite-usable-area-benchmark pipeline.
#
# Reads config.example.toml and merges a local config.toml over it if
# present; the IEDO_BASE environment variable overrides paths.base. Exposes BASE (external data root) and named
# input-path variables for every input dataset referenced by the R
# pipeline scripts.
#
# Usage from an R script (run from the repo root via Rscript):
#
#     source("scripts/_config.R")
#     parcels <- sf::st_read(PARCELS_WORKING_GPKG, quiet = TRUE)
#     out    <- file.path(OUTPUTS, "nlcd_wind", "myfile.csv")

suppressPackageStartupMessages({
  library(RcppTOML)
})

# ---------------------------------------------------------------------------
# Locate the repo root and choose the active config file
# ---------------------------------------------------------------------------
.find_repo_root <- function() {
  # Try the script directory first (works when sourced from a script run
  # via `Rscript scripts/xx_...R` from the repo root).
  cmd_args <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", cmd_args, value = TRUE)
  script_dir <- if (length(file_arg) > 0) {
    dirname(normalizePath(sub("^--file=", "", file_arg[1])))
  } else if (!is.null(sys.frame(1)$ofile)) {
    dirname(normalizePath(sys.frame(1)$ofile))
  } else {
    getwd()
  }
  # scripts/ lives at repo_root/scripts/
  parent <- dirname(script_dir)
  # Sanity check: repo root should contain pixi.toml
  if (file.exists(file.path(parent, "pixi.toml"))) return(parent)
  if (file.exists(file.path(script_dir, "pixi.toml"))) return(script_dir)
  # Fall back to cwd
  if (file.exists(file.path(getwd(), "pixi.toml"))) return(getwd())
  stop("Could not locate repo root (pixi.toml). Run from repo root via Rscript.")
}

.REPO_ROOT <- .find_repo_root()
.CONFIG_TOML <- file.path(.REPO_ROOT, "config.toml")
.CONFIG_EXAMPLE <- file.path(.REPO_ROOT, "config.example.toml")

# config.example.toml is the template; a local config.toml (gitignored) is
# merged over it, so it may hold only the keys that differ (e.g. paths.base).
.cfg <- RcppTOML::parseTOML(.CONFIG_EXAMPLE)
if (file.exists(.CONFIG_TOML)) {
  .cfg <- utils::modifyList(.cfg, RcppTOML::parseTOML(.CONFIG_TOML))
}
if (nzchar(Sys.getenv("IEDO_BASE"))) .cfg$paths$base <- Sys.getenv("IEDO_BASE")
.active_config <- if (file.exists(.CONFIG_TOML)) .CONFIG_TOML else .CONFIG_EXAMPLE

# ---------------------------------------------------------------------------
# Path resolution helpers
# ---------------------------------------------------------------------------
BASE <- path.expand(.cfg$paths$base)
if (!dir.exists(BASE)) {
  stop("Data root ", BASE, " not found. Set paths.base in config.toml or export IEDO_BASE.")
}

.base_rel <- function(p) {
  p <- path.expand(p)
  if (startsWith(p, "/") || grepl("^[A-Z]:", p)) p else file.path(BASE, p)
}

.repo_rel <- function(p) {
  p <- path.expand(p)
  if (startsWith(p, "/") || grepl("^[A-Z]:", p)) p else file.path(.REPO_ROOT, sub("^\\./", "", p))
}

# ---------------------------------------------------------------------------
# Repo-local working directories
# ---------------------------------------------------------------------------
INTERMEDIATE <- .repo_rel(.cfg$paths$intermediate)
OUTPUTS      <- .repo_rel(.cfg$paths$outputs)
FIGURES      <- .repo_rel(.cfg$paths$figures)

for (.d in c(INTERMEDIATE, OUTPUTS, FIGURES)) {
  if (!dir.exists(.d)) dir.create(.d, recursive = TRUE, showWarnings = FALSE)
}
rm(.d)

# ---------------------------------------------------------------------------
# Parcel universe inputs
# ---------------------------------------------------------------------------
PARCELS_SOURCE_GPKG  <- .base_rel(.cfg$inputs$parcels$source_gpkg)
PARCELS_WORKING_GPKG <- .base_rel(.cfg$inputs$parcels$working_gpkg)
FACILITY_CSV         <- .base_rel(.cfg$inputs$parcels$facility_csv)

# ---------------------------------------------------------------------------
# reV composite exclusion rasters (NLR)
# ---------------------------------------------------------------------------
REV_SOLAR <- list(
  open          = .base_rel(.cfg$inputs$rev_solar$open),
  reference     = .base_rel(.cfg$inputs$rev_solar$reference),
  limited       = .base_rel(.cfg$inputs$rev_solar$limited),
  parcel_joined = .base_rel(.cfg$inputs$rev_solar$parcel_joined)
)
REV_WIND <- list(
  open      = .base_rel(.cfg$inputs$rev_wind$open),
  reference = .base_rel(.cfg$inputs$rev_wind$reference),
  limited   = .base_rel(.cfg$inputs$rev_wind$limited)
)

# ---------------------------------------------------------------------------
# NLCD
# ---------------------------------------------------------------------------
NLCD_GEE_DIR <- .base_rel(.cfg$inputs$nlcd$gee_extract_dir)

# ---------------------------------------------------------------------------
# Wind binary exclusion layers
# ---------------------------------------------------------------------------
WIND_BINARY <- list(
  airports         = .base_rel(.cfg$inputs$wind_binary$airports_hifld),
  dod_airspace     = .base_rel(.cfg$inputs$wind_binary$dod_airspace),
  critical_habitat = .base_rel(.cfg$inputs$wind_binary$critical_habitat),
  urban_areas      = .base_rel(.cfg$inputs$wind_binary$urban_areas),
  nwi_flags        = .base_rel(.cfg$inputs$wind_binary$nwi_flags),
  slope_flags      = .base_rel(.cfg$inputs$wind_binary$slope_flags)
)

# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------
CRS <- .cfg$projection$crs
