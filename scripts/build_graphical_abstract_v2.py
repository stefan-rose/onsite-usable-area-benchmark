"""Graphical abstract v2 (flow layout) for the Applied Energy submission.

Layout: (1) parcels -> (2) two methods on one example parcel -> (3) national
usable area as plain bars, plus a one-line takeaway band. Replaces the v1
dot-range middle panel (overlapping symbols).

Elsevier spec: >= 1328 x 531 px, readable at 13 x 5 cm. Drawn at 13.0 x 5.2 cm,
min font 7 pt, no mathtext.

Numbers: national totals (million acres) from the Zenodo release v1.0
summaries, asserted against the abstract ratios; exemplar parcel values as in
build_fig1_conceptual.py (Darke Co., OH, obs 2n60pgp73g, open OGRIP boundary).

Run: PROJ_NETWORK=OFF pixi run -q python scripts/build_graphical_abstract_v2.py
"""
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import FancyArrowPatch, PathPatch, Rectangle  # noqa: E402
from matplotlib.path import Path as MplPath  # noqa: E402
from rasterio.windows import from_bounds  # noqa: E402
from shapely.geometry import box  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from _config import FIGURES, INTERMEDIATE, REV_SOLAR  # noqa: E402

plt.rcParams["mathtext.default"] = "regular"
plt.rcParams["text.usetex"] = False
plt.rcParams["font.family"] = "DejaVu Sans"

# ---------------------------------------------------------------- data
SOLAR = dict(lim=0.9842, ref=2.3228, open=5.7266, nlcd=2.9082)
WIND = {  # NLCD = 5-layer binary exclusions; Open shared across turbines
    "80/77": dict(lim=0.4347, ref=1.2410, open=4.4141, nlcd=1.3093),
    "115/170": dict(lim=0.2346, ref=0.7940, open=4.4141, nlcd=1.3093),
}
assert round(SOLAR["open"] / SOLAR["lim"], 1) == 5.8
assert round(WIND["80/77"]["open"] / WIND["80/77"]["lim"], 1) == 10.2
assert round(WIND["115/170"]["open"] / WIND["115/170"]["lim"], 1) == 18.8
assert round(SOLAR["nlcd"] / SOLAR["ref"], 2) == 1.25
assert round(WIND["80/77"]["nlcd"] / WIND["80/77"]["ref"], 2) == 1.06
assert round(WIND["115/170"]["nlcd"] / WIND["115/170"]["ref"], 2) == 1.65
N_PARCELS = "305,123"

OBS = "2n60pgp73g"
GEOJSON = REPO / "data" / "exemplar_parcel" / "ogrip_39037_F27230906010110101.geojson"
NLCD_PNG = INTERMEDIATE / "fig1_conceptual" / f"nlcd_5070_{OBS}.png"
NEIGHBORS = REPO / "data" / "exemplar_parcel" / "ogrip_darke_neighbors.geojson"
EX = dict(gross=78.7953, nlcd=37.1836, open=71.2188, ref=20.9919, lim=9.2534)

p = gpd.read_file(GEOJSON).to_crs(5070)
assert p["mfind_obs_id"].iloc[0] == OBS
g = p.geometry.iloc[0]
if g.geom_type == "MultiPolygon":
    g = max(g.geoms, key=lambda q: q.area)
OUTLINE = np.array(g.exterior.coords)
b = p.total_bounds
PAD = 90
VIEW = (b[0] - PAD, b[1] - PAD, b[2] + PAD, b[3] + PAD)   # same as Fig 1 -> NLCD cache matches
ASPECT = (VIEW[2] - VIEW[0]) / (VIEW[3] - VIEW[1])
nlcd_img = mpimg.imread(NLCD_PNG)
with rasterio.open(REV_SOLAR["reference"]) as src:
    w = from_bounds(*VIEW, transform=src.transform)
    arr = src.read(1, window=w).astype(float)
    if src.nodata is not None:
        arr[arr == src.nodata] = np.nan
    if np.nanmax(arr) > 1.5:
        arr /= 100.0
    t = src.window_transform(w)
    r, c = arr.shape
    rev_ext = (t.c, t.c + c * src.res[0], t.f - r * src.res[1], t.f)

# ---------------------------------------------------------------- figure
CM = 1 / 2.54
W, H = 13.0 * CM, 5.2 * CM
MIN_PT, FS, FS_H = 7.0, 7.0, 8.0
INK, INK2 = "#1a1a1a", "#555555"
C_REV, C_REV_L, C_NLCD, C_BG = "#2b6cb0", "#a9c8e8", "#b35806", "#EAF2FA"
C_MFG = "#6b6b6b"
TEXTS, AXES_BOXES, ARROWS = [], [], []

