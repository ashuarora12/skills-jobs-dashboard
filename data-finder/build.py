"""
Build the Health Economics Data Finder page (site/data-buff.html).

Inputs
  datasets.json                         hand-curated dataset catalogue (each entry: status + evidence link)
  ../who-benefits/data/raw/*.xlsx       World Bank Group Scorecard vision indicators (country level)
  ../site/patent-dashboard.html   world map paths (Natural Earth via world-atlas)

Run: python3 build.py
"""
import json
import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
SITE = HERE.parent / "site"
RAW = HERE.parent / "who-benefits" / "data" / "raw"

cat = json.loads((HERE / "datasets.json").read_text())

# ------------------------------------------------------------------ world map paths (rounded)
src = (SITE / "patent-dashboard.html").read_text()
i = src.index("const MAP = ") + len("const MAP = ")
world, _ = json.JSONDecoder().raw_decode(src[i:])
def simplify(d):
    """Round to whole pixels (the map is drawn 960 px wide) and drop repeated points."""
    d = re.sub(r"-?\d+\.\d+", lambda m: str(round(float(m.group()))), d)
    out, prev = [], None
    for tok in re.findall(r"[MLZmlz]|-?\d+,-?\d+", d):
        if tok == prev and "," in tok:
            continue
        out.append(tok); prev = tok
    return "".join(out)


paths = {k: {"name": v["name"], "d": simplify(v["d"])} for k, v in world["countries"].items()}

# ------------------------------------------------------------------ hotspot metrics (latest year >= 2015)
METRICS = [
    # key, file, indicator code, label, invert (100 - value), unit note, datasets that measure it
    ("food", "SN_ITK_MSFI_ZS.xlsx", "SN_ITK_MSFI_ZS", "Food & nutrition insecurity", False, "% of people facing food and nutrition insecurity", ["nfhs", "dhs", "mics", "gbd"]),
    ("hygiene", "SH_H2O_STA_HYGN_TO.xlsx", "SH_STA_HYGN_ZS", "No basic hygiene services", True, "% of people without basic hygiene services (100 − access)", ["nfhs", "dhs", "mics", "gho"]),
    ("sanitation", "SH_H2O_STA_HYGN_TO.xlsx", "SH_STA_BASS_ZS", "No basic sanitation", True, "% of people without basic sanitation services (100 − access)", ["nfhs", "dhs", "mics", "gho"]),
    ("water", "SH_H2O_STA_HYGN_TO.xlsx", "SH_H2O_BASW_ZS", "No basic drinking water", True, "% of people without basic drinking-water services (100 − access)", ["nfhs", "dhs", "mics", "gho"]),
    ("poverty", "SI_POV_DDAY_TO.xlsx", "SI_POV_DDAY", "Extreme poverty ($3.00/day)", False, "% of people living below $3.00 a day (2021 PPP)", ["hces", "lsms", "wdi"]),
]
cache, metrics = {}, []
for key, f, code, label, inv, unit, ds in METRICS:
    if f not in cache:
        cache[f] = pd.read_excel(RAW / f, sheet_name="Aggregates")
    d = cache[f]
    d = d[(d.Indicator_Code == code) & (d.Geography_Type == "ECONOMY")].copy()
    d["t"] = d.Time_Period.astype(int)
    d = d[d.t >= 2015].sort_values("t").groupby("Geography_Code").tail(1)
    vals = {}
    for r in d.itertuples():
        v = 100 - r.Value if inv else r.Value
        vals[r.Geography_Code] = [round(float(max(0, v)), 1), int(r.t), r.Geography_Name]
    metrics.append({"key": key, "label": label, "unit": unit, "datasets": ds, "values": vals,
                    "n": len(vals), "on_map": sum(1 for k in vals if k in paths)})
    print(f"{key:10s} countries {len(vals):3d}  on map {metrics[-1]['on_map']}")

payload = {"catalogue": cat, "metrics": metrics,
           "map": {"w": world["width"], "h": world["height"], "paths": paths}}
data = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
tpl = (HERE / "template.html").read_text()
assert "/*__DATA__*/null" in tpl
out = SITE / "data-buff.html"
out.write_text(tpl.replace("/*__DATA__*/null", data))
print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)")
