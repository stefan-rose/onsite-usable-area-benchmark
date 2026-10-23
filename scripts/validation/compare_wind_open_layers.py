"""Sanity-check a new reV wind Open layer against the published one.

Read-only. Nothing in the pipeline uses this script's outputs.

Part A: whole-raster statistics for each layer, read in row strips:
  - valid-cell count and area
  - included area (sum of inclusion x cell area)
  - value histogram
Part B: point-wise comparison at cell centres of the OLD grid, sampled every
  STEP-th row and column. Each point is reprojected into the NEW layer's CRS
  and looked up there by nearest cell (no resampling). Reports:
  - agreement on zero / partial / one
  - mean difference and correlation
  - the 2-degree tiles with the largest change in included area

Usage: pixi run python -u scripts/validation/compare_wind_open_layers.py OLD NEW OUTDIR
"""
import sys, json
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import Window
from pyproj import Transformer

OLD, NEW, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)
STRIP = 512
STEP = 10
EDGES = [0, 1e-9, 0.25, 0.5, 0.75, 1 - 1e-9, 1.0 + 1e-6]
LABELS = ["0", "(0,0.25]", "(0.25,0.5]", "(0.5,0.75]", "(0.75,1)", "1"]


def valid(a, nod):
    m = np.isfinite(a)
    if nod is not None:
        m &= a != nod
    return m


def whole_stats(path):
    with rasterio.open(path) as r:
        cell = abs(r.res[0] * r.res[1])
        nod = r.nodata
        n = 0; s = 0.0; h = np.zeros(len(LABELS), dtype=np.int64)
        vmin, vmax = np.inf, -np.inf
        for row in range(0, r.height, STRIP):
            a = r.read(1, window=Window(0, row, r.width, min(STRIP, r.height - row)))
            v = a[valid(a, nod)].astype(np.float64)
            if v.size == 0:
                continue
            n += v.size; s += v.sum()
            vmin = min(vmin, v.min()); vmax = max(vmax, v.max())
            h += np.histogram(np.clip(v, 0, 1), bins=EDGES)[0]
    return dict(file=path.name, cell_m2=cell, valid_cells=int(n),
                valid_area_Mac=n * cell / 4046.8564224 / 1e6,
                included_area_Mac=s * cell / 4046.8564224 / 1e6,
                mean_inclusion=s / n, vmin=float(vmin), vmax=float(vmax),
                hist_share={k: float(c / n) for k, c in zip(LABELS, h)})


print("Part A: whole-raster statistics")
A = {k: whole_stats(p) for k, p in [("old", OLD), ("new", NEW)]}
for k, d in A.items():
    print(f"  {k}: {d['file']}")
    print(f"    valid area {d['valid_area_Mac']:,.1f} M ac | included {d['included_area_Mac']:,.1f} M ac "
          f"| mean {d['mean_inclusion']:.4f} | range [{d['vmin']:.3f}, {d['vmax']:.3f}]")
    print("    hist " + "  ".join(f"{k2}:{v*100:.2f}%" for k2, v in d['hist_share'].items()))

