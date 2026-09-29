"""
Who Benefits? Health, Jobs & Gender in the World Bank Group portfolio.

Builds every number shown on site/who-benefits.html
from the World Bank Group Scorecard exports in data/raw/ and writes
output/dashboard_data.json (which build_page.py embeds into the page).

Run:  python3 pipeline.py && python3 build_page.py

Sources (downloaded from https://scorecard.worldbank.org, FY25 cycle,
results as of 30 June 2025):
  CSC_RES_HEA_SERV        people receiving quality health, nutrition & population services
  CSC_RES_WAT_SAN_HYG_TOT people provided with water, sanitation and/or hygiene
  CSC_RES_GEN_EQU_BENE    people benefiting from actions to advance gender equality /
                          expand economic opportunities
  CSC_RES_FIN_SERV_WOM    people & businesses using financial services (incl. women)
  CSC_RES_HEA_EMER_BENE   economies with strengthened health-emergency capacity
  SI_POV_DDAY_TO, SI_POV_PROS, SN_ITK_MSFI_ZS, SH_H2O_STA_HYGN_TO  (Scorecard "vision" context)
"""
import json
import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, balanced_accuracy_score, brier_score_loss
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
RNG = np.random.default_rng(20250630)
LAST = {}  # internals kept for report_stats.py
HERE = Path(__file__).parent
RAW = HERE / "data" / "raw"
OUT = HERE / "output"
OUT.mkdir(exist_ok=True)

RESULT_FILES = {
    "HEALTH": "CSC_RES_HEA_SERV.xlsx",
    "WASH": "CSC_RES_WAT_SAN_HYG_TOT.xlsx",
    "GENDER": "CSC_RES_GEN_EQU_BENE.xlsx",
    "FIN": "CSC_RES_FIN_SERV_WOM.xlsx",
}
# results-region code -> (display name, Scorecard "vision" region code)
REGIONS = {
    "AFE": ("Eastern & Southern Africa", "AFE"),
    "AFW": ("Western & Central Africa", "AFW"),
    "EAP": ("East Asia & Pacific", "EAS"),
    "ECA": ("Europe & Central Asia", "ECS"),
    "LCR": ("Latin America & Caribbean", "LCN"),
    "MENAAP": ("Middle East, N. Africa, Afghanistan & Pakistan", "MEA"),
    "SAR": ("South Asia", "SAS"),
}
# "ACW" in the results files is labelled "All Countries": the seven regions sum to it.
ALL = "ACW"
SUBS = {
    "CSC_RES_HEA_SERV": "Health, nutrition & population services",
    "CSC_RES_WAT_SAN_HYG": "Water, sanitation and/or hygiene",
    "CSC_RES_GEN_EQU": "Actions advancing gender equality",
    "CSC_RES_BENE_ENAB_ECO_OPP": "Actions expanding economic opportunity",
    "CSC_RES_FIN_SERV": "Financial services users",
}


def num(s):
    """Scorecard uses 'ND' (no data) strings inside numeric columns."""
    return pd.to_numeric(s, errors="coerce")


def r(x, n=1):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), n)


# ---------------------------------------------------------------- 1. regional results
def load_aggregates():
    frames = []
    for f in list(RESULT_FILES.values()) + ["CSC_RES_HEA_EMER_BENE.xlsx"]:
        d = pd.read_excel(RAW / f, sheet_name="Aggregates")
        frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    d["sub"] = d.Sub_Indicator_Code.fillna(d.Indicator_Code)
    d["A"] = num(d.Achieved_Results)
    d["E"] = num(d.Expected_Results)
    # WBG-wide figures; "Total" disability flag = all projects (the "Yes" rows are a subset)
    return d[(d.Organization_Code == "WBG") & (d.Disability_Inclusive_Flag == "Total")]


