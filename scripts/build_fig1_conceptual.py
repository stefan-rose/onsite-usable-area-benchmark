#!/usr/bin/env python3
"""
Build Figure 1 - Conceptual comparison of NLCD land-cover-proportion
vs reV composite-exclusion usable-area methods, using an Ohio exemplar
parcel (M-FIND v1.1 obs_id 2n60pgp73g, Darke County, 78.8 ac; light
manufacturing in the Ohio statewide parcel land-use code).

Run from repo root under pixi:
    pixi run fig1-conceptual

Outputs (written to the FIGURES directory from config.toml):
    fig3_conceptual_ohio.png
    fig3_conceptual_ohio.pdf
(The output file name keeps its earlier "fig3" prefix because the
manuscript source includes it under that name. It appears as Figure 1
in the compiled paper.)

The figure is drawn at its printed size (6.5 in, the manuscript text
width), so the font sizes below are the sizes on the page. The script
checks before saving that every font is >= MIN_PT, that all text lies
inside the figure, that no two labels overlap, and that every table
label fits inside its cell. It exits non-zero if any check fails.

Data dependencies:
- Parcel boundary: data/exemplar_parcel/ (open OGRIP Ohio Statewide
  Parcels record; see the README there). No licensed geometry is used.
- MRLC WMS: https://www.mrlc.gov/geoserver/mrlc_display/wms (NLCD 2021
  land cover). The tile is cached under intermediate/fig1_conceptual/;
  set FIG1_REFRESH=1 to download it again.
- reV solar composite exclusion rasters (EPSG:5070, 90 m), REV_SOLAR.
- Per-class NLCD acres and the four usable-area values are the pipeline
  values for this parcel (Zenodo release v1.0, row primary_obs_id
  2n60pgp73g). The reV values are re-derived here from the rasters by
  cell-centre zonal means and asserted against the pipeline values.
"""
import os
import sys as _sys
import urllib.parse
import urllib.request
from pathlib import Path as _Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import PathPatch, Rectangle  # noqa: E402
from matplotlib.path import Path as MplPath  # noqa: E402
from rasterio.windows import from_bounds  # noqa: E402
from rasterstats import zonal_stats  # noqa: E402

_REPO = _Path(__file__).resolve().parents[1]
_sys.path.insert(0, str(_REPO / "scripts"))
from _config import FIGURES, INTERMEDIATE, REV_SOLAR  # noqa: E402

OUT = FIGURES / "fig3_conceptual_ohio.png"
EXEMPLAR_OBS_ID = "2n60pgp73g"
PARCEL_GEOJSON = _REPO / "data" / "exemplar_parcel" / "ogrip_39037_F27230906010110101.geojson"
CACHE = INTERMEDIATE / "fig1_conceptual"
CACHE.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------
# Pipeline values for this parcel (Zenodo release v1.0)
# ---------------------------------------------------------------------
GROSS_AC = 78.7953            # parcel_acres (licensed polygon, EPSG:5070)
NLCD_USABLE_AC = 37.1836      # solar_nlcd_ac
REV_USABLE_AC = {"reV Open": 71.2188, "reV Reference": 20.9919, "reV Limited": 9.2534}
# (code, label, acres, solar availability, NLCD legend colour); NLCD code order
NLCD_COMP = [
    ("11", "Open water",            2.3794, 0.00, "#466b9f"),
    ("21", "Developed, open space", 4.7312, 0.30, "#dec5c5"),
    ("22", "Developed, low",        4.1347, 0.30, "#d99282"),
    ("23", "Developed, medium",     4.7686, 0.20, "#eb0000"),
    ("24", "Developed, high",      10.2430, 0.20, "#ab0000"),
    ("81", "Pasture/hay",           0.8471, 0.60, "#dcd93d"),
    ("82", "Cultivated crops",     51.6888, 0.60, "#ab6c28"),
]
TOT_AC = sum(c[2] for c in NLCD_COMP)
assert abs(sum(c[2] * c[3] for c in NLCD_COMP) - NLCD_USABLE_AC) < 0.001

