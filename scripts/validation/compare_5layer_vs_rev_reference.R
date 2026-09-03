# 5-layer NLCD binary (3 km airport) vs reV Wind Reference
# Parcel-level agreement analysis on 305,123 CONUS parcels.
#
# Purpose: validate that the 5-layer NLCD binary + reV Reference are
# measuring similar things (same parcels identified as wind-developable
# / non-developable), even though totals differ ~1.6x.

suppressPackageStartupMessages({
  library(dplyr); library(readr); library(tibble); library(tidyr)
})

REPO <- "/Users/rose501/Library/CloudStorage/OneDrive-PNNL/Desktop/IEDO"

NLCD_7LAYER <- file.path(REPO,
  "Scripts/applied_energy_paper/outputs/nlcd_wind/nlcd_wind_percentage_plus_binary.csv")
REV_REF <- file.path(REPO,
  "Scripts/method_comparison/outputs/full_run_wind_reference_2026_04_23/rev_full_population.csv")

OUT_DIR <- file.path(REPO, "Scripts/applied_energy_paper/outputs/validation")
dir.create(OUT_DIR, showWarnings = FALSE, recursive = TRUE)

# ---------------------------------------------------------------------------
# Build 5-layer view by re-combining flags (suppress slope + NWI)
# ---------------------------------------------------------------------------
nlcd <- read_csv(NLCD_7LAYER, show_col_types = FALSE)

# 5-layer flag set: lt_1ac, urban, dod_sua, usfws, airport (3 km)
nlcd_5 <- nlcd %>%
  mutate(
    n_flags_5 = as.integer(flag_lt_1ac) + as.integer(flag_urban) +
                as.integer(flag_dod_sua) + as.integer(flag_usfws) +
                as.integer(flag_airport),
    usable_5layer_ac = ifelse(n_flags_5 > 0, 0, usable_area_nlcd_wind_ac),
    is_dev_5layer    = usable_5layer_ac > 0
  )

cat(sprintf("5-layer usable total: %.0f ac (%d parcels developable)\n",
            sum(nlcd_5$usable_5layer_ac), sum(nlcd_5$is_dev_5layer)))
cat(sprintf("7-layer usable total: %.0f ac (%d parcels developable)\n",
            sum(nlcd$usable_area_nlcd_wind_bin_ac),
            sum(nlcd$usable_area_nlcd_wind_bin_ac > 0)))

# ---------------------------------------------------------------------------
# Join reV Reference
# ---------------------------------------------------------------------------
rev <- read_csv(REV_REF, show_col_types = FALSE,
                col_select = c(PARCEL_LID, usable_area_rev_ac)) %>%
  mutate(is_dev_rev = usable_area_rev_ac > 0)

cat(sprintf("reV Reference total: %.0f ac (%d parcels developable)\n",
            sum(rev$usable_area_rev_ac), sum(rev$is_dev_rev)))

m <- nlcd_5 %>%
  select(PARCEL_LID, SITE_STATE, size_bin, acres,
         usable_5layer_ac, is_dev_5layer,
         usable_area_nlcd_wind_bin_ac,  # 7-layer
         n_flags, n_flags_5) %>%
  inner_join(rev, by = "PARCEL_LID") %>%
  mutate(is_dev_7layer = usable_area_nlcd_wind_bin_ac > 0)

cat(sprintf("\nJoined rows: %d (of 305,123)\n", nrow(m)))

# ---------------------------------------------------------------------------
# Binary-developable confusion matrices
# ---------------------------------------------------------------------------
cat("\n=== 5-layer NLCD binary vs reV Reference (developable? flag) ===\n")
tbl <- table(NLCD_5_dev = m$is_dev_5layer, reV_Ref_dev = m$is_dev_rev)
print(tbl)
cat(sprintf("Agreement: %d / %d (%.2f%%)\n",
    sum(m$is_dev_5layer == m$is_dev_rev), nrow(m),
    100*mean(m$is_dev_5layer == m$is_dev_rev)))

# Kappa (chance-corrected agreement) - manual computation
po <- mean(m$is_dev_5layer == m$is_dev_rev)
p_nlcd <- mean(m$is_dev_5layer); p_rev <- mean(m$is_dev_rev)
pe <- p_nlcd*p_rev + (1-p_nlcd)*(1-p_rev)
kappa <- (po - pe) / (1 - pe)
cat(sprintf("Cohen's kappa: %.3f\n", kappa))

