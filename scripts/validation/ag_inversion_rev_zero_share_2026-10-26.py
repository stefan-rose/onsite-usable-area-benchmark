import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _config import BASE  # noqa: E402
import pandas as pd
B=str(BASE / "Scripts/method_comparison/outputs") + "/"
n=pd.read_csv(BASE / "Scripts/applied_energy_paper/outputs/nlcd_wind/nlcd_wind_percentage_plus_binary.csv",dtype={"PARCEL_LID":str},
   usecols=["PARCEL_LID","usable_area_nlcd_solar_ac","usable_area_nlcd_wind_ac"]).set_index("PARCEL_LID")
inv=n.index[n.usable_area_nlcd_wind_ac>n.usable_area_nlcd_solar_ac]
xs=(n.usable_area_nlcd_wind_ac-n.usable_area_nlcd_solar_ac)[inv].sum()
print("inversion parcels",len(inv),"excess Mac",round(xs/1e6,4))
for tag in ["","bespoke_115hh_170rd_grid90_","ge_80hh_77rd_"]:
    for s in ["reference","limited"]:
        d=pd.read_csv(f"{B}full_run_wind_{tag}{s}_2026_04_23/rev_full_population.csv",dtype={"PARCEL_LID":str},usecols=["PARCEL_LID","usable_area_rev_ac"]).set_index("PARCEL_LID").usable_area_rev_ac.fillna(0)
        print(f"{tag or 'old92m_'}{s:10s} zero% inversion={ (d[inv]<=0).mean()*100:.2f}  zero% all={(d<=0).mean()*100:.2f}")