print(f"\nPart B: point-wise at every {STEP}th old-grid cell centre")
with rasterio.open(OLD) as ro, rasterio.open(NEW) as rn:
    tr = Transformer.from_crs(ro.crs, rn.crs, always_xy=True)
    to_ll = Transformer.from_crs(ro.crs, "EPSG:4326", always_xy=True)
    cols = np.arange(STEP // 2, ro.width, STEP)
    o_all, n_all, lon_all, lat_all = [], [], [], []
    for row in range(STEP // 2, ro.height, STEP):
        a = ro.read(1, window=Window(0, row, ro.width, 1))[0, cols]
        m = valid(a, ro.nodata)
        if not m.any():
            continue
        c = cols[m]; ov = a[m]
        x, y = ro.xy(np.full(c.size, row), c)
        xn, yn = tr.transform(np.asarray(x), np.asarray(y))
        rr, cc = rasterio.transform.rowcol(rn.transform, xn, yn)
        rr = np.asarray(rr); cc = np.asarray(cc)
        inb = (rr >= 0) & (rr < rn.height) & (cc >= 0) & (cc < rn.width)
        nv = np.full(c.size, np.nan, dtype=np.float32)
        if inb.any():
            # read the band of rows needed in the new raster
            r0, r1 = rr[inb].min(), rr[inb].max()
            band = rn.read(1, window=Window(0, r0, rn.width, r1 - r0 + 1))
            vals = band[rr[inb] - r0, cc[inb]].astype(np.float32)
            vals[~valid(vals, rn.nodata)] = np.nan
            nv[inb] = vals
        lon, lat = to_ll.transform(np.asarray(x), np.asarray(y))
        o_all.append(ov.astype(np.float32)); n_all.append(nv)
        lon_all.append(np.asarray(lon, dtype=np.float32)); lat_all.append(np.asarray(lat, dtype=np.float32))
o = np.concatenate(o_all); n = np.concatenate(n_all)
lon = np.concatenate(lon_all); lat = np.concatenate(lat_all)
both = np.isfinite(n)
print(f"  old valid points {o.size:,} | new valid at those points {both.sum():,} "
      f"({100*both.mean():.3f}%)")
o2, n2 = o[both], n[both]
cls = lambda v: np.where(v <= 1e-9, 0, np.where(v >= 1 - 1e-9, 2, 1))
co, cn = cls(o2), cls(n2)
conf = np.zeros((3, 3), dtype=np.int64)
np.add.at(conf, (co, cn), 1)
names = ["zero", "partial", "one"]
print("  confusion (rows old, cols new), share of points:")
for i in range(3):
    print(f"    {names[i]:8s} " + "  ".join(f"{names[j]}:{100*conf[i,j]/conf.sum():6.2f}%" for j in range(3)))
d = n2 - o2
B = dict(points=int(o.size), points_both_valid=int(both.sum()),
         mean_old=float(o2.mean()), mean_new=float(n2.mean()),
         mean_diff=float(d.mean()), mean_abs_diff=float(np.abs(d).mean()),
         share_exact_equal=float((np.abs(d) < 1e-6).mean()),
         share_absdiff_gt_0_5=float((np.abs(d) > 0.5).mean()),
         corr=float(np.corrcoef(o2, n2)[0, 1]),
         confusion=conf.tolist())
print(f"  mean old {B['mean_old']:.4f} | mean new {B['mean_new']:.4f} | mean diff {B['mean_diff']:+.4f} "
      f"| mean |diff| {B['mean_abs_diff']:.4f} | equal {100*B['share_exact_equal']:.1f}% "
      f"| |diff|>0.5 {100*B['share_absdiff_gt_0_5']:.2f}% | corr {B['corr']:.4f}")
missing_new = ~both
if missing_new.any():
    print(f"  points valid in old but nodata/outside in new: {missing_new.sum():,}; "
          f"old included share there {o[missing_new].sum()/o.sum()*100:.3f}% of old sampled inclusion")

# 2-degree tiles
tx = np.floor(lon[both] / 2) * 2; ty = np.floor(lat[both] / 2) * 2
key = tx * 1000 + ty
uk, inv = np.unique(key, return_inverse=True)
so = np.bincount(inv, weights=o2); sn = np.bincount(inv, weights=n2); cnt = np.bincount(inv)
tiles = sorted([dict(lon=float(k // 1000), lat=float(k % 1000 if k % 1000 < 500 else k % 1000 - 1000),
                     n=int(c), old_mean=float(a / c), new_mean=float(b / c), diff=float((b - a) / c))
                for k, a, b, c in zip(uk, so, sn, cnt) if c >= 500], key=lambda t: -abs(t["diff"]))
print("  2-degree tiles with largest change in mean inclusion (>=500 points):")
for t in tiles[:10]:
    print(f"    lon {t['lon']:+.0f}..{t['lon']+2:+.0f} lat {t['lat']:.0f}..{t['lat']+2:.0f} n={t['n']:6d} "
          f"old {t['old_mean']:.3f} new {t['new_mean']:.3f} diff {t['diff']:+.3f}")
json.dump(dict(A=A, B=B, top_tiles=tiles[:25]), open(OUT / "compare_wind_open_layers.json", "w"), indent=1)
np.savez_compressed(OUT / "points.npz", lon=lon, lat=lat, old=o, new=n)
print(f"\nWrote {OUT}")