def regional_results(agg):
    out = {}
    geo = agg[agg.Geography_Code.isin(list(REGIONS) + [ALL])]
    for sub in list(SUBS) + ["CSC_RES_FIN_SERV_WOM_CUS", "CSC_RES_HEA_EMER_BENE"]:
        s = geo[geo["sub"] == sub]
        block = {}
        for code in list(REGIONS) + [ALL]:
            row = {}
            for demo in ["Total", "Female", "Youth"]:
                x = s[(s.Geography_Code == code) & (s.Demographic_Disaggregation == demo)]
                if len(x):
                    row[demo] = {"achieved": r(x.A.iloc[0], 0), "expected": r(x.E.iloc[0], 0)}
            block[code] = row
        out[sub] = block
    # check: regions sum to the "All Countries" row
    s = geo[(geo["sub"] == "CSC_RES_HEA_SERV") & (geo.Demographic_Disaggregation == "Total")]
    reg_sum = s[s.Geography_Code.isin(REGIONS)].A.sum()
    all_val = s[s.Geography_Code == ALL].A.iloc[0]
    assert abs(reg_sum - all_val) / all_val < 0.001, (reg_sum, all_val)
    return out


def vision_context():
    files = {
        "pov3": ("SI_POV_DDAY_TO.xlsx", "SI_POV_DDAY"),
        "pov83": ("SI_POV_DDAY_TO.xlsx", "SI_POV_UMIC"),
        "prosgap": ("SI_POV_PROS.xlsx", "SI_POV_PROS"),
        "food": ("SN_ITK_MSFI_ZS.xlsx", "SN_ITK_MSFI_ZS"),
        "hygiene": ("SH_H2O_STA_HYGN_TO.xlsx", "SH_STA_HYGN_ZS"),
        "sanitation": ("SH_H2O_STA_HYGN_TO.xlsx", "SH_STA_BASS_ZS"),
        "water": ("SH_H2O_STA_HYGN_TO.xlsx", "SH_H2O_BASW_ZS"),
    }
    cache, out = {}, {}
    codes = {k: v[1] for k, v in REGIONS.items()}
    codes[ALL] = "WLD"
    for key, (f, ind) in files.items():
        if f not in cache:
            cache[f] = pd.read_excel(RAW / f, sheet_name="Aggregates")
        d = cache[f]
        d = d[d.Indicator_Code == ind]
        out[key] = {}
        for rc, vc in codes.items():
            x = d[d.Geography_Code == vc].copy()
            x["t"] = x.Time_Period.astype(int)
            x = x.sort_values("t")
            if len(x):
                out[key][rc] = {"value": r(x.Value.iloc[-1], 1), "year": int(x.t.iloc[-1])}
    return out


# ---------------------------------------------------------------- project-level data
def load_projects():
    frames = []
    for k, f in RESULT_FILES.items():
        p = pd.read_excel(RAW / f, sheet_name="WB Project Information")
        p["file"] = k
        frames.append(p)
    p = pd.concat(frames, ignore_index=True)
    p["sub"] = p.sub_indicator_code.fillna(p.indicator_code)
    # the same project-indicator row can appear in more than one export
    p = p.drop_duplicates(subset=[c for c in p.columns if c != "file"])
    p["A"] = num(p.Achieved_Results)
    p["E"] = num(p.Expected_Results)
    return p