# ---------------------------------------------------------------------
# Parcel (open OGRIP boundary) in EPSG:5070
# ---------------------------------------------------------------------
p_5070 = gpd.read_file(PARCEL_GEOJSON).to_crs(5070)
assert len(p_5070) == 1 and p_5070["mfind_obs_id"].iloc[0] == EXEMPLAR_OBS_ID
assert abs(p_5070.area.iloc[0] / 4046.8564224 - GROSS_AC) < 0.05
geom = p_5070.geometry.iloc[0]
if geom.geom_type == "MultiPolygon":
    geom = max(geom.geoms, key=lambda g: g.area)
OUTLINE = np.array(geom.exterior.coords)   # interior ring is a 0.0006 ac sliver; not drawn
b = p_5070.total_bounds
PAD_M = 90
VIEW = (b[0] - PAD_M, b[1] - PAD_M, b[2] + PAD_M, b[3] + PAD_M)
ASPECT = (VIEW[2] - VIEW[0]) / (VIEW[3] - VIEW[1])   # width / height

# reV: cell-centre zonal means, checked against the pipeline values
REV_STATS = {}
for lbl, key in (("reV Open", "open"), ("reV Reference", "reference"), ("reV Limited", "limited")):
    s = zonal_stats(p_5070, str(REV_SOLAR[key]), stats=["mean", "count"], all_touched=False)[0]
    mean = s["mean"] / (100.0 if s["mean"] > 1.5 else 1.0)
    assert abs(mean * GROSS_AC - REV_USABLE_AC[lbl]) < 0.01, (lbl, mean * GROSS_AC, REV_USABLE_AC[lbl])
    REV_STATS[lbl] = dict(n=s["count"], mean=mean, usable=REV_USABLE_AC[lbl])

# NLCD WMS tile in EPSG:5070 (v1.3.0 BBOX order minx,miny,maxx,maxy)
HPX = 800
WPX = int(round(HPX * ASPECT))
nlcd_png = CACHE / f"nlcd_5070_{EXEMPLAR_OBS_ID}.png"
if os.environ.get("FIG1_REFRESH") or not nlcd_png.exists():
    wms = {
        "SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap",
        "LAYERS": "mrlc_display:NLCD_2021_Land_Cover_L48", "CRS": "EPSG:5070",
        "BBOX": ",".join(f"{v}" for v in VIEW), "WIDTH": str(WPX), "HEIGHT": str(HPX),
        "FORMAT": "image/png", "TRANSPARENT": "TRUE",
    }
    urllib.request.urlretrieve("https://www.mrlc.gov/geoserver/mrlc_display/wms?" + urllib.parse.urlencode(wms), nlcd_png)
nlcd_img = mpimg.imread(nlcd_png)
assert nlcd_img.shape[:2] == (HPX, WPX), nlcd_img.shape

rev_arrays = {}
for lbl, key in (("reV Open", "open"), ("reV Reference", "reference"), ("reV Limited", "limited")):
    with rasterio.open(REV_SOLAR[key]) as src:
        w = from_bounds(*VIEW, transform=src.transform)
        arr = src.read(1, window=w).astype(float)
        if src.nodata is not None:
            arr[arr == src.nodata] = np.nan
        if np.nanmax(arr) > 1.5:
            arr = arr / 100.0
        t = src.window_transform(w)
        r, c = arr.shape
        rev_arrays[lbl] = dict(arr=arr, extent=(t.c, t.c + c * src.res[0], t.f - r * src.res[1], t.f))

# ---------------------------------------------------------------------
# FIGURE, laid out in inches from the top-left at printed size
# ---------------------------------------------------------------------
W, H = 6.5, 6.15
MIN_PT = 7.0
FS = 7.5            # body / table text
FS_HEAD = 8.5       # method headers
INK, INK2, BLUE, GREEN_D = "#111111", "#444444", "#08519c", "#00441b"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": FS,
                     "pdf.fonttype": 42, "axes.linewidth": 0.6})