fig = plt.figure(figsize=(W, H))
fig.patch.set_facecolor("white")


def T(x, y, s, pt=FS, **kw):
    kw.setdefault("va", "top")
    kw.setdefault("color", INK)
    a = fig.text(x / W, 1 - y / H, s, fontsize=pt, **kw)
    TEXTS.append(a)
    return a


def AX(x, y, w, h, name):
    ax = fig.add_axes([x / W, 1 - (y + h) / H, w / W, h / H])
    AXES_BOXES.append((name, ax))
    return ax


def ARROW(x0, x1, y):
    a = FancyArrowPatch((x0 / W, 1 - y / H), (x1 / W, 1 - y / H), transform=fig.transFigure,
                        arrowstyle="-|>", mutation_scale=7, lw=1.0, color="#777777")
    fig.add_artist(a)
    ARROWS.append(a)


def map_style(ax, lw=0.8):
    ax.plot(OUTLINE[:, 0], OUTLINE[:, 1], color="black", lw=lw)
    ax.set_xlim(VIEW[0], VIEW[2]); ax.set_ylim(VIEW[1], VIEW[3])
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)


BAND_Y = 1.66            # top of takeaway band (in)
ROW_Y0 = 0.36            # top of panel content

# ---- Panel 1: parcels (exemplar in context: open OGRIP parcels around it)
P1X, P1W = 0.06, 1.02
T(P1X, 0.07, "1  Parcels", FS_H, fontweight="bold")
MH1 = 0.78
NB = gpd.read_file(NEIGHBORS).to_crs(5070)
_c = g.centroid
V1_W = 2400.0                                  # m across
V1_H = V1_W * MH1 / P1W
VIEW1 = (_c.x - V1_W / 2, _c.y - V1_H / 2, _c.x + V1_W / 2, _c.y + V1_H / 2)
ax1 = AX(P1X, ROW_Y0, P1W, MH1, "map1")
NB[~NB.in_universe].plot(ax=ax1, facecolor="white", edgecolor="#b5b5b5", lw=0.25)
NB[NB.in_universe & ~NB.is_exemplar].plot(ax=ax1, facecolor=C_MFG, edgecolor=C_MFG, lw=0.3)
ax1.fill(OUTLINE[:, 0], OUTLINE[:, 1], color=C_MFG, lw=0)
ax1.plot(OUTLINE[:, 0], OUTLINE[:, 1], color="black", lw=1.1)
ax1.set_xlim(VIEW1[0], VIEW1[2]); ax1.set_ylim(VIEW1[1], VIEW1[3])
ax1.set_aspect("equal", adjustable="datalim")
ax1.set_xticks([]); ax1.set_yticks([])
for _s in ax1.spines.values():
    _s.set_color("#999999"); _s.set_linewidth(0.4)
N_MFG_VIEW = int(NB[NB.in_universe].intersects(box(*VIEW1)).sum())
LEG_Y = ROW_Y0 + MH1 + 0.05
leg = Rectangle(((P1X + 0.0) / W, 1 - (LEG_Y + 0.085) / H), 0.075 / W, 0.075 / H,
                transform=fig.transFigure, facecolor=C_MFG, edgecolor="none")
fig.add_artist(leg)
T(P1X + 0.11, LEG_Y - 0.005, "manufacturing parcel", FS, color=INK2)
T(P1X + P1W / 2, LEG_Y + 0.15, N_PARCELS, FS_H, ha="center", fontweight="bold")
T(P1X + P1W / 2, LEG_Y + 0.30, "across CONUS", FS, ha="center", color=INK2)