# ---------------------------------------------------------------- 2. text classifier
THEMES = {
    "health_workforce": {
        "label": "Health workforce",
        # v1 also matched "deliveries attended by skilled health personnel" (a service-coverage
        # indicator, not a workforce measure); v2 requires the workers themselves to be the object.
        "patterns": [r"health (care )?workers?", r"\bnurses?\b", r"\bmidwives\b", r"\bmidwife\b(?!-attended)",
                     r"community health (volunteers?|agents?|promoters?)", r"\bdoctors?\b",
                     r"(train|recruit|deploy|hir)\w*[^|]{0,40}health (personnel|staff|professionals?|providers?)",
                     r"health (personnel|staff|professionals?|providers?)[^|]{0,30}(trained|recruited|deployed)",
                     r"health extension workers?"],
    },
    "jobs_skills": {
        "label": "Jobs & skills training",
        "patterns": [r"\bjobs?\b", r"employment", r"employab", r"(vocational|technical|skills?) training",
                     r"\btvet\b", r"apprentice", r"\bskills?\b", r"labou?r market", r"trained in"],
    },
    "migration": {
        "label": "Migration & displacement",
        "patterns": [r"migra(nt|nts|tion)", r"refugees?", r"displaced", r"\bidps?\b", r"host communit",
                     r"labou?r mobility", r"returnees?", r"remittance"],
    },
    "women_econ": {
        "label": "Women's economic empowerment",
        "patterns": [r"women[- ]owned", r"women[- ]led", r"female[- ]owned", r"female[- ]led",
                     r"women entrepreneurs?", r"women'?s economic", r"(women|female) (farmers|producers)",
                     r"women'?s (employment|income|livelihood)"],
    },
    "care_economy": {
        "label": "Childcare & care economy",
        # v1 matched "care services", which caught "primary health care services"
        "patterns": [r"child ?care", r"day ?care", r"care economy", r"\bcreches?\b",
                     r"early childhood (development|education|care)", r"care ?givers?", r"(?<!health )(?<!health)care work(?!ers)"],
    },
    "menstrual": {
        "label": "Menstrual health & hygiene",
        "patterns": [r"menstrua", r"\bmhm\b", r"sanitary (pads?|napkins?|products?)"],
    },
}


def project_text(p):
    g = p.groupby("Project_ID")
    txt = g.apply(lambda x: " | ".join(
        pd.unique(pd.concat([x.Project_Development_Objective, x.Project_Indicator,
                             x.Project_Indicator_Description]).dropna().astype(str))))
    meta = g.agg(name=("Project_Name", "first"), country=("CountryEconomy_Name", "first"),
                 region=("WB_Region", "first"), fcv=("FCV_Flag", "first"),
                 income=("Income_Group", "first"), dept=("Global_Department", "first"),
                 status=("Project_Status", "first"), commit=("Net_Commitment_Total", "first"),
                 approval=("Approval_Date", "first"))
    meta["text"] = txt
    return meta


def snippet(text, m, width=70):
    a, b = max(0, m.start() - width), min(len(text), m.end() + width)
    return ("…" if a else "") + text[a:b].strip() + ("…" if b < len(text) else "")


def classify(meta):
    rows, hits = [], {k: [] for k in THEMES}
    for pid, row in meta.iterrows():
        text = re.sub(r"\s+", " ", row.text)
        low = text.lower()
        themes = {}
        for key, t in THEMES.items():
            for pat in t["patterns"]:
                m = re.search(pat, low)
                if m:
                    themes[key] = snippet(text, m)
                    hits[key].append(pid)
                    break
        rows.append({
            "id": pid, "name": row["name"], "country": row.country, "region": row.region,
            "fcv": row.fcv == "Y", "status": row.status, "dept": row.dept,
            "themes": list(themes), "evidence": themes,
        })
    return rows, hits


def validation_sample(rows, n=12):
    """Random sample of matches per theme for manual precision review."""
    path = HERE / "validation" / "theme_review.csv"
    by_theme = {k: [x for x in rows if k in x["themes"]] for k in THEMES}
    if not path.exists():
        path.parent.mkdir(exist_ok=True)
        recs = []
        for k, lst in by_theme.items():
            idx = RNG.choice(len(lst), size=min(n, len(lst)), replace=False)
            for i in idx:
                x = lst[i]
                recs.append({"theme": k, "project_id": x["id"], "project": x["name"],
                             "evidence": x["evidence"][k], "correct": ""})
        pd.DataFrame(recs).to_csv(path, index=False)
    rev = pd.read_csv(path, dtype={"correct": str})
    v1_path = HERE / "validation" / "theme_review_v1.csv"
    v1 = pd.read_csv(v1_path, dtype={"correct": str}) if v1_path.exists() else None
    res = {}
    for k in THEMES:
        x = rev[(rev.theme == k) & rev.correct.isin(["1", "0"])]
        res[k] = {"reviewed": int(len(x)), "correct": int((x.correct == "1").sum()),
                  "precision": r(x.correct.astype(int).mean(), 2) if len(x) else None}
        if v1 is not None:
            y = v1[(v1.theme == k) & v1.correct.isin(["1", "0"])]
            res[k]["v1_precision"] = r(y.correct.astype(int).mean(), 2) if len(y) else None
    return res