fig = plt.figure(figsize=(W, H), facecolor="white")
CELLS = []          # (text artist, cell rectangle in inches x, y, w, h)


def T(x, y, s, pt=FS, **kw):
    kw.setdefault("va", "top")
    return fig.text(x / W, 1 - y / H, s, fontsize=pt, **kw)


def AX(x, y, w, h):
    return fig.add_axes([x / W, 1 - (y + h) / H, w / W, h / H])


def style_map(ax, lw=1.1):
    ax.set_xlim(VIEW[0], VIEW[2]); ax.set_ylim(VIEW[1], VIEW[3])
    ax.set_xticks([]); ax.set_yticks([]); ax.set_aspect("equal")
    for sp in ax.spines.values():
        sp.set_edgecolor("#888"); sp.set_linewidth(0.5)
    ax.plot(OUTLINE[:, 0], OUTLINE[:, 1], color="black", lw=lw)


def table(x0, y0, widths, header, rows, row_h=0.165, head_h=0.30, fills=None, bold_rows=(),
          align=None, swatches=None):
    """Draw a table with explicit cells. Returns the bottom y (inches)."""
    align = align or ["left"] + ["right"] * (len(widths) - 1)
    xs = np.concatenate([[x0], x0 + np.cumsum(widths)])
    pad = 0.05

    def cell(ci, y, h, s, fc, bold=False, color=INK, swatch=None):
        fig.add_artist(Rectangle((xs[ci] / W, 1 - (y + h) / H), widths[ci] / W, h / H,
                                 facecolor=fc, edgecolor="#bbbbbb", lw=0.5))
        tx = xs[ci] + pad
        if swatch:
            fig.add_artist(Rectangle(((xs[ci] + pad) / W, 1 - (y + h / 2 + 0.045) / H), 0.11 / W, 0.09 / H,
                                     facecolor=swatch, edgecolor="#666", lw=0.4))
            tx += 0.16
        if align[ci] == "right":
            tx, ha = xs[ci + 1] - pad, "right"
        elif align[ci] == "center":
            tx, ha = (xs[ci] + xs[ci + 1]) / 2, "center"
        else:
            ha = "left"
        t = T(tx, y + h / 2, s, FS, ha=ha, va="center", fontweight="bold" if bold else "normal",
              color=color, linespacing=1.05)
        CELLS.append((t, (xs[ci], y, widths[ci], h)))

    for ci, s in enumerate(header):
        cell(ci, y0, head_h, s, "#e6e6e6", bold=True)
    y = y0 + head_h
    for ri, row in enumerate(rows):
        for ci, s in enumerate(row):
            fc = fills[ri][ci] if fills else "white"
            sw = swatches[ri] if (swatches and ci == 0) else None
            cell(ci, y, row_h, s, fc, bold=ri in bold_rows or (fc == "#c7e9c0"),
                 color=GREEN_D if fc == "#c7e9c0" else INK, swatch=sw)
        y += row_h
    return y


LX, RX, COLW = 0.04, 3.36, 3.10          # left / right column origin and width

T(W / 2, 0.02, f"Exemplar parcel: Darke County, Ohio, {GROSS_AC:.1f} ac", 9.0, ha="center",
  fontweight="bold", color=INK)
T(LX + COLW / 2, 0.27, "NLCD land-cover-proportion method", FS_HEAD, ha="center", fontweight="bold", color=BLUE)
T(RX + COLW / 2, 0.27, "reV composite-exclusion method", FS_HEAD, ha="center", fontweight="bold", color=BLUE)
fig.add_artist(plt.Line2D([(RX - 0.13) / W] * 2, [1 - 0.27 / H, 1 - 4.05 / H], color="#d0d0d0", lw=0.8))