# ---- Panel 2: two methods on one parcel
P2X, P2W = 1.30, 1.36
ARROW(P1X + P1W + 0.03, P2X - 0.04, ROW_Y0 + 0.31)
T(P2X, 0.07, "2  Two methods", FS_H, fontweight="bold")
MH2 = 0.62
MW2 = MH2 * ASPECT
GAP2 = P2W - 2 * MW2
ax_n = AX(P2X, ROW_Y0, MW2, MH2, "map_nlcd")
ext = (VIEW[0], VIEW[2], VIEW[1], VIEW[3])
im = ax_n.imshow(nlcd_img, extent=ext, interpolation="nearest")
clip = PathPatch(MplPath(OUTLINE), transform=ax_n.transData, facecolor="none", lw=0)
ax_n.add_patch(clip); im.set_clip_path(clip)
map_style(ax_n)
cmap = LinearSegmentedColormap.from_list("incl", ["#08306b", "#4292c6", "#c6dbef", "#f7f7f7"])
ax_r = AX(P2X + MW2 + GAP2, ROW_Y0, MW2, MH2, "map_rev")
ax_r.imshow(arr, extent=rev_ext, cmap=cmap, vmin=0, vmax=1, interpolation="nearest")
map_style(ax_r)
cx_n, cx_r = P2X + MW2 / 2, P2X + MW2 + GAP2 + MW2 / 2
T(cx_n, ROW_Y0 + MH2 + 0.06, "NLCD\nland cover", FS, ha="center", color=C_NLCD, fontweight="bold", linespacing=1.0)
T(cx_r, ROW_Y0 + MH2 + 0.06, "reV\nexclusions", FS, ha="center", color=C_REV, fontweight="bold", linespacing=1.0)
T(cx_n, ROW_Y0 + MH2 + 0.36, f"{EX['nlcd']:.0f} ac", FS, ha="center", color=C_NLCD)
T(cx_r, ROW_Y0 + MH2 + 0.36, f"{EX['lim']:.0f}–{EX['open']:.0f} ac", FS, ha="center", color=C_REV)
T(P2X + P2W / 2, ROW_Y0 + MH2 + 0.52, f"usable for solar, {EX['gross']:.0f} ac parcel", FS,
  ha="center", color=INK2)

# ---- Panel 3: national bars
P3X = 2.92
P3W = W - P3X - 0.05
ARROW(P2X + P2W + 0.05, P3X - 0.04, ROW_Y0 + MH2 / 2)
T(P3X, 0.07, "3  National usable area", FS_H, fontweight="bold")
T(P3X, 0.22, "million acres (wind: 2 turbine sizes)", FS, color=INK2)
TECH_W, SCN_W, VAL_W = 0.33, 0.57, 0.50
BAR_X = P3X + TECH_W + SCN_W
BAR_W = P3W - TECH_W - SCN_W - VAL_W
XMAX = 5.8
GROUP_GAP = 0.08
ROW_H = (BAND_Y - 0.06 - ROW_Y0 - GROUP_GAP) / 8
axb = AX(BAR_X, ROW_Y0, BAR_W, 8 * ROW_H + GROUP_GAP, "bars")
axb.set_xlim(0, XMAX)
total_h = 8 * ROW_H + GROUP_GAP
axb.set_ylim(total_h, 0)              # y in inches from panel top, downward
axb.axis("off")

wind_rng = {k: (min(WIND[t][k] for t in WIND), max(WIND[t][k] for t in WIND)) for k in ("lim", "ref", "open", "nlcd")}
groups = [("Solar", {k: (SOLAR[k], SOLAR[k]) for k in SOLAR}), ("Wind", wind_rng)]
scen = [("lim", "Limited", C_REV), ("ref", "Reference", C_REV), ("open", "Open", C_REV), ("nlcd", "NLCD", C_NLCD)]
BAR_PATCHES, VAL_TEXTS = [], []
for gi, (tech, d) in enumerate(groups):
    g0 = gi * (4 * ROW_H + GROUP_GAP)
    T(P3X, ROW_Y0 + g0 + 2 * ROW_H - 0.065, tech, FS, fontweight="bold")
    for si, (k, lab, col) in enumerate(scen):
        yc = g0 + (si + 0.5) * ROW_H
        lo, hi = d[k]
        T(P3X + TECH_W, ROW_Y0 + yc - 0.06, lab, FS, color=col)
        bh = ROW_H * 0.62
        rp = Rectangle((0, yc - bh / 2), lo, bh, facecolor=col, edgecolor="none")
        axb.add_patch(rp); BAR_PATCHES.append(rp)
        if hi > lo:
            rp2 = Rectangle((lo, yc - bh / 2), hi - lo, bh, facecolor=C_REV_L if col == C_REV else "#f1b77e",
                            edgecolor="none")
            axb.add_patch(rp2); BAR_PATCHES.append(rp2)
        s = f"{lo:.2f}" if hi == lo else f"{lo:.2f}–{hi:.2f}"
        vt = axb.text(hi + 0.12, yc, s, fontsize=FS, va="center", ha="left", color=col)
        VAL_TEXTS.append(vt)

