"""Count parcels with any usable area (>0) under each method/scenario.
Denominators:
  Solar: all 305,123 manufacturing parcels in CONUS.
  Wind: parcels >= 1 acre (paper's floor).
"""
import pandas as pd, glob
BASE = "/Users/rose501/OneDrive - PNNL/Desktop/IEDO/Scripts"
MC = f"{BASE}/method_comparison/outputs"
AE = f"{BASE}/applied_energy_paper/outputs"

nlcd = pd.read_csv(f"{AE}/nlcd_wind/nlcd_wind_percentage_only.csv",
                   usecols=["PARCEL_LID","SITE_STATE","acres",
                            "usable_area_nlcd_solar_ac","usable_area_nlcd_wind_ac"]).drop_duplicates("PARCEL_LID")
CONUS = set("AL AR AZ CA CO CT DE FL GA IA ID IL IN KS KY LA MA MD ME MI MN MO MS MT NC ND NE NH NJ NM NV NY OH OK OR PA RI SC SD TN TX UT VA VT WA WI WV WY DC".split())
nlcd = nlcd[nlcd.SITE_STATE.isin(CONUS)]

def load_rev(subdir, name):
    df = pd.concat([pd.read_csv(f, usecols=["PARCEL_LID","usable_area_rev_ac"])
                    for f in glob.glob(f"{MC}/{subdir}/rev_*.csv")], ignore_index=True)
    return df.drop_duplicates("PARCEL_LID").rename(columns={"usable_area_rev_ac": name})

df = nlcd.copy()
for scen in ["open","reference","limited"]:
    df = df.merge(load_rev(f"full_run_{scen}_2026_04_23", f"rev_{scen}_solar_ac"),
                  on="PARCEL_LID", how="left")
    df = df.merge(load_rev(f"full_run_wind_{scen}_2026_04_23", f"rev_{scen}_wind_ac"),
                  on="PARCEL_LID", how="left")

df = df[df.SITE_STATE.isin(CONUS)]
N = len(df)
wind_pop = df[df.acres >= 1.0]
Nw = len(wind_pop)
print(f"Solar denominator (all CONUS mfg parcels): N = {N:,}")
print(f"Wind denominator (parcels >= 1 ac):        N = {Nw:,}")
print()
print("SOLAR — parcels with any usable solar area (> 0):")
for col, label in [("usable_area_nlcd_solar_ac","NLCD 5-layer"),
                   ("rev_open_solar_ac","reV Open"),
                   ("rev_reference_solar_ac","reV Reference"),
                   ("rev_limited_solar_ac","reV Limited")]:
    n = (df[col].fillna(0) > 0).sum()
    print(f"  {label:20s}  {n:>7,}   ({n/N*100:5.1f}%)")
print()
print("WIND — parcels (>= 1 ac) with any usable wind area (> 0):")
for col, label in [("usable_area_nlcd_wind_ac","NLCD 5-layer"),
                   ("rev_open_wind_ac","reV Open"),
                   ("rev_reference_wind_ac","reV Reference"),
                   ("rev_limited_wind_ac","reV Limited")]:
    n = (wind_pop[col].fillna(0) > 0).sum()
    print(f"  {label:20s}  {n:>7,}   ({n/Nw*100:5.1f}%)")
print()
print("UNION — parcels with any usable area for solar OR wind (>0), under each method:")
# For union: use solar denom N; wind contribution needs the >=1ac restriction (else all wind vals are dropped)
for scen, sol_col, wind_col in [
    ("NLCD 5-layer","usable_area_nlcd_solar_ac","usable_area_nlcd_wind_ac"),
    ("reV Open","rev_open_solar_ac","rev_open_wind_ac"),
    ("reV Reference","rev_reference_solar_ac","rev_reference_wind_ac"),
    ("reV Limited","rev_limited_solar_ac","rev_limited_wind_ac"),
]:
    sol = df[sol_col].fillna(0) > 0
    # for wind, restrict to >=1ac parcels contributing
    wnd = (df.acres >= 1.0) & (df[wind_col].fillna(0) > 0)
    n = (sol | wnd).sum()
    print(f"  {scen:20s}  {n:>7,}   ({n/N*100:5.1f}%)")