# ---- Row 1, left: NLCD map + class legend
MAP_Y = 0.70
NMAP_H = 1.72
nmap_w = NMAP_H * ASPECT
T(LX, 0.52, "NLCD 2021 land cover (30 m)", FS, color=INK2)
ax_n = AX(LX, MAP_Y, nmap_w, NMAP_H)
ext = (VIEW[0], VIEW[2], VIEW[1], VIEW[3])
ax_n.imshow(nlcd_img, extent=ext, interpolation="nearest", alpha=0.20)
im_n = ax_n.imshow(nlcd_img, extent=ext, interpolation="nearest")
clip = PathPatch(MplPath(OUTLINE), transform=ax_n.transData, facecolor="none", lw=0)
ax_n.add_patch(clip); im_n.set_clip_path(clip)
style_map(ax_n)
lgx = LX + nmap_w + 0.14
T(lgx, MAP_Y, "Classes in parcel", FS, fontweight="bold", color=INK)
for i, (_, nm, _, _, hx) in enumerate(NLCD_COMP):
    yy = MAP_Y + 0.25 + i * 0.205
    fig.add_artist(Rectangle((lgx / W, 1 - (yy + 0.12) / H), 0.13 / W, 0.11 / H, facecolor=hx, edgecolor="#666", lw=0.4))
    T(lgx + 0.19, yy + 0.065, nm, FS, va="center", color=INK)

# ---- Row 1, right: three reV maps + colorbar
cmap_rev = LinearSegmentedColormap.from_list("rev_incl", ["#08306b", "#4292c6", "#c6dbef", "#f7f7f7"])
GAP = 0.10
cw = (COLW - 2 * GAP) / 3
rmap_h = cw / ASPECT
for k, (lbl, d) in enumerate(rev_arrays.items()):
    x = RX + k * (cw + GAP)
    T(x + cw / 2, 0.52, lbl, FS, ha="center", color=INK2)
    ax = AX(x, MAP_Y, cw, rmap_h)
    im_r = ax.imshow(d["arr"], extent=d["extent"], cmap=cmap_rev, vmin=0, vmax=1, interpolation="nearest")
    style_map(ax, lw=0.9)
CB_Y = MAP_Y + rmap_h + 0.16
cax = AX(RX + 0.12, CB_Y, COLW - 0.24, 0.08)
cb = fig.colorbar(im_r, cax=cax, orientation="horizontal")
cb.set_ticks([0, 0.25, 0.5, 0.75, 1.0])
cb.ax.tick_params(labelsize=FS, length=2, width=0.5, pad=1.5)
cb.outline.set_linewidth(0.5)
T(RX + COLW / 2, CB_Y + 0.30, "Inclusion fraction (0 = excluded, dark;\n1 = fully included, light)",
  FS, ha="center", color=INK2, linespacing=1.15)

# ---- Row 2: tables
TB_Y = 2.55
T(LX, TB_Y, "Weighted sum across NLCD classes (30 m)", FS, fontweight="bold", color=INK)
rows_n = [[nm, f"{ac:.2f}", f"{av:.2f}", f"{ac * av:.2f}"] for _, nm, ac, av, _ in NLCD_COMP]
rows_n.append(["Total (usable area)", f"{TOT_AC:.2f}", "", f"{NLCD_USABLE_AC:.2f}"])
fills_n = [["white"] * 4 for _ in NLCD_COMP] + [["#f0f0f0", "#f0f0f0", "#f0f0f0", "#c7e9c0"]]
yb_n = table(LX, TB_Y + 0.20, [1.50, 0.46, 0.50, 0.64],
             ["NLCD class", "Area\n(ac)", "Solar\navail.", "Contrib.\n(ac)"],
             rows_n, fills=fills_n, bold_rows=(len(rows_n) - 1,),
             swatches=[c[4] for c in NLCD_COMP] + [None])