cat("\n=== 7-layer NLCD binary vs reV Reference ===\n")
tbl7 <- table(NLCD_7_dev = m$is_dev_7layer, reV_Ref_dev = m$is_dev_rev)
print(tbl7)
cat(sprintf("Agreement: %d / %d (%.2f%%)\n",
    sum(m$is_dev_7layer == m$is_dev_rev), nrow(m),
    100*mean(m$is_dev_7layer == m$is_dev_rev)))
po7 <- mean(m$is_dev_7layer == m$is_dev_rev)
p7 <- mean(m$is_dev_7layer)
pe7 <- p7*p_rev + (1-p7)*(1-p_rev)
kappa7 <- (po7 - pe7) / (1 - pe7)
cat(sprintf("Cohen's kappa: %.3f\n", kappa7))

# ---------------------------------------------------------------------------
# Where do the disagreements concentrate? By size bin.
# ---------------------------------------------------------------------------
cat("\n=== Disagreement by size bin (5-layer vs reV Reference) ===\n")
m %>%
  mutate(case = case_when(
    is_dev_5layer  & is_dev_rev  ~ "both_dev",
    !is_dev_5layer & !is_dev_rev ~ "both_non",
    is_dev_5layer  & !is_dev_rev ~ "nlcd5_only_dev",
    !is_dev_5layer & is_dev_rev  ~ "rev_only_dev"
  )) %>%
  group_by(size_bin, case) %>% tally() %>%
  pivot_wider(names_from = case, values_from = n, values_fill = 0L) %>%
  as.data.frame() %>% print(row.names=FALSE)

# ---------------------------------------------------------------------------
# Magnitude correlation (restricted to parcels developable in BOTH)
# ---------------------------------------------------------------------------
m_both <- m %>% filter(is_dev_5layer, is_dev_rev)
cat(sprintf("\n=== Magnitude correlation on %d both-developable parcels ===\n",
            nrow(m_both)))
if (nrow(m_both) > 0) {
  cat(sprintf("  NLCD 5-layer total: %.0f ac\n", sum(m_both$usable_5layer_ac)))
  cat(sprintf("  reV Reference total: %.0f ac\n", sum(m_both$usable_area_rev_ac)))
  cat(sprintf("  Ratio (NLCD/reV): %.2fx\n",
              sum(m_both$usable_5layer_ac)/sum(m_both$usable_area_rev_ac)))
  rho <- cor(m_both$usable_5layer_ac, m_both$usable_area_rev_ac, method="spearman")
  cat(sprintf("  Spearman correlation: %.3f\n", rho))
  pr  <- cor(log1p(m_both$usable_5layer_ac), log1p(m_both$usable_area_rev_ac))
  cat(sprintf("  Pearson (log1p scale): %.3f\n", pr))
}

# ---------------------------------------------------------------------------
# Save outputs
# ---------------------------------------------------------------------------
library(tidyr)
summary_rows <- tibble::tibble(
  scenario = c("NLCD pct-only", "NLCD 5-layer binary (3km)",
               "NLCD 7-layer binary (3km+slope+NWI)",
               "reV Wind Reference"),
  total_ac = c(sum(nlcd$usable_area_nlcd_wind_ac),
               sum(nlcd_5$usable_5layer_ac),
               sum(nlcd$usable_area_nlcd_wind_bin_ac),
               sum(rev$usable_area_rev_ac)),
  n_parcels_developable = c(sum(nlcd$usable_area_nlcd_wind_ac > 0),
                            sum(nlcd_5$is_dev_5layer),
                            sum(nlcd$usable_area_nlcd_wind_bin_ac > 0),
                            sum(rev$is_dev_rev))
) %>% mutate(pct_of_pct_only = round(100*total_ac/total_ac[1], 1),
             pct_parcels = round(100*n_parcels_developable/305123, 2))
readr::write_csv(summary_rows, file.path(OUT_DIR, "compare_5vs7vsREV_summary.csv"))

readr::write_csv(m, file.path(OUT_DIR, "compare_5vs7vsREV_parcel.csv"))
cat(sprintf("\nWrote %s\n", file.path(OUT_DIR, "compare_5vs7vsREV_summary.csv")))
cat(sprintf("Wrote %s\n", file.path(OUT_DIR, "compare_5vs7vsREV_parcel.csv")))