# ---------------------------------------------------------------- 3. delivery-gap model
def delivery_frame(p):
    t = p[(p.Demographic_Disaggregation == "Total") & (p.Double_Counting_Flag == "N")]
    g = t.groupby(["Project_ID", "sub"]).agg(
        A=("A", "sum"), E=("E", "sum"), approval=("Approval_Date", "first"),
        closing=("Closing_Date", "first"), progress=("Progress_Date", "max"),
        region=("WB_Region", "first"), fcv=("FCV_Flag", "first"), income=("Income_Group", "first"),
        instrument=("Lending_Instrument", "first"), dept=("Global_Department", "first"),
        agreement=("Agreement_Type", "first"), commit=("Net_Commitment_Total", "first"),
        status=("Project_Status", "first"), ldc=("LDC_Flag", "first"),
        name=("Project_Name", "first")).reset_index()
    g = g[(g.E > 0) & g.approval.notna() & g.closing.notna() & g.progress.notna()]
    span = (g.closing - g.approval).dt.days.clip(lower=30)
    g["elapsed"] = ((g.progress - g.approval).dt.days / span).clip(0, 1)
    g["ratio"] = (g.A / g.E).clip(lower=0)
    # behind schedule: share of the target delivered is below the share of the
    # implementation period that has passed (with a 10-point tolerance)
    g["behind"] = (g.ratio < g.elapsed - 0.10).astype(int)
    g["log_commit"] = np.log10(g.commit.clip(lower=1e5))
    g["years_since_approval"] = (pd.Timestamp("2025-06-30") - g.approval).dt.days / 365.25
    g = g[g.elapsed >= 0.2]  # too early to judge
    return g