T(LX, yb_n + 0.08, "Usable area = \u03a3 over classes (class area \u00d7 solar availability)", FS, color=INK2)

T(RX, TB_Y, "Coverage-weighted sum across reV cells (90 m)", FS, fontweight="bold", color=INK)
scen_bg = {"reV Open": "#deebf7", "reV Reference": "#6baed6", "reV Limited": "#08519c"}
rows_r = [[lbl, f"{d['n']}", f"{d['mean']:.3f}", f"{d['usable']:.2f}"] for lbl, d in REV_STATS.items()]
fills_r = [[scen_bg[lbl], "white", "white", "#c7e9c0"] for lbl in REV_STATS]
yb_r = table(RX, TB_Y + 0.20, [1.02, 0.56, 0.74, 0.78],
             ["Scenario", "Cells\n(n)", "Mean\ninclusion", "Usable\narea (ac)"], rows_r, fills=fills_r)
for t, (cx, cy, cwid, ch) in CELLS:     # white text on the dark Limited fill
    if t.get_text() == "reV Limited":
        t.set_color("white")
T(RX, yb_r + 0.08, "Usable area = \u03a3 over cells (cell area \u00d7 inclusion fraction)", FS, color=INK2)
T(RX, yb_r + 0.34, "Cells: 90 m cells whose centres fall inside the parcel.\n"
  "Equivalently, mean inclusion \u00d7 parcel area.", FS, color=INK2, linespacing=1.15)

# ---- Row 3: comparison bar
BAR_Y = 4.75
T(LX, BAR_Y, "Method outputs for this parcel (solar)", FS, fontweight="bold", color=INK)
ax_c = AX(1.02, BAR_Y + 0.22, W - 1.02 - 0.30, 0.86)
methods = ["NLCD", "reV Open", "reV Reference", "reV Limited"]
values = [NLCD_USABLE_AC] + [REV_USABLE_AC[m] for m in methods[1:]]
colors = ["#2ca25f", "#deebf7", "#6baed6", "#08519c"]
edges = ["#00441b", "#08519c", "#08519c", "#08519c"]
ax_c.barh(np.arange(4), values, color=colors, edgecolor=edges, linewidth=0.7, height=0.66)
# Value labels: outside the bar end, except where that would cross the
# gross-area line; those go inside the bar (right-aligned).
XMAX = 85.0                       # just past gross area; no estimate can exceed it
BAR_LABELS = []
for i, v in enumerate(values):
    inside = v + 14.0 > GROSS_AC
    t = ax_c.text(v - 1.0 if inside else v + 1.0, i, f"{v:.2f} ac", va="center",
                  ha="right" if inside else "left", fontsize=FS, fontweight="bold",
                  color="white" if (inside and colors[i] == "#08519c") else INK)
    BAR_LABELS.append(t)
ax_c.set_yticks(np.arange(4)); ax_c.set_yticklabels(methods, fontsize=FS)
ax_c.invert_yaxis()
ax_c.set_xlim(0, XMAX)
ax_c.set_xticks([0, 20, 40, 60, 80])
ax_c.set_xlabel("Usable area estimate (ac)", fontsize=FS, labelpad=2)
ax_c.tick_params(axis="both", labelsize=FS, length=2, width=0.5, pad=2)
ax_c.spines[["top", "right"]].set_visible(False)
ax_c.axvline(GROSS_AC, color="#888", linestyle="--", linewidth=0.8)
# Gross-area label sits just above the plot, centred on the dashed line.
GROSS_LABEL = ax_c.text(GROSS_AC, 1.03, f"parcel gross {GROSS_AC:.1f} ac", transform=ax_c.get_xaxis_transform(),
                        fontsize=FS, color="#555", ha="center", va="bottom", clip_on=False)

