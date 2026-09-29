"""
Extra statistics used only in the written report (report/who-benefits-report.pdf).
Runs the same pipeline functions as pipeline.py, then adds uncertainty and robustness:

  - Wilson 95% intervals for hand-checked classifier precision
  - cluster-bootstrap 95% interval for the delivery model's out-of-fold AUC
  - a timing-only baseline model, to show what the full model adds
  - logistic-regression odds ratios (standardised) for the main features
  - sample-construction counts for every analysis
  - robustness of the matched FCS estimate: regression adjustment on the full
    informative sample and on the matched sample, cluster-robust by project
  - cluster-bootstrap intervals for the mean gender gap by result type

Writes output/report_stats.json.
"""
import json
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import pipeline as P

warnings.filterwarnings("ignore")
rng = np.random.default_rng(7)


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    ph = k / n
    den = 1 + z ** 2 / n
    c = (ph + z ** 2 / (2 * n)) / den
    h = z * np.sqrt(ph * (1 - ph) / n + z ** 2 / (4 * n ** 2)) / den
    return [round(max(0, c - h), 3), round(min(1, c + h), 3)]


def cluster_boot(values_by_group, stat, B=2000):
    keys = list(values_by_group)
    out = []
    for _ in range(B):
        pick = rng.choice(len(keys), size=len(keys), replace=True)
        out.append(stat([values_by_group[keys[i]] for i in pick]))
    return np.percentile(out, [2.5, 97.5])


def main():
    D = json.loads((P.OUT / "dashboard_data.json").read_text())
    p = P.load_projects()

    # ---------------- classifier precision intervals
    prec = {}
    for t in D["themes"]["summary"]:
        v = t["validation"]
        prec[t["key"]] = {"label": t["label"], "correct": v["correct"], "reviewed": v["reviewed"],
                          "ci": wilson(v["correct"], v["reviewed"]), "v1": v.get("v1_precision")}

    # ---------------- delivery sample construction
    t = p[(p.Demographic_Disaggregation == "Total") & (p.Double_Counting_Flag == "N")]
    n_pairs_total = t.groupby(["Project_ID", "sub"]).ngroups
    tt = t.groupby(["Project_ID", "sub"]).agg(E=("E", "sum"), approval=("Approval_Date", "first"),
                                               closing=("Closing_Date", "first"), progress=("Progress_Date", "max"))
    with_target = int(((tt.E > 0) & tt.approval.notna() & tt.closing.notna() & tt.progress.notna()).sum())
    g = P.delivery_frame(p)
    model = P.fit_delivery_model(g)
    L = P.LAST["delivery"]
    X, y, groups, best = L["X"], L["y"], L["groups"], L["best"]
    pred = L["preds"][best]

    # AUC cluster bootstrap (by project)
    idx_by_proj = pd.Series(np.arange(len(y))).groupby(groups).apply(list).to_dict()
    def auc_of(parts):
        ii = np.concatenate(parts)
        return roc_auc_score(y[ii], pred[ii])
    auc_ci = cluster_boot(idx_by_proj, auc_of, B=1000)

    # timing-only baseline, same folds
    Xb = X[["elapsed", "years_since_approval"]]
    base = np.zeros(len(y))
    for tr, te in GroupKFold(n_splits=5).split(Xb, y, groups):
        m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000)).fit(Xb.iloc[tr], y[tr])
        base[te] = m.predict_proba(Xb.iloc[te])[:, 1]
    base_auc = roc_auc_score(y, base)

    # standardised odds ratios from the full logistic model
    lm = make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=2000)).fit(X, y)
    coef = pd.Series(lm[-1].coef_[0], index=X.columns)
    keep = ["years_since_approval", "elapsed", "log_commit", "fcv", "ldc"]
    ors = {k: round(float(np.exp(coef[k])), 2) for k in keep}

    # ---------------- gender gap / PSM robustness
    audit, psm = P.gender_gap(p)
    S = P.LAST["psm"]
    info, Xp = S["info"].reset_index(drop=True), S["X"].reset_index(drop=True)
    yv = info.gap.values * 100
    # (a) regression adjustment on the full informative sample
    Z = sm.add_constant(pd.concat([info.fcv.rename("fcv"), Xp], axis=1).astype(float))
    ols = sm.OLS(yv, Z).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(info.Project_ID)[0]})
    ra = {"coef": round(float(ols.params["fcv"]), 1),
          "ci": [round(float(x), 1) for x in ols.conf_int().loc["fcv"]], "p": round(float(ols.pvalues["fcv"]), 2),
          "n": int(len(yv))}
    # (b) regression on the matched sample (controls weighted by times used)
    mi, mc = S["mi"], S["mc"]
    w = pd.Series(1.0, index=np.concatenate([mi, mc])).groupby(level=0).sum()
    ms = pd.DataFrame({"i": w.index, "w": w.values})
    Zm = Z.iloc[ms.i].reset_index(drop=True)
    wls = sm.WLS(yv[ms.i], Zm, weights=ms.w).fit(cov_type="cluster",
                                                 cov_kwds={"groups": pd.factorize(info.Project_ID.values[ms.i])[0]})
    mr = {"coef": round(float(wls.params["fcv"]), 1),
          "ci": [round(float(x), 1) for x in wls.conf_int().loc["fcv"]], "p": round(float(wls.pvalues["fcv"]), 2),
          "n": int(len(ms))}
    # (c) mean gap by result type with cluster-bootstrap CIs
    by_sub = []
    for sub, d in info.groupby("sub"):
        vals = d.groupby("Project_ID").gap.apply(lambda s: list(s * 100)).to_dict()
        lo, hi = cluster_boot(vals, lambda parts: np.mean(np.concatenate(parts)))
        by_sub.append({"sub": sub, "label": P.SUBS.get(sub, sub), "n": int(len(d)), "projects": int(d.Project_ID.nunique()),
                       "mean": round(float(d.gap.mean() * 100), 1), "median": round(float(d.gap.median() * 100), 1),
                       "ci": [round(float(lo), 1), round(float(hi), 1)]})
    share_neg = round(float((info.gap < 0).mean()), 3)

    first = p.drop_duplicates("Project_ID")
    sample = {"rows_by_file": {k: int(v) for k, v in p.groupby("file").size().items()},
              "double_counted_rows": int((p.Double_Counting_Flag == "Y").sum()),
              "active": int((first.Project_Status == "A").sum()), "closed": int((first.Project_Status == "C").sum()),
              "fcs_projects": int((first.FCV_Flag == "Y").sum())}
    out = {
        "sample": sample,
        "precision": prec,
        "delivery": {"pairs_total": int(n_pairs_total), "with_target_and_dates": with_target, "analysed": model["n"],
                     "projects": model["projects"], "behind_rate": model["behind_rate"],
                     "auc_best": model["models"][best]["auc"], "auc_ci": [round(float(x), 3) for x in auc_ci],
                     "baseline_auc": round(float(base_auc), 3), "odds_ratios_per_sd": ors, "best": best},
        "psm_robustness": {"regression_full": ra, "regression_matched": mr},
        "gap_by_sub": by_sub, "share_negative_gap": share_neg,
        "checks": {"att": psm["att"], "ci": psm["ci"], "audit": audit},
    }
    (P.OUT / "report_stats.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