def fit_delivery_model(g):
    cat = ["region", "income", "instrument", "dept", "agreement", "sub", "status"]
    top_dept = g.dept.value_counts().index[:10]
    g = g.assign(dept=np.where(g.dept.isin(top_dept), g.dept, "Other"))
    X = pd.get_dummies(g[cat], drop_first=False).astype(float)
    X["fcv"] = (g.fcv == "Y").astype(float)
    X["ldc"] = (g.ldc == "Y").astype(float)
    X["log_commit"] = g.log_commit
    X["elapsed"] = g.elapsed
    X["years_since_approval"] = g.years_since_approval
    y = g.behind.values
    groups = g.Project_ID.values
    models = {
        "logit": make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=2000)),
        "gbm": HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=300,
                                              l2_regularization=1.0, random_state=0),
    }
    cv = GroupKFold(n_splits=5)
    res = {}
    for name, m in models.items():
        pred = np.zeros(len(y))
        for tr, te in cv.split(X, y, groups):
            m.fit(X.iloc[tr], y[tr])
            pred[te] = m.predict_proba(X.iloc[te])[:, 1]
        res[name] = {"auc": r(roc_auc_score(y, pred), 3),
                     "bal_acc": r(balanced_accuracy_score(y, pred > 0.5), 3),
                     "brier": r(brier_score_loss(y, pred), 3), "pred": pred}
    best = max(res, key=lambda k: res[k]["auc"])
    pred = res[best]["pred"]
    LAST["delivery"] = {"X": X, "y": y, "groups": groups, "g": g, "preds": {k: v["pred"] for k, v in res.items()}, "best": best}

    # fairness / robustness: performance by subgroup (out-of-fold predictions)
    def subgroup(col, labels=None):
        out = []
        for v, idx in g.groupby(col).groups.items():
            ii = g.index.get_indexer(idx)
            yy, pp = y[ii], pred[ii]
            if len(ii) < 25 or yy.min() == yy.max():
                continue
            out.append({"group": labels.get(v, v) if labels else str(v), "n": int(len(ii)),
                        "behind_rate": r(yy.mean(), 3), "predicted_rate": r(pp.mean(), 3),
                        "auc": r(roc_auc_score(yy, pp), 3),
                        "fnr": r(((pp <= 0.5) & (yy == 1)).sum() / max(1, (yy == 1).sum()), 3)})
        return out

    fairness = {
        "region": subgroup("region", {k: v[0] for k, v in REGIONS.items()}),
        "fcv": subgroup("fcv", {"Y": "Fragile & conflict-affected", "N": "Not FCV"}),
        "income": subgroup("income"),
    }

    # permutation importance on the best model, fit on all data, grouped by original variable
    m = models[best].fit(X, y)
    pi = permutation_importance(m, X, y, scoring="roc_auc", n_repeats=10, random_state=0)
    imp = pd.Series(pi.importances_mean, index=X.columns)
    groups_map = {}
    for c in X.columns:
        base = next((k for k in cat if c.startswith(k + "_")), c)
        groups_map[c] = base
    imp = imp.groupby(groups_map).sum().sort_values(ascending=False)
    names = {"elapsed": "Share of implementation period elapsed", "years_since_approval": "Years since approval",
             "log_commit": "Project size (log commitment)", "dept": "Lead global department",
             "region": "Region", "income": "Country income group", "fcv": "Fragile/conflict setting",
             "sub": "Type of result (indicator)", "instrument": "Lending instrument",
             "agreement": "IDA / IBRD financing", "status": "Active vs. closed", "ldc": "Least developed country"}
    # calibration by decile
    cal = pd.DataFrame({"p": pred, "y": y})
    cal["bin"] = pd.qcut(cal.p, 10, labels=False, duplicates="drop")
    cal = cal.groupby("bin").agg(pred=("p", "mean"), obs=("y", "mean"), n=("y", "size"))
    by_dept = (g.assign(y=y).groupby("dept").agg(n=("y", "size"), rate=("y", "mean"))
               .query("n >= 30").sort_values("rate"))
    age_bins = pd.cut(g.years_since_approval, [0, 3, 5, 7, 100], labels=["< 3 yrs", "3–5 yrs", "5–7 yrs", "7+ yrs"])
    by_age = g.assign(y=y, b=age_bins).groupby("b", observed=True).agg(n=("y", "size"), rate=("y", "mean"))
    return {
        "n": int(len(y)), "projects": int(pd.Series(groups).nunique()),
        "behind_rate": r(y.mean(), 3), "best": best,
        "models": {k: {kk: vv for kk, vv in v.items() if kk != "pred"} for k, v in res.items()},
        "importance": [{"feature": names.get(k, k), "value": r(v, 4)} for k, v in imp.items() if v > 0][:8],
        "fairness": fairness,
        "calibration": [{"pred": r(a, 3), "obs": r(b, 3), "n": int(c)} for a, b, c in cal.values],
        "by_dept": [{"dept": k, "n": int(v.n), "rate": r(v.rate, 3)} for k, v in by_dept.iterrows()],
        "by_age": [{"bin": str(k), "n": int(v.n), "rate": r(v.rate, 3)} for k, v in by_age.iterrows()],
    }


