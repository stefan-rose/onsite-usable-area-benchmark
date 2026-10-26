import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _config import BASE  # noqa: E402
import pandas as pd
B=str(BASE / "Scripts/method_comparison/outputs") + "/"
rd=lambda p: pd.read_csv(B+p,dtype={"PARCEL_LID":str},usecols=["PARCEL_LID","usable_area_rev_ac"]).set_index("PARCEL_LID").usable_area_rev_ac.fillna(0)
for s in ["open","reference","limited"]:
    sol=rd(f"full_run_{s}_2026_04_23/rev_full_population.csv")
    for tag in ["bespoke_115hh_170rd_grid90_","ge_80hh_77rd_"]:
        w=rd(f"full_run_wind_{tag}{s}_2026_04_23/rev_full_population.csv").reindex(sol.index).fillna(0)
        m=w>sol+1e-9
        print(f"{s:9s} {tag[:12]:12s} reV wind>solar parcels={m.sum():6d} ({m.mean()*100:.2f}%) excess Mac={(w-sol)[m].sum()/1e6:.4f}")
n=pd.read_csv(BASE / "Scripts/applied_energy_paper/outputs/nlcd_wind/nlcd_wind_percentage_plus_binary.csv",dtype={"PARCEL_LID":str},usecols=["PARCEL_LID","usable_area_nlcd_solar_ac","usable_area_nlcd_wind_ac"]).set_index("PARCEL_LID")
inv=set(n.index[n.usable_area_nlcd_wind_ac>n.usable_area_nlcd_solar_ac])
for s in ["open","reference"]:
    sol=rd(f"full_run_{s}_2026_04_23/rev_full_population.csv")
    w=rd(f"full_run_wind_bespoke_115hh_170rd_grid90_{s}_2026_04_23/rev_full_population.csv").reindex(sol.index).fillna(0)
    R=set(sol.index[w>sol+1e-9]); print(s,"overlap with NLCD inversion set:",len(R&inv),"of",len(R))
# old 92 m layer for provenance
sol=rd("full_run_open_2026_04_23/rev_full_population.csv"); w=rd("full_run_wind_open_2026_04_23/rev_full_population.csv").reindex(sol.index).fillna(0)
print("old 92m open wind>solar:",(w>sol+1e-9).sum())
