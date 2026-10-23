"""Central path configuration for the onsite-usable-area-benchmark pipeline.

Reads ``config.toml`` at the repo root if present, otherwise falls back to
``config.example.toml``. Exposes ``BASE`` (external data root) plus resolved
Path objects for every input dataset referenced by the pipeline scripts.

Usage from a script::

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _config import BASE, PARCELS_WORKING_GPKG, REV_SOLAR, OUTPUTS

Every path is either absolute (used verbatim) or relative to ``paths.base``
(joined against BASE). Repo-local paths (``paths.intermediate``,
``paths.outputs``, ``paths.figures``) are resolved against the repo root
rather than against BASE.
"""
from __future__ import annotations

from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# Resolve config file (config.toml preferred; falls back to config.example.toml)
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
_CONFIG_TOML = _REPO_ROOT / "config.toml"
_CONFIG_EXAMPLE = _REPO_ROOT / "config.example.toml"

_ACTIVE_CONFIG = _CONFIG_TOML if _CONFIG_TOML.exists() else _CONFIG_EXAMPLE

with open(_ACTIVE_CONFIG, "rb") as _f:
    _cfg = tomllib.load(_f)


# ---------------------------------------------------------------------------
# Path resolution helpers
# ---------------------------------------------------------------------------
BASE = Path(_cfg["paths"]["base"]).expanduser()


def _base_rel(p: str) -> Path:
    """Resolve *p* against BASE if it is not already absolute."""
    pp = Path(p).expanduser()
    return pp if pp.is_absolute() else BASE / pp


def _repo_rel(p: str) -> Path:
    """Resolve *p* against the repo root if it is not already absolute."""
    pp = Path(p).expanduser()
    return pp if pp.is_absolute() else _REPO_ROOT / pp


# ---------------------------------------------------------------------------
# Repo-local working directories
# ---------------------------------------------------------------------------
INTERMEDIATE = _repo_rel(_cfg["paths"]["intermediate"])
OUTPUTS = _repo_rel(_cfg["paths"]["outputs"])
FIGURES = _repo_rel(_cfg["paths"]["figures"])

# Ensure they exist so scripts can write without extra ceremony.
for _d in (INTERMEDIATE, OUTPUTS, FIGURES):
    _d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Parcel universe inputs
# ---------------------------------------------------------------------------
PARCELS_SOURCE_GPKG = _base_rel(_cfg["inputs"]["parcels"]["source_gpkg"])
PARCELS_WORKING_GPKG = _base_rel(_cfg["inputs"]["parcels"]["working_gpkg"])
FACILITY_CSV = _base_rel(_cfg["inputs"]["parcels"]["facility_csv"])


# ---------------------------------------------------------------------------
# reV composite exclusion rasters (NLR)
# ---------------------------------------------------------------------------
REV_SOLAR: dict[str, Path] = {
    "open": _base_rel(_cfg["inputs"]["rev_solar"]["open"]),
    "reference": _base_rel(_cfg["inputs"]["rev_solar"]["reference"]),
    "limited": _base_rel(_cfg["inputs"]["rev_solar"]["limited"]),
    "parcel_joined": _base_rel(_cfg["inputs"]["rev_solar"]["parcel_joined"]),
}
REV_WIND: dict[str, Path] = {
    "open": _base_rel(_cfg["inputs"]["rev_wind"]["open"]),
    "reference": _base_rel(_cfg["inputs"]["rev_wind"]["reference"]),
    "limited": _base_rel(_cfg["inputs"]["rev_wind"]["limited"]),
}

# Wind turbine configurations keyed by turbine id. The headline 115/170
# layers ([inputs.rev_wind]) are always present as "bespoke_115hh_170rd";
# additional configurations come from [inputs.rev_wind_turbines.<id>].
_ws = _cfg.get("wind_spec", {})
REV_WIND_TURBINES: dict[str, dict] = {
    "bespoke_115hh_170rd": {
        "hub_height_m": _ws.get("hub_height_m", 115),
        "rotor_diameter_m": _ws.get("rotor_diameter_m", 170),
        "scenarios": dict(REV_WIND),
    }
}
for _tid, _t in _cfg["inputs"].get("rev_wind_turbines", {}).items():
    REV_WIND_TURBINES[_tid] = {
        "hub_height_m": _t["hub_height_m"],
        "rotor_diameter_m": _t["rotor_diameter_m"],
        "scenarios": {
            _s: _base_rel(_t[_s]) for _s in ("open", "reference", "limited") if _s in _t
        },
    }


# ---------------------------------------------------------------------------
# NLCD (via Google Earth Engine)
# ---------------------------------------------------------------------------
NLCD_GEE_DIR = _base_rel(_cfg["inputs"]["nlcd"]["gee_extract_dir"])


# ---------------------------------------------------------------------------
# Wind binary exclusion layers
# ---------------------------------------------------------------------------
WIND_BINARY: dict[str, Path] = {
    "airports": _base_rel(_cfg["inputs"]["wind_binary"]["airports_hifld"]),
    "dod_airspace": _base_rel(_cfg["inputs"]["wind_binary"]["dod_airspace"]),
    "critical_habitat": _base_rel(_cfg["inputs"]["wind_binary"]["critical_habitat"]),
    "urban_areas": _base_rel(_cfg["inputs"]["wind_binary"]["urban_areas"]),
    "nwi_flags": _base_rel(_cfg["inputs"]["wind_binary"]["nwi_flags"]),
    "slope_flags": _base_rel(_cfg["inputs"]["wind_binary"]["slope_flags"]),
}


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------
CRS = _cfg["projection"]["crs"]


__all__ = [
    "BASE",
    "INTERMEDIATE",
    "OUTPUTS",
    "FIGURES",
    "PARCELS_SOURCE_GPKG",
    "PARCELS_WORKING_GPKG",
    "FACILITY_CSV",
    "REV_SOLAR",
    "REV_WIND",
    "REV_WIND_TURBINES",
    "NLCD_GEE_DIR",
    "WIND_BINARY",
    "CRS",
]