# ---- takeaway band
fig.add_artist(Rectangle((0.04 / W, 1 - (H - 0.04) / H), (W - 0.08) / W, (H - 0.04 - BAND_Y) / H,
                         transform=fig.transFigure, facecolor=C_BG, edgecolor="none", zorder=-1))
T(W / 2, BAND_Y + 0.05, "Scenario choice matters more than method choice", FS_H, ha="center", fontweight="bold")
T(W / 2, BAND_Y + 0.20, "reV scenarios differ 5.8× (solar) and 10–19× (wind);  "
  "NLCD is 1.06–1.65× reV Reference", FS, ha="center")

# ---------------------------------------------------------------- checks
OUT = FIGURES / "graphical_abstract_v2"
fig.savefig(OUT.with_suffix(".pdf"))
fig.savefig(OUT.with_suffix(".png"), dpi=300)
rd = fig.canvas.get_renderer()
fb = fig.bbox
errs = []
alltexts = TEXTS + VAL_TEXTS
boxes = [(a.get_text(), a.get_window_extent(rd)) for a in alltexts]
for a, (s, bb) in zip(alltexts, boxes):
    if a.get_fontsize() < MIN_PT:
        errs.append(f"font {a.get_fontsize()} < {MIN_PT}: {s!r}")
    if bb.x0 < fb.x0 + 2 or bb.x1 > fb.x1 - 2 or bb.y0 < fb.y0 + 2 or bb.y1 > fb.y1 - 2:
        errs.append(f"out of bounds: {s!r}")
for i in range(len(boxes)):
    for j in range(i + 1, len(boxes)):
        if boxes[i][1].expanded(1.0, 1.0).padded(0.03 * fig.dpi).overlaps(boxes[j][1]):   # >= 0.03 in clearance
            errs.append(f"text overlap: {boxes[i][0]!r} / {boxes[j][0]!r}")
# text vs map axes and bars
for name, ax in AXES_BOXES:
    if name == "bars":
        continue
    abb = ax.get_window_extent(rd)
    for s, bb in boxes:
        if bb.overlaps(abb):
            errs.append(f"text over {name}: {s!r}")
for pch in BAR_PATCHES:
    pbb = pch.get_window_extent(rd)
    for s, bb in boxes:
        if bb.overlaps(pbb):
            errs.append(f"text over bar: {s!r}")
    for pch2 in BAR_PATCHES:
        if pch2 is not pch:
            q = pch2.get_window_extent(rd)
            if q.overlaps(pbb) and abs(q.y0 - pbb.y0) > 0.5:
                errs.append("bars from different rows overlap")
for a in ARROWS:
    abb = a.get_path().get_extents()     # drawn arrow geometry, display px (window extent adds padding)
    for s, bb in boxes:
        if bb.overlaps(abb):
            errs.append(f"arrow over text: {s!r}")
    for name, ax in AXES_BOXES:
        if abb.overlaps(ax.get_window_extent(rd)):
            errs.append(f"arrow over {name}: arrow x {abb.x0/fig.dpi:.3f}-{abb.x1/fig.dpi:.3f} in, "
                        f"axes x {ax.get_window_extent(rd).x0/fig.dpi:.3f}-{ax.get_window_extent(rd).x1/fig.dpi:.3f} in")
# panel 3 value labels must stay right of the bar column, inside figure
band_top_px = fb.y1 - BAND_Y * fig.dpi
for s, bb in boxes:
    if s.startswith(("Scenario", "reV scenarios")):
        if bb.y1 > band_top_px:
            errs.append(f"takeaway above band: {s!r}")
    elif bb.y0 < band_top_px:
        errs.append(f"panel text inside band: {s!r}")
from PIL import Image  # noqa: E402
px = Image.open(OUT.with_suffix(".png")).size
if px[0] < 1328 or px[1] < 531:
    errs.append(f"png too small {px}")
print(f"panel 1: {N_MFG_VIEW} manufacturing parcels (incl. exemplar) in view; view {V1_W:.0f} x {V1_H:.0f} m")
print(f"ASPECT {ASPECT:.3f} ROW_H {ROW_H:.3f} in  BAR_W {BAR_W:.2f} in  P3W {P3W:.2f} in")
print(f"size {W/CM:.1f} x {H/CM:.1f} cm, png {px[0]}x{px[1]} px, {len(boxes)} text items")
if errs:
    print("LAYOUT CHECK FAILED:\n  " + "\n  ".join(dict.fromkeys(errs)))
    sys.exit(1)
print("layout check: OK")
