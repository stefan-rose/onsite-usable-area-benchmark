"""Count parcels where reV wind Limited usable area exceeds Reference (per turbine, 90 m grid)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _config import BASE  # noqa: E402

import pandas as pd
B=str(BASE / "Scripts/method_comparison/outputs") + "/"
rd=lambda p: pd.read_csv(B+p,dtype={"PARCEL_LID":str},usecols=["PARCEL_LID","usable_area_rev_ac"]).set_index("PARCEL_LID").usable_area_rev_ac.fillna(0)
for tag in ["bespoke_115hh_170rd_grid90_","ge_80hh_77rd_",""]:
    r=rd(f"full_run_wind_{tag}reference_2026_04_23/rev_full_population.csv"); l=rd(f"full_run_wind_{tag}limited_2026_04_23/rev_full_population.csv").reindex(r.index).fillna(0)
    m=l>r+1e-9
    print(f"{tag or 'old92m_'}: Lim>Ref parcels={m.sum()}  Lim ac on them={l[m].sum():,.0f}  Ref ac on them={r[m].sum():,.0f}  excess={(l-r)[m].sum():,.0f}  of Lim total {l.sum():,.0f}")
