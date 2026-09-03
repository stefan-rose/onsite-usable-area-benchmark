#!/usr/bin/env python3
"""
Build Figure 3 - Conceptual comparison of NLCD land-cover-proportion
vs reV composite-exclusion usable-area methods, using an Ohio exemplar
parcel (PARCEL_LID 02045A7E94BIP8PKTU7I4T, 81.2 ac).

Run from repo root under pixi:
    cd Scripts/method_comparison && pixi run python ../applied_energy_paper/build_fig3.py

Outputs (relative to manuscript root):
    manuscript/figures/fig3_conceptual_ohio.png
    manuscript/figures/fig3_conceptual_ohio.pdf

Data dependencies:
- MRLC WMS: https://www.mrlc.gov/geoserver/mrlc_display/wms  (NLCD 2021 land cover)
- reV composite exclusion rasters (EPSG:5070, 90 m) under Data/reV Exclusions/
- Parcel geometry from parcels_conus_2026_04_23.gpkg
- Pipeline exact values from method_comparison output CSVs.
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec, GridSpecFromSubplotSpec
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.path import Path as MplPath
from matplotlib.patches import PathPatch
import matplotlib.image as mpimg
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.mask import mask
from rasterio.windows import from_bounds
import urllib.request, urllib.parse, os

OUT = "/Users/rose501/OneDrive - PNNL/Desktop/IEDO/Communications/Paper/Applied Energy/manuscript/figures/fig3_conceptual_ohio.png"

# --- Parcel in EPSG:5070 (same as reV) ---
p_wgs = gpd.read_file("/tmp/fig3/parcel_A.gpkg").to_crs(4326)
p_5070 = p_wgs.to_crs(5070)
b5070 = p_5070.total_bounds
# Symmetric padding
pad_m = 90
b5070_pad = (b5070[0]-pad_m, b5070[1]-pad_m, b5070[2]+pad_m, b5070[3]+pad_m)

# --- NLCD via WMS in EPSG:5070 (matches reV CRS) ---
# WMS BBOX in v1.3.0 order for EPSG:5070 (projected) is minx,miny,maxx,maxy
wms_params = {
    "SERVICE":"WMS","VERSION":"1.3.0","REQUEST":"GetMap",
    "LAYERS":"mrlc_display:NLCD_2021_Land_Cover_L48",
    "CRS":"EPSG:5070",
    "BBOX":f"{b5070_pad[0]},{b5070_pad[1]},{b5070_pad[2]},{b5070_pad[3]}",
    "WIDTH":"500","HEIGHT":"800","FORMAT":"image/png","TRANSPARENT":"TRUE",
}
nlcd_png = "/tmp/fig3/nlcd_5070.png"
# Always refresh so we're consistent
urllib.request.urlretrieve(
    "https://www.mrlc.gov/geoserver/mrlc_display/wms?" + urllib.parse.urlencode(wms_params),
    nlcd_png)
nlcd_img = mpimg.imread(nlcd_png)
print(f"NLCD img shape: {nlcd_img.shape}, size {os.path.getsize(nlcd_png)} bytes")

# --- reV rasters clipped to same bbox ---
rev_paths = {
    "reV Open":      "/Users/rose501/OneDrive - PNNL/Desktop/IEDO/Data/reV Exclusions/composite_exclusions_open.tif",
    "reV Reference": "/Users/rose501/OneDrive - PNNL/Desktop/IEDO/Data/reV Exclusions/composite_exclusions_reference.tif",
    "reV Limited":   "/Users/rose501/OneDrive - PNNL/Desktop/IEDO/Data/reV Exclusions/composite_exclusions_limited.tif",
}
rev_arrays = {}
for lbl, pth in rev_paths.items():
    with rasterio.open(pth) as src:
        w = from_bounds(*b5070_pad, transform=src.transform)
        arr = src.read(1, window=w)
        arr = np.where(arr == src.nodata, np.nan, arr)
        win_transform = src.window_transform(w)
        rows, cols = arr.shape
        left = win_transform.c
        top  = win_transform.f
        right = left + cols*src.res[0]
        bottom = top - rows*src.res[1]
        rev_arrays[lbl] = dict(arr=arr, extent=(left, right, bottom, top))

# --- Pipeline exact values (from CSVs) ---
PIPELINE = {
    "nlcd_usable_ac": 35.475,
    "rev": {
        "reV Open":      {"n_pix":40, "mean_incl":0.9485, "usable_ac":77.034},
        "reV Reference": {"n_pix":40, "mean_incl":0.2945, "usable_ac":23.918},
        "reV Limited":   {"n_pix":40, "mean_incl":0.0215, "usable_ac":1.746},
    },
    "parcel_gross_ac": p_wgs.acres.iloc[0],
}

# NLCD per-class exact values (ac, avail, color)
nlcd_comp = [
    ("82", "Cultivated Crops",        30.377, 0.60, "#ab6c28"),
    ("81", "Pasture/Hay",             21.392, 0.60, "#dcd93d"),
    ("41", "Deciduous Forest",        17.018, 0.10, "#68ab5f"),
    ("43", "Mixed Forest",             6.369, 0.15, "#b5c58f"),
    ("21", "Developed, Open Space",    3.829, 0.30, "#dec5c5"),
    ("22", "Developed, Low",           1.795, 0.30, "#d99282"),
    ("23", "Developed, Medium",        0.345, 0.20, "#eb0000"),
]
tot_ac = sum(c[2] for c in nlcd_comp)
nlcd_usable_ac = sum(c[2]*c[3] for c in nlcd_comp)
print(f"NLCD sum: {tot_ac:.3f} ac; usable: {nlcd_usable_ac:.3f} ac (pipeline: 35.475)")

# =====================================================================
# FIGURE
# =====================================================================
fig = plt.figure(figsize=(13.5, 9.3), constrained_layout=False)
gs = GridSpec(3, 2, figure=fig,
              height_ratios=[1.35, 0.98, 0.72],
              width_ratios=[1.0, 1.0],
              hspace=0.36, wspace=0.14, left=0.055, right=0.98, top=0.92, bottom=0.06)

fig.suptitle(f"Exemplar parcel · Ohio · {PIPELINE['parcel_gross_ac']:.1f} ac",
             fontsize=15, fontweight="bold", y=0.985, color="#111111")
fig.text(0.28, 0.945, "NLCD land-cover-proportion method",
         ha="center", fontsize=13, fontweight="bold", color="#08519c")
fig.text(0.76, 0.945, "reV composite-exclusion method",
         ha="center", fontsize=13, fontweight="bold", color="#08519c")

# ---------------------------------------------------------------------
# ROW 1 — MAPS (all in EPSG:5070)
# ---------------------------------------------------------------------
# NLCD map — clipped to parcel polygon
ax_n = fig.add_subplot(gs[0, 0])
# First draw a very light gray background rectangle showing bbox extent
ax_n.imshow(nlcd_img, extent=(b5070_pad[0], b5070_pad[2], b5070_pad[1], b5070_pad[3]),
            interpolation="nearest", aspect="equal", alpha=0.20)
# Then draw same image again clipped to parcel path (full opacity where parcel lies)
im_nlcd = ax_n.imshow(nlcd_img, extent=(b5070_pad[0], b5070_pad[2], b5070_pad[1], b5070_pad[3]),
                      interpolation="nearest", aspect="equal", alpha=1.0)
# Build clip path from parcel polygon
parcel_geom = p_5070.geometry.iloc[0]
# Handle MultiPolygon by taking largest polygon
if parcel_geom.geom_type == "MultiPolygon":
    parcel_geom = max(parcel_geom.geoms, key=lambda g: g.area)
xy = np.array(parcel_geom.exterior.coords)
clip_path = MplPath(xy)
clip_patch = PathPatch(clip_path, transform=ax_n.transData, facecolor="none")
ax_n.add_patch(clip_patch)
im_nlcd.set_clip_path(clip_patch)

# Draw parcel outline on top
p_5070.plot(ax=ax_n, facecolor="none", edgecolor="black", linewidth=1.8)
ax_n.set_xlim(b5070_pad[0], b5070_pad[2])
ax_n.set_ylim(b5070_pad[1], b5070_pad[3])
ax_n.set_title("NLCD 2021 land cover (30 m)", fontsize=10, loc="left")
ax_n.set_xticks([]); ax_n.set_yticks([])
for s in ax_n.spines.values(): s.set_edgecolor("#888"); s.set_linewidth(0.6)

# Inline NLCD legend
legend_handles = [mpatches.Patch(facecolor=hx, edgecolor="#666", linewidth=0.4, label=nm)
                  for _, nm, _, _, hx in nlcd_comp]
ax_n.legend(handles=legend_handles, loc="center left", bbox_to_anchor=(1.02, 0.5),
            fontsize=8, frameon=False, title="Classes present", title_fontsize=8,
            handlelength=1.2, handleheight=1.0, labelspacing=0.5)

# reV small-multiples — REVERSED cmap: light=included(1), dark=excluded(0)
sub_gs = GridSpecFromSubplotSpec(1, 3, subplot_spec=gs[0,1], wspace=0.10)
# Reversed: 0 = dark blue (excluded), 1 = light/near-white (included)
cmap_rev = LinearSegmentedColormap.from_list("rev_incl_rev", ["#08306b","#4292c6","#c6dbef","#f7f7f7"])
rev_axes = []
first_ax_pos = None
last_ax_pos = None
for i, (lbl, d) in enumerate(rev_arrays.items()):
    ax = fig.add_subplot(sub_gs[0, i])
    im = ax.imshow(d["arr"], extent=d["extent"], cmap=cmap_rev, vmin=0, vmax=1,
                   interpolation="nearest", aspect="equal")
    p_5070.plot(ax=ax, facecolor="none", edgecolor="black", linewidth=1.5)
    ax.set_xlim(d["extent"][0], d["extent"][1])
    ax.set_ylim(d["extent"][2], d["extent"][3])
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title(lbl, fontsize=10, pad=3)
    for s in ax.spines.values(): s.set_edgecolor("#888"); s.set_linewidth(0.5)
    rev_axes.append((ax, im))

# Draw once so subplot positions are finalized, then align colorbar to sub-plot extent
fig.canvas.draw()
pos_left  = rev_axes[0][0].get_position()
pos_right = rev_axes[-1][0].get_position()
cbar_left  = pos_left.x0
cbar_width = pos_right.x1 - pos_left.x0
cbar_ax = fig.add_axes([cbar_left, 0.605, cbar_width, 0.014])
cb = plt.colorbar(rev_axes[-1][1], cax=cbar_ax, orientation="horizontal")
cb.set_label("Inclusion fraction (0 = excluded [dark], 1 = fully included [light])", fontsize=8)
cb.ax.tick_params(labelsize=8)

# ---------------------------------------------------------------------
# ROW 2 — TABLES
# ---------------------------------------------------------------------
ax_tbl_n = fig.add_subplot(gs[1, 0])
ax_tbl_n.axis("off")
ax_tbl_n.set_title("Weighted sum across NLCD classes (30 m)", fontsize=10, loc="left", pad=6)

col_labels = ["NLCD class", "Area\n(ac)", "Solar avail.\n(0–1)", "Contribution\n(ac)"]
cell_text  = []
cell_colors = []
for code, name, ac, avail, hex_col in nlcd_comp:
    contrib = ac*avail
    cell_text.append([f"{name}", f"{ac:.2f}", f"{avail:.2f}", f"{contrib:.2f}"])
    cell_colors.append([hex_col, "white", "white", "white"])
cell_text.append(["Σ  (usable area)", f"{tot_ac:.2f}", "", f"{nlcd_usable_ac:.2f}"])
cell_colors.append(["#f0f0f0"]*4)

tbl_n = ax_tbl_n.table(cellText=cell_text, colLabels=col_labels, cellColours=cell_colors,
                       loc="center", cellLoc="center",
                       colWidths=[0.45, 0.14, 0.18, 0.20])
tbl_n.auto_set_font_size(False); tbl_n.set_fontsize(9)
tbl_n.scale(1, 1.30)
for (r,c), cell in tbl_n.get_celld().items():
    cell.set_edgecolor("#bbb")
    if r == 0:
        cell.set_text_props(fontweight="bold"); cell.set_facecolor("#e6e6e6")
    if r == len(cell_text):
        cell.set_text_props(fontweight="bold")
    if c == 0 and r > 0:
        cell.set_text_props(ha="left"); cell._loc = "left"
    # White text on dark class color for readability
    if r > 0 and r <= len(nlcd_comp) and c == 0:
        _, _, _, _, hex_col = nlcd_comp[r-1]
        if hex_col in ["#ab6c28","#68ab5f","#eb0000"]:
            cell.set_text_props(color="white", ha="left")
tbl_n.get_celld()[(len(cell_text), 3)].set_facecolor("#c7e9c0")
tbl_n.get_celld()[(len(cell_text), 3)].set_text_props(fontweight="bold", color="#00441b")

ax_tbl_r = fig.add_subplot(gs[1, 1])
ax_tbl_r.axis("off")
ax_tbl_r.set_title("Coverage-weighted sum across reV composite cells (90 m)",
                   fontsize=10, loc="left", pad=6)

col_labels_r = ["Scenario", "N cells", "Mean inclusion", "Usable area (ac)"]
cell_text_r = []
cell_colors_r = []
# Light→dark palette consistent with bar chart
scenario_bg = {"reV Open":"#deebf7", "reV Reference":"#6baed6", "reV Limited":"#08519c"}
scenario_text = {"reV Open":"black", "reV Reference":"black", "reV Limited":"white"}
for lbl in ["reV Open","reV Reference","reV Limited"]:
    d = PIPELINE["rev"][lbl]
    cell_text_r.append([lbl, f"{d['n_pix']}", f"{d['mean_incl']:.3f}", f"{d['usable_ac']:.2f}"])
    cell_colors_r.append([scenario_bg[lbl], "white", "white", "white"])

tbl_r = ax_tbl_r.table(cellText=cell_text_r, colLabels=col_labels_r, cellColours=cell_colors_r,
                       loc="upper center", cellLoc="center",
                       colWidths=[0.30, 0.16, 0.24, 0.28])
tbl_r.auto_set_font_size(False); tbl_r.set_fontsize(9)
tbl_r.scale(1, 1.30)
for (r,c), cell in tbl_r.get_celld().items():
    cell.set_edgecolor("#bbb")
    if r == 0:
        cell.set_text_props(fontweight="bold"); cell.set_facecolor("#e6e6e6")
    if c == 0 and r > 0:
        lbl_r = ["reV Open","reV Reference","reV Limited"][r-1]
        cell.set_text_props(ha="left", color=scenario_text[lbl_r]); cell._loc = "left"
    if c == 3 and r > 0:
        cell.set_text_props(fontweight="bold")
        cell.set_facecolor("#c7e9c0")

ax_tbl_n.text(0.02, -0.12,
              r"$\mathrm{usable\ area} = \sum_c A_c \times f_c^{\mathrm{avail}}$",
              transform=ax_tbl_n.transAxes, fontsize=10, color="#444")
ax_tbl_r.text(0.02, 0.40,
              r"$\mathrm{usable\ area} = \sum_i A_{\mathrm{pixel}} \times \mathrm{incl}_i$",
              transform=ax_tbl_r.transAxes, fontsize=10, color="#444")

# ---------------------------------------------------------------------
# ROW 3 — COMPARISON BAR (Open=light → Limited=dark)
# ---------------------------------------------------------------------
ax_cmp = fig.add_subplot(gs[2, :])
methods = ["NLCD", "reV Open", "reV Reference", "reV Limited"]
values  = [PIPELINE["nlcd_usable_ac"],
           PIPELINE["rev"]["reV Open"]["usable_ac"],
           PIPELINE["rev"]["reV Reference"]["usable_ac"],
           PIPELINE["rev"]["reV Limited"]["usable_ac"]]
# Open→Limited = light→dark, matching table & colorbar semantics
colors  = ["#2ca25f", "#deebf7", "#6baed6", "#08519c"]
edge_colors = ["#00441b", "#08519c", "#08519c", "#08519c"]

bars = ax_cmp.barh(np.arange(4), values, color=colors, edgecolor=edge_colors, linewidth=1.2)
for i, v in enumerate(values):
    ax_cmp.text(v+1, i, f"{v:.2f} ac", va="center", fontsize=10, fontweight="bold")
ax_cmp.set_yticks(np.arange(4))
ax_cmp.set_yticklabels(methods, fontsize=10)
ax_cmp.invert_yaxis()
ax_cmp.set_xlim(0, max(values)*1.12)
ax_cmp.set_xlabel("Usable area estimate (ac) — solar", fontsize=10)
ax_cmp.set_title(f"Method outputs for this parcel (parcel gross area = {PIPELINE['parcel_gross_ac']:.1f} ac)",
                 fontsize=10, loc="left")
ax_cmp.spines[["top","right"]].set_visible(False)
ax_cmp.tick_params(axis="x", labelsize=9)
ax_cmp.axvline(PIPELINE['parcel_gross_ac'], color="#888", linestyle="--", linewidth=1)
ax_cmp.text(PIPELINE['parcel_gross_ac']+0.5, -0.55, f"parcel gross = {PIPELINE['parcel_gross_ac']:.1f} ac",
            fontsize=8, color="#666", va="bottom")

plt.savefig(OUT, dpi=180, bbox_inches="tight", facecolor="white")
plt.savefig(OUT.replace(".png", ".pdf"), bbox_inches="tight", facecolor="white")
print(f"Saved {OUT}")