# ---------------------------------------------------------------------------
# 11_parcel_area_floor_sensitivity.R
#
# Purpose: sensitivity of the 5-layer NLCD binary wind total to the parcel-area
# floor, in response to reviewer comment R9 (Applied Energy round 1).
#
# Motivation. The published 5-layer binary set zeroes parcels below 1 acre and
# justifies that floor as a utility-scale siting minimum. The reV wind
# composites the paper benchmarks against are parameterized at 115 m hub /
# 170 m rotor. A 1-acre parcel (63.6 m square) is smaller than that rotor
# sweep, so the floor is a distributed-scale threshold, not a utility-scale
# one. This script quantifies how much of the reported NLCD-above-reV wind gap
# is attributable to the choice of floor.
#
# Thresholds swept:
#   1   ac  published headline
#   5   ac  distributed / light-commercial multi-turbine
#   20  ac  ~single-turbine pad plus minimal setback
#   107 ac  5D x 3D array envelope for D = 170 m
#           (850 m x 510 m = 433,500 m^2 = 107.12 ac)
#
# No geospatial re-run is required: the per-parcel binary-exclusion output
# carries parcel acreage, percentage-only wind acreage, and each binary flag
# separably, so the 5-layer total at any floor T is an exact recomputation:
#   sum(usable_area_nlcd_wind_ac) over parcels where
#     !(flag_urban | flag_dod_sua | flag_usfws | flag_airport) & acres >= T
#
# Validation: T = 1 must reproduce the published 1.309 M ac headline.
# ---------------------------------------------------------------------------

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
})

base_dir <- "/Users/rose501/Library/CloudStorage/OneDrive-PNNL/Desktop/IEDO/Scripts/applied_energy_paper"
in_csv   <- file.path(base_dir, "outputs/nlcd_wind/nlcd_wind_percentage_plus_binary.csv")
out_dir  <- file.path(base_dir, "outputs/nlcd_wind/parcel_area_floor_sensitivity")
dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)

# Published anchors used for validation / framing (see 04_results.tex)
PUB_5LAYER_MAC  <- 1.309   # 5-layer binary NLCD wind, 3 km airport buffer
PUB_PCTONLY_AC  <- 2721060 # NLCD percentage-only wind
REV_REF_WIND_AC <- 794000  # reV Reference wind

# 5D x 3D envelope for the 170 m rotor the reV wind composites model
D_M            <- 170
ENVELOPE_M2    <- (5 * D_M) * (3 * D_M)
ENVELOPE_AC    <- ENVELOPE_M2 / 4046.86
cat(sprintf("5D x 3D envelope for D = %d m: %.0f m x %.0f m = %s m2 = %.2f ac\n",
            D_M, 5 * D_M, 3 * D_M, format(ENVELOPE_M2, big.mark = ","), ENVELOPE_AC))

pw <- read_csv(in_csv, show_col_types = FALSE, progress = FALSE) |>
  select(PARCEL_LID, acres, size_bin,
         usable_area_nlcd_wind_ac,
         flag_urban, flag_dod_sua, flag_usfws, flag_airport,
         flag_lt_1ac)

cat(sprintf("\nParcels read: %s\n", format(nrow(pw), big.mark = ",")))
cat(sprintf("Percentage-only wind total: %s ac (published %s ac)\n",
            format(round(sum(pw$usable_area_nlcd_wind_ac)), big.mark = ","),
            format(PUB_PCTONLY_AC, big.mark = ",")))

# --- Sanity check: flag_lt_1ac is exactly acres < 1 -------------------------
mismatch <- sum(pw$flag_lt_1ac != (pw$acres < 1))
cat(sprintf("flag_lt_1ac disagrees with (acres < 1) on %d parcels\n", mismatch))

# --- The four non-area 5-layer gates, held fixed ----------------------------
pw <- pw |>
  mutate(gated_nonarea = flag_urban | flag_dod_sua | flag_usfws | flag_airport)

THRESHOLDS <- c(1, 5, 20, ENVELOPE_AC)
LABELS     <- c("1", "5", "20", "107")

sweep <- lapply(seq_along(THRESHOLDS), function(i) {
  T_ac <- THRESHOLDS[i]
  keep <- !pw$gated_nonarea & pw$acres >= T_ac
  tibble(
    floor_label    = LABELS[i],
    floor_ac       = T_ac,
    n_below_floor  = sum(pw$acres < T_ac),
    pct_below      = 100 * sum(pw$acres < T_ac) / nrow(pw),
    n_retained     = sum(keep),
    pct_retained   = 100 * sum(keep) / nrow(pw),
    total_ac       = sum(pw$usable_area_nlcd_wind_ac[keep]),
    total_mac      = sum(pw$usable_area_nlcd_wind_ac[keep]) / 1e6
  )
}) |> bind_rows() |>
  mutate(
    delta_vs_1ac_pct = 100 * (total_ac - total_ac[floor_label == "1"]) / total_ac[floor_label == "1"],
    vs_rev_ref_pct   = 100 * (total_ac - REV_REF_WIND_AC) / REV_REF_WIND_AC
  )

cat("\n=== Parcel-area-floor sweep, 5-layer NLCD binary wind ===\n")
print(as.data.frame(sweep |>
  mutate(across(c(pct_below, pct_retained, total_mac, delta_vs_1ac_pct, vs_rev_ref_pct),
                \(x) round(x, 3)),
         total_ac = round(total_ac))))

# --- Validation ------------------------------------------------------------
got <- sweep$total_mac[sweep$floor_label == "1"]
cat(sprintf("\nVALIDATION T=1: %.3f M ac vs published %.3f M ac -> %s\n",
            got, PUB_5LAYER_MAC,
            if (abs(got - PUB_5LAYER_MAC) < 0.001) "MATCH" else "MISMATCH"))

# --- Per-size-bin decomposition -------------------------------------------
bin_order <- c("tiny", "small", "medium", "large", "xlarge")
bins <- lapply(seq_along(THRESHOLDS), function(i) {
  T_ac <- THRESHOLDS[i]
  keep <- !pw$gated_nonarea & pw$acres >= T_ac
  pw[keep, ] |>
    group_by(size_bin) |>
    summarise(ac = sum(usable_area_nlcd_wind_ac), n = n(), .groups = "drop") |>
    mutate(floor_label = LABELS[i])
}) |> bind_rows() |>
  mutate(size_bin = factor(size_bin, levels = bin_order)) |>
  arrange(floor_label, size_bin)

cat("\n=== Per-size-bin acreage (K ac) by floor ===\n")
print(as.data.frame(bins |>
  select(floor_label, size_bin, n, ac) |>
  mutate(k_ac = round(ac / 1e3, 1), ac = NULL)))

write_csv(sweep, file.path(out_dir, "parcel_area_floor_sensitivity_totals.csv"))
write_csv(bins,  file.path(out_dir, "parcel_area_floor_sensitivity_by_bin.csv"))
cat(sprintf("\nWrote outputs to %s\n", out_dir))