# ---------------------------------------------------------------- 4. gender delivery gap + matching
def gender_gap(p):
    q = p[p.Double_Counting_Flag == "N"].copy()
    f = q.Progress_Disaggregation_Factor
    q["imputed"] = (f > 0) & (f < 1)
    F = q[q.Demographic_Disaggregation == "Female"].groupby(["Project_ID", "sub"]).agg(
        AF=("A", "sum"), EF=("E", "sum"), imputed=("imputed", "max"))
    T = q[q.Demographic_Disaggregation == "Total"].groupby(["Project_ID", "sub"]).agg(
        AT=("A", "sum"), ET=("E", "sum"))
    m = F.join(T, how="inner").reset_index()
    audit = {"pairs": int(len(m)), "imputed": int(m.imputed.sum())}
    m = m[~m.imputed]
    no_progress = (m.AT <= 0) | (m.ET <= 0)
    audit["no_progress_yet"] = int(no_progress.sum())
    m = m[~no_progress].copy()
    m["share_achieved"] = m.AF / m.AT
    m["share_expected"] = m.EF / m.ET
    bad = (m.share_achieved > 1.05) | (m.share_expected > 1.05) | (m.AF < 0)
    audit["inconsistent"] = int(bad.sum())
    m = m[~bad]
    women_only = (m.share_achieved > 0.995) & (m.share_expected > 0.995)
    m["gap"] = m.share_achieved - m.share_expected
    identical = (m.gap.abs() < 1e-3) & ~women_only
    audit["women_only"] = int(women_only.sum())
    audit["identical_share"] = int(identical.sum())
    info = m[~women_only & ~identical].copy()
    audit["informative"] = int(len(info))
    audit["informative_projects"] = int(info.Project_ID.nunique())

    meta = (p.sort_values("Project_ID").drop_duplicates("Project_ID").set_index("Project_ID")
            [["Project_Name", "CountryEconomy_Name", "WB_Region", "FCV_Flag", "Income_Group",
              "Global_Department", "Net_Commitment_Total", "Project_Status", "Approval_Date"]])
    info = info.merge(meta, left_on="Project_ID", right_index=True)
    info["fcv"] = (info.FCV_Flag == "Y").astype(int)

    # ---- propensity-score matching: FCV (treated) vs non-FCV
    X = pd.DataFrame(index=info.index)
    X["africa"] = info.WB_Region.isin(["AFE", "AFW"]).astype(float)
    X["mena"] = (info.WB_Region == "MENAAP").astype(float)
    X["lic"] = (info.Income_Group == "LIC").astype(float)
    X["umc"] = (info.Income_Group.isin(["UMC", "HIC"])).astype(float)
    X["log_commit"] = np.log10(info.Net_Commitment_Total.clip(lower=1e5))
    X["health_or_wash"] = info["sub"].isin(["CSC_RES_HEA_SERV", "CSC_RES_WAT_SAN_HYG"]).astype(float)
    X["gender_actions"] = (info["sub"] == "CSC_RES_GEN_EQU").astype(float)
    X["active"] = (info.Project_Status == "A").astype(float)
    X["share_expected"] = info.share_expected
    cov_names = {"africa": "Africa region", "mena": "MENAAP region", "lic": "Low-income country",
                 "umc": "Upper-middle / high income", "log_commit": "Project size (log $)",
                 "health_or_wash": "Health or WASH result", "gender_actions": "Gender-equality result",
                 "active": "Project still active", "share_expected": "Planned share of women"}
    t = info.fcv.values
    ps_model = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000)).fit(X, t)
    ps = ps_model.predict_proba(X)[:, 1]
    logit = np.log(ps / (1 - ps))
    caliper = 0.2 * logit.std()
    ti, ci = np.where(t == 1)[0], np.where(t == 0)[0]
    pairs = []
    for i in ti:  # 1:1 nearest neighbour with replacement, within caliper
        d = np.abs(logit[ci] - logit[i])
        j = d.argmin()
        if d[j] <= caliper:
            pairs.append((i, ci[j]))
    mi = np.array([a for a, _ in pairs])
    mc = np.array([b for _, b in pairs])

    def smd(a, b):
        s = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
        return 0.0 if s == 0 else (a.mean() - b.mean()) / s

    balance = []
    for c in X.columns:
        balance.append({"covariate": cov_names[c],
                        "before": r(smd(X[c].values[ti], X[c].values[ci]), 3),
                        "after": r(smd(X[c].values[mi], X[c].values[mc]), 3)})
    LAST["psm"] = {"info": info, "X": X, "mi": mi, "mc": mc, "ti": ti, "ci": ci, "logit": logit}
    gap = info.gap.values
    att = float(np.mean(gap[mi] - gap[mc]))
    naive = float(gap[ti].mean() - gap[ci].mean())
    # bootstrap over matched pairs, clustered by treated project
    proj_t = info.Project_ID.values[mi]
    uniq = np.unique(proj_t)
    diffs = gap[mi] - gap[mc]
    boots = []
    for _ in range(2000):
        pick = RNG.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([np.where(proj_t == u)[0] for u in pick])
        boots.append(diffs[idx].mean())
    lo, hi = np.percentile(boots, [2.5, 97.5])
    # sensitivity: drop the caliper (all treated matched)
    att_nocal = float(np.mean([gap[i] - gap[ci[np.abs(logit[ci] - logit[i]).argmin()]] for i in ti]))

    pts = [{"a": r(x.share_achieved, 3), "e": r(x.share_expected, 3), "fcv": int(x.fcv),
            "sub": x.sub, "name": x.Project_Name, "country": x.CountryEconomy_Name}
           for x in info.itertuples()]
    by_sub = info.groupby("sub").gap.agg(["count", "mean", "median"]).reset_index()
    return audit, {
        "n": int(len(info)), "treated": int(len(ti)), "control": int(len(ci)),
        "matched_treated": int(len(mi)), "unique_controls": int(len(np.unique(mc))),
        "caliper": r(caliper, 3), "balance": balance,
        "att": r(att * 100, 1), "ci": [r(lo * 100, 1), r(hi * 100, 1)],
        "naive": r(naive * 100, 1), "att_no_caliper": r(att_nocal * 100, 1),
        "mean_gap": r(info.gap.mean() * 100, 1), "median_gap": r(info.gap.median() * 100, 1),
        "share_below": r((info.gap < 0).mean(), 3),
        "by_sub": [{"sub": x["sub"], "label": SUBS.get(x["sub"], x["sub"]), "n": int(x["count"]),
                    "mean": r(x["mean"] * 100, 1), "median": r(x["median"] * 100, 1)}
                   for _, x in by_sub.iterrows()],
        "points": pts,
    }