# ---------------------------------------------------------------------
# Checks (no mathtext is used, so no sub-/superscripts below the floor): font floor, in-bounds, no overlaps, table labels inside cells
# ---------------------------------------------------------------------
fig.canvas.draw()
rend = fig.canvas.get_renderer()
to_px = fig.dpi
allt = [t for t in fig.findobj(matplotlib.text.Text) if t.get_text().strip() and t.get_visible()]
problems = [f"font {t.get_fontsize()} pt < {MIN_PT}: {t.get_text()!r}" for t in allt if t.get_fontsize() < MIN_PT - 1e-6]
fb = fig.bbox
boxes = [(t, t.get_window_extent(rend)) for t in allt]
for t, bb in boxes:
    if bb.x0 < fb.x0 or bb.x1 > fb.x1 or bb.y0 < fb.y0 or bb.y1 > fb.y1:
        problems.append(f"out of figure: {t.get_text()!r}")
for i in range(len(boxes)):
    for j in range(i + 1, len(boxes)):
        a, c = boxes[i][1], boxes[j][1]
        if min(a.x1, c.x1) - max(a.x0, c.x0) > 0.5 and min(a.y1, c.y1) - max(a.y0, c.y0) > 0.5:
            problems.append(f"overlap: {boxes[i][0].get_text()!r} / {boxes[j][0].get_text()!r}")
PAD_IN = 0.02
for t, (cx, cy, cwid, ch) in CELLS:
    bb = t.get_window_extent(rend)
    x0, x1 = (cx + PAD_IN) * to_px, (cx + cwid - PAD_IN) * to_px
    y1, y0 = (H - cy - PAD_IN) * to_px, (H - cy - ch + PAD_IN) * to_px
    if bb.x0 < x0 or bb.x1 > x1 or bb.y0 < y0 or bb.y1 > y1:
        problems.append(f"label outside its cell: {t.get_text()!r}")
map_axes = [a for a in fig.axes if a is not cax and a is not ax_c]
for a in map_axes:
    ab = a.get_window_extent(rend)
    for t, bb in boxes:
        if t.axes is None and min(bb.x1, ab.x1) - max(bb.x0, ab.x0) > 0.5 and min(bb.y1, ab.y1) - max(bb.y0, ab.y0) > 0.5:
            problems.append(f"text on map: {t.get_text()!r}")
axb = ax_c.get_window_extent(rend)
gb = GROSS_LABEL.get_window_extent(rend)
if gb.y0 < axb.y1:
    problems.append("gross label overlaps the plot area")
xline = ax_c.transData.transform((GROSS_AC, 0))[0]
for t in BAR_LABELS:
    bb = t.get_window_extent(rend)
    if bb.x0 - 1 < xline < bb.x1 + 1:
        problems.append(f"bar label crosses the gross line: {t.get_text()!r}")
    if bb.x1 > axb.x1 or bb.x0 < axb.x0:
        problems.append(f"bar label outside plot: {t.get_text()!r}")
for i, t in enumerate(BAR_LABELS):      # inside labels must fit inside their bar
    if t.get_ha() == "right":
        bb = t.get_window_extent(rend)
        if bb.x0 < ax_c.transData.transform((0, 0))[0] + 2:
            problems.append(f"bar label wider than bar: {t.get_text()!r}")
print("\n".join(problems) if problems else
      f"layout check: OK ({len(allt)} labels, {len(CELLS)} table cells, min font {min(t.get_fontsize() for t in allt)} pt)")
for lbl, d in REV_STATS.items():
    print(f"  {lbl}: n={d['n']} mean={d['mean']:.4f} usable={d['usable']:.4f}")
print(f"  NLCD: total {TOT_AC:.4f} ac, usable {NLCD_USABLE_AC:.4f} ac; gross {GROSS_AC:.4f} ac")

fig.savefig(OUT, dpi=300, facecolor="white")
fig.savefig(OUT.with_suffix(".pdf"), facecolor="white")
print(f"Saved {OUT} and .pdf ({W} x {H} in)")
_sys.exit(1 if problems else 0)
