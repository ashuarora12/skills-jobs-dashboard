"""
Country-level analysis for the Data Finder guide (issue brief 1).
Inputs: World Bank Group Scorecard vision indicators (FY25 cycle).
Output: guide/output/guide_stats.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

HERE = Path(__file__).parent
RAW = HERE.parent / "data" / "raw"
OUT = HERE / "output"
OUT.mkdir(exist_ok=True)

SPECS = {  # key: (file, code, invert, label)
    "food": (RAW / "SN_ITK_MSFI_ZS.xlsx", "SN_ITK_MSFI_ZS", False, "Food & nutrition insecurity"),
    "hygiene": (RAW / "SH_H2O_STA_HYGN_TO.xlsx", "SH_STA_HYGN_ZS", True, "No basic hygiene"),
    "sanitation": (RAW / "SH_H2O_STA_HYGN_TO.xlsx", "SH_STA_BASS_ZS", True, "No basic sanitation"),
    "water": (RAW / "SH_H2O_STA_HYGN_TO.xlsx", "SH_H2O_BASW_ZS", True, "No basic drinking water"),
    "poverty": (RAW / "SI_POV_DDAY_TO.xlsx", "SI_POV_DDAY", False, "Poverty ($3.00/day)"),
    "climate": (RAW / "EN_CLM_VULN.xlsx", "EN_CLM_VULN", False, "High climate-hazard risk"),
}
cache = {}


def load(key, geo_type="ECONOMY"):
    f, code, inv, _ = SPECS[key]
    if f not in cache:
        cache[f] = pd.read_excel(f, sheet_name="Aggregates")
    d = cache[f]
    d = d[(d.Indicator_Code == code) & (d.Geography_Type == geo_type)].copy()
    d["t"] = d.Time_Period.astype(int)
    d = d[d.t >= 2015].sort_values("t").groupby("Geography_Code").tail(1)
    d["v"] = (100 - d.Value) if inv else d.Value
    d["v"] = d.v.clip(lower=0)
    return d.set_index("Geography_Code")[["Geography_Name", "v", "t"]]


country = {k: load(k) for k in SPECS}
names = pd.concat([v.Geography_Name for v in country.values()]).groupby(level=0).first()
wide = pd.DataFrame({k: v.v for k, v in country.items()})
years = pd.DataFrame({k: v.t for k, v in country.items()})

# ---- multiple-burden hotspots: top quartile on each of the five core risks (climate reported separately)
core = ["food", "hygiene", "sanitation", "water", "poverty"]
q75 = wide[core].quantile(0.75)
flags = (wide[core] >= q75) & wide[core].notna()
covered = wide[core].notna().sum(axis=1)
full = wide[covered == 5]
nflags = flags.loc[full.index].sum(axis=1)
hot = full.assign(n=nflags).sort_values(["n", "hygiene"], ascending=False)
hotspots = [{"iso": i, "name": names[i], "n": int(r.n), **{k: round(float(r[k]), 1) for k in core},
             "climate": None if pd.isna(wide.loc[i, "climate"]) else round(float(wide.loc[i, "climate"]), 1)}
            for i, r in hot.head(15).iterrows()]

# ---- association between poverty and each risk (Spearman, countries with both)
assoc = {}
for k in ["food", "hygiene", "sanitation", "water", "climate"]:
    d = wide[["poverty", k]].dropna()
    rho, p = spearmanr(d.poverty, d[k])
    assoc[k] = {"rho": round(float(rho), 2), "p": float(p), "n": int(len(d))}
scatter = [{"iso": i, "name": names[i], "x": round(float(r.poverty), 1), "y": round(float(r.hygiene), 1)}
           for i, r in wide[["poverty", "hygiene"]].dropna().iterrows()]

# ---- India vs South Asia vs world (vision aggregates use WDI-style region codes)
agg = {}
for k in SPECS:
    f, code, inv, _ = SPECS[k]
    d = cache[f]
    d = d[d.Indicator_Code == code].copy()
    d["t"] = d.Time_Period.astype(int)
    row = {}
    for g in ["IND", "SAS", "WLD"]:
        x = d[d.Geography_Code == g].sort_values("t")
        if len(x):
            v = x.Value.iloc[-1]
            row[g] = {"v": round(float(100 - v if inv else v), 1), "t": int(x.t.iloc[-1])}
    agg[k] = row

stats = {
    "labels": {k: v[3] for k, v in SPECS.items()},
    "n_countries": {k: int(wide[k].notna().sum()) for k in SPECS},
    "n_full": int(len(full)),
    "q75": {k: round(float(v), 1) for k, v in q75.items()},
    "hotspots": hotspots,
    "n_hot4plus": int((nflags >= 4).sum()), "n_hot5": int((nflags == 5).sum()),
    "hot4_names": [names[i] for i in nflags[nflags >= 4].index],
    "assoc": assoc, "scatter": scatter, "india": agg,
    "year_range": [int(years.min().min()), int(years.max().max())],
}
(OUT / "guide_stats.json").write_text(json.dumps(stats, indent=1))
print(json.dumps({k: stats[k] for k in ["n_countries", "n_full", "q75", "n_hot4plus", "n_hot5", "hot4_names", "assoc", "india", "year_range"]}, indent=1))
print([ (h["name"], h["n"]) for h in hotspots])