# ---------------------------------------------------------------- main
def main():
    agg = load_aggregates()
    p = load_projects()

    meta = project_text(p)
    proj_rows, hits = classify(meta)
    validation = validation_sample(proj_rows)
    n_proj = len(proj_rows)
    theme_summary = []
    for k, t in THEMES.items():
        ids = set(hits[k])
        by_region = {rc: sum(1 for x in proj_rows if x["region"] == rc and k in x["themes"]) for rc in REGIONS}
        theme_summary.append({"key": k, "label": t["label"], "projects": len(ids),
                              "share": r(len(ids) / n_proj, 3), "by_region": by_region,
                              "patterns": t["patterns"], "validation": validation[k]})
    proj_region_counts = {rc: sum(1 for x in proj_rows if x["region"] == rc) for rc in REGIONS}
    both = sum(1 for x in proj_rows if "health_workforce" in x["themes"] and "jobs_skills" in x["themes"])
    hw_mig = sum(1 for x in proj_rows if "health_workforce" in x["themes"] and "migration" in x["themes"])

    g = delivery_frame(p)
    model = fit_delivery_model(g)
    audit, psm = gender_gap(p)

    data = {
        "meta": {"as_of": "2025-06-30", "cycle": "FY25", "generated": pd.Timestamp.now().strftime("%Y-%m-%d"),
                 "project_records": int(len(p)), "projects": int(p.Project_ID.nunique()),
                 "countries": int(p.CountryEconomy_Code.nunique())},
        "regions": {k: v[0] for k, v in REGIONS.items()} | {ALL: "All countries (WBG total)"},
        "subs": SUBS,
        "results": regional_results(agg),
        "context": vision_context(),
        "themes": {"summary": theme_summary, "n_projects": n_proj, "region_projects": proj_region_counts,
                   "health_workforce_and_jobs": both, "health_workforce_and_migration": hw_mig,
                   "projects": proj_rows},
        "model": model,
        "gender_audit": audit,
        "psm": psm,
    }
    (OUT / "dashboard_data.json").write_text(json.dumps(data, default=str, separators=(",", ":")))
    # console summary
    print("projects", data["meta"])
    print("themes", [(t["label"], t["projects"]) for t in theme_summary])
    print("model", {k: model[k] for k in ["n", "projects", "behind_rate", "best", "models"]})
    print("importance", model["importance"])
    print("audit", audit)
    print("psm", {k: psm[k] for k in ["n", "treated", "control", "matched_treated", "att", "ci", "naive",
                                      "att_no_caliper", "mean_gap", "median_gap"]})
    print("balance", psm["balance"])


if __name__ == "__main__":
    main()
