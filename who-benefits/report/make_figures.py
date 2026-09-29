"""Figures for the written report. Reads ../output/dashboard_data.json and
../output/report_stats.json; writes SVGs to report/figures/."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

HERE = Path(__file__).parent
OUT = HERE / "figures"
OUT.mkdir(exist_ok=True)
for f in (HERE / "fonts").glob("*.ttf"):
    fm.fontManager.addfont(str(f))
D = json.loads((HERE.parent / "output" / "dashboard_data.json").read_text())
S = json.loads((HERE.parent / "output" / "report_stats.json").read_text())

INK, SOFT, FAINT, GRID, MUTED = "#12263f", "#4a5568", "#7b8494", "#e8e4da", "#cdc7ba"
S1, S2 = "#3380b5", "#c9774a"          # validated pair (CVD ΔE ≥ 24, contrast ≥ 3:1 on white)
plt.rcParams.update({
    "font.family": "Source Sans 3 ExtraLight", "font.size": 9, "text.color": INK,
    "axes.edgecolor": GRID, "axes.labelcolor": SOFT, "axes.titlesize": 10, "axes.titleweight": 600,
    "xtick.color": FAINT, "ytick.color": SOFT, "xtick.labelsize": 8.5, "ytick.labelsize": 8.5,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": False,
    "svg.fonttype": "path", "figure.dpi": 150, "axes.axisbelow": True,
})
FULL, HALF = 6.7, 3.25
REG = ["AFE", "AFW", "EAP", "ECA", "LCR", "MENAAP", "SAR"]
REGS = {"AFE": "Eastern & Southern Africa", "AFW": "Western & Central Africa", "EAP": "East Asia & Pacific",
        "ECA": "Europe & Central Asia", "LCR": "Latin America & Caribbean", "MENAAP": "MENA, Afghanistan & Pakistan",
        "SAR": "South Asia", "ACW": "All countries"}


def save(fig, name):
    fig.savefig(OUT / f"{name}.svg", bbox_inches="tight", pad_inches=0.04, transparent=True)
    plt.close(fig)


def xgrid(ax):
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)


def ygrid(ax):
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)


def row(sub, c, women_sub=None):
    R = D["results"][sub].get(c, {})
    tot = R.get("Total", {})
    W = (D["results"][women_sub].get(c, {}) if women_sub else R).get("Female")
    return tot.get("achieved"), tot.get("expected"), W["achieved"] if W else None


# ---------------------------------------------------------------- F1 reach by region (health)
def f1():
    rows = [row("CSC_RES_HEA_SERV", c) for c in REG]
    fig, ax = plt.subplots(figsize=(FULL, 3.2))
    y = np.arange(len(REG))[::-1]
    h = 0.36
    tot = [r[0] / 1e6 for r in rows]
    wom = [r[2] / 1e6 for r in rows]
    ax.barh(y + h / 2, tot, h, color=S1, label="All people reached")
    ax.barh(y - h / 2, wom, h, color=S2, label="Women reached")
    for yi, t, w, r in zip(y, tot, wom, rows):
        ax.text(t + 1.5, yi + h / 2, f"{t:.1f}M · {r[0] / r[1]:.0%} of target", va="center", fontsize=8, color=SOFT)
        flag = "  (check sex-disaggregated reporting)" if w / t < 0.3 else ""
        ax.text(w + 1.5, yi - h / 2, f"{w:.1f}M · {w / t:.0%} women{flag}", va="center", fontsize=8,
                color=S2 if flag else SOFT, fontweight=600 if flag else 400)
    ax.set_yticks(y, [REGS[c] for c in REG])
    ax.set_xlim(0, 215)
    ax.set_xlabel("People reached to date (millions)")
    xgrid(ax)
    ax.legend(frameon=False, loc="lower right", fontsize=8.5)
    save(fig, "f1_reach_health")


# ---------------------------------------------------------------- F2 context small multiples
def f2():
    ctx = D["context"]
    items = [("pov3", "Poverty at $3.00/day"), ("food", "Food & nutrition\ninsecurity"), ("hygiene", "Access to basic\nhygiene services")]
    fig, axes = plt.subplots(1, 3, figsize=(FULL, 2.9), sharey=True)
    y = np.arange(len(REG))[::-1]
    for ax, (k, lab) in zip(axes, items):
        vals = [ctx[k].get(c, {}).get("value") for c in REG]
        ax.barh(y, [v or 0 for v in vals], 0.6, color=S1)
        for yi, v in zip(y, vals):
            ax.text((v or 0) + 2, yi, f"{v:.0f}%" if v is not None else "no data", va="center", fontsize=7.5,
                    color=SOFT if v is not None else FAINT)
        w = ctx[k]["ACW"]["value"]
        ax.axvline(w, color=INK, lw=1, ls=(0, (3, 2)))
        ax.text(w + 2, -0.95, f"world {w:.0f}%", fontsize=7.5, ha="left", color=INK, fontweight=600)
        yrs = sorted({v["year"] for v in ctx[k].values()})
        ax.set_title(f"{lab} ({'/'.join(map(str, yrs))})", fontsize=8.8, loc="left", color=INK)
        ax.set_ylim(-1.3, len(REG) - 0.5)
        ax.set_xlim(0, 110)
        ax.set_xticks([0, 50, 100], ["0", "50", "100%"])
        xgrid(ax)
    axes[0].set_yticks(y, [REGS[c] for c in REG])
    fig.subplots_adjust(wspace=0.16)
    save(fig, "f2_context")


# ---------------------------------------------------------------- F3 themes
def f3():
    T = D["themes"]["summary"]
    order = sorted(T, key=lambda t: t["projects"])
    fig, ax = plt.subplots(figsize=(FULL, 2.6))
    y = np.arange(len(order))
    cols = [S2 if t["key"] in ("health_workforce", "menstrual") else S1 for t in order]
    ax.barh(y, [t["projects"] for t in order], 0.6, color=cols)
    for yi, t in zip(y, order):
        p = S["precision"][t["key"]]
        ax.text(t["projects"] + 3, yi, f"{t['projects']} projects ({t['share']:.1%})", va="center", fontsize=8.5, color=INK)
        ax.text(262, yi, f"{p['correct']:>2}/{p['reviewed']:<2}  [{p['ci'][0]:.2f}–{p['ci'][1]:.2f}]", va="center",
                fontsize=8, color=SOFT, family="IBM Plex Mono")
    ax.text(262, len(order) - 0.3, "Precision (Wilson 95% CI)", fontsize=8, color=FAINT, fontweight=600)
    ax.set_yticks(y, [t["label"] for t in order])
    ax.set_xlim(0, 340)
    ax.set_xticks([0, 50, 100, 150, 200])
    ax.set_xlabel(f"Projects with at least one matching objective or indicator (of {D['themes']['n_projects']:,})")
    xgrid(ax)
    save(fig, "f3_themes")


# ---------------------------------------------------------------- F4 theme × region heat table
def f4():
    T = D["themes"]["summary"]
    rp = D["themes"]["region_projects"]
    M = np.array([[t["by_region"][c] / rp[c] * 100 for c in REG] for t in T])
    cmap = LinearSegmentedColormap.from_list("b", ["#f3f7fb", "#9cc3e0", "#2c6f9f", "#16456b"])
    fig, ax = plt.subplots(figsize=(FULL, 2.7))
    ax.imshow(M, cmap=cmap, aspect="auto", vmin=0, vmax=30)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            n = T[i]["by_region"][REG[j]]
            ax.text(j, i, f"{M[i, j]:.0f}%\n({n})", ha="center", va="center", fontsize=7.5,
                    color="white" if M[i, j] > 16 else INK, linespacing=1.1)
    short = {"AFE": "E. & S.\nAfrica", "AFW": "W. & C.\nAfrica", "EAP": "East Asia\n& Pacific", "ECA": "Europe &\nC. Asia",
             "LCR": "Latin Am.\n& Carib.", "MENAAP": "MENA, Afg.\n& Pakistan", "SAR": "South\nAsia"}
    ax.set_xticks(range(len(REG)), [f"{short[c]}\nn = {rp[c]}" for c in REG], fontsize=7.5)
    ax.set_yticks(range(len(T)), [t["label"] for t in T])
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.xaxis.tick_top()
    save(fig, "f4_theme_region")


# ---------------------------------------------------------------- F5 behind by age
def f5():
    A = D["model"]["by_age"]
    fig, ax = plt.subplots(figsize=(HALF, 2.6))
    x = np.arange(len(A))
    ax.bar(x, [a["rate"] * 100 for a in A], 0.62, color=S1)
    for xi, a in zip(x, A):
        ax.text(xi, a["rate"] * 100 + 2, f"{a['rate']:.0%}", ha="center", fontsize=9, fontweight=600)
        ax.text(xi, 3, f"n={a['n']}", ha="center", fontsize=7, color="white")
    ax.set_xticks(x, [a["bin"] for a in A])
    ax.set_ylim(0, 100)
    ax.set_yticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100%"])
    ax.set_xlabel("Years since Board approval")
    ygrid(ax)
    save(fig, "f5_age")


# ---------------------------------------------------------------- F6 importance
def f6():
    I = D["model"]["importance"][::-1]
    fig, ax = plt.subplots(figsize=(HALF, 2.6))
    y = np.arange(len(I))
    ax.barh(y, [i["value"] for i in I], 0.6, color=S1)
    for yi, i in zip(y, I):
        ax.text(i["value"] + 0.001, yi, f"{i['value']:.3f}", va="center", fontsize=7.5, color=SOFT)
    ax.set_yticks(y, [i["feature"] for i in I], fontsize=7.8)
    ax.set_xlabel("Drop in AUC when shuffled")
    ax.set_xlim(0, max(i["value"] for i in I) * 1.25)
    xgrid(ax)
    save(fig, "f6_importance")


# ---------------------------------------------------------------- F7 calibration
def f7():
    C = D["model"]["calibration"]
    fig, ax = plt.subplots(figsize=(HALF, 2.8))
    ax.plot([0, 100], [0, 100], color=FAINT, lw=1, ls=(0, (4, 3)))
    ax.scatter([c["pred"] * 100 for c in C], [c["obs"] * 100 for c in C], s=34, color=S1, edgecolor="white", lw=1.2, zorder=3)
    ax.set_xlim(0, 100); ax.set_ylim(0, 100)
    ax.set_xlabel("Predicted probability (decile mean, %)")
    ax.set_ylabel("Observed share behind (%)")
    ax.grid(color=GRID, lw=0.8)
    ax.text(62, 12, "perfect calibration", rotation=0, fontsize=7.5, color=FAINT)
    save(fig, "f7_calibration")


# ---------------------------------------------------------------- F8 fairness
def f8():
    F = D["model"]["fairness"]
    inc = {"LIC": "Low income", "LMC": "Lower-middle income", "UMC": "Upper-middle income"}
    rows = [("Region", r["group"], r) for r in F["region"]] + [("FCS status", r["group"], r) for r in F["fcv"]] + \
           [("Income", inc.get(r["group"], r["group"]), r) for r in F["income"]]
    fig, ax = plt.subplots(figsize=(FULL, 3.4))
    y = np.arange(len(rows))[::-1]
    overall = S["delivery"]["auc_best"]
    ax.axvline(overall, color=S1, lw=1, ls=(0, (3, 2)))
    ax.text(overall, len(rows) - 0.2, f"overall {overall:.2f}", color=S1, fontsize=7.5, ha="center")
    ax.axvline(0.5, color=FAINT, lw=1)
    ax.text(0.5, len(rows) - 0.2, "coin flip", color=FAINT, fontsize=7.5, ha="center")
    worst = min(r["auc"] for _, _, r in rows[:len(F["region"])])
    for yi, (grp, lab, r) in zip(y, rows):
        c = S2 if r["auc"] == worst else S1
        ax.hlines(yi, 0.5, r["auc"], color=MUTED, lw=1.4)
        ax.scatter(r["auc"], yi, s=40, color=c, zorder=3, edgecolor="white", lw=1)
        ax.text(0.905, yi, f"{r['auc']:.2f}   miss {r['fnr']:.0%}   n={r['n']}", va="center", fontsize=7.8, color=SOFT, family="IBM Plex Mono")
    ax.set_yticks(y, [f"{lab}" for _, lab, _ in rows], fontsize=8.2)
    bounds = [len(F["region"]), len(F["region"]) + len(F["fcv"])]
    for b in bounds:
        ax.axhline(len(rows) - b - 0.5, color=GRID, lw=1)
    ax.set_xlim(0.45, 1.08)
    ax.set_xticks([0.5, 0.6, 0.7, 0.8, 0.9])
    ax.set_xlabel("Out-of-fold AUC (higher = better ranking of behind vs. on-track results)")
    xgrid(ax)
    save(fig, "f8_fairness")


# ---------------------------------------------------------------- F9 audit waterfall
def f9():
    A = D["gender_audit"]
    steps = [("Reported for women and in total", A["pairs"], "start"),
             ("Women's figure = fixed share of total", -A["imputed"], "drop"),
             ("No progress reported yet", -A["no_progress_yet"], "drop"),
             ("Women-only result (100% / 100%)", -A["women_only"], "drop"),
             ("Identical shares by construction", -A["identical_share"], "drop"),
             ("Internally inconsistent (> 100%)", -A["inconsistent"], "drop"),
             ("Informative: women counted directly", A["informative"], "end")]
    fig, ax = plt.subplots(figsize=(FULL, 2.9))
    y = np.arange(len(steps))[::-1]
    run = 0
    for yi, (lab, v, kind) in zip(y, steps):
        if kind == "start":
            ax.barh(yi, v, 0.6, color=MUTED); run = v; txt = f"{v:,}"; x = v
        elif kind == "drop":
            ax.barh(yi, -v, 0.6, left=run + v, color=S2 if lab.startswith("Women's figure") else "#e3c3ad"); run += v
            txt = f"−{-v:,}  ({-v / A['pairs']:.0%})"; x = run - v
        else:
            ax.barh(yi, v, 0.6, color=S1); txt = f"{v:,}  ({v / A['pairs']:.0%}) from {A['informative_projects']} projects"; x = v
        ax.text(x + 18, yi, txt, va="center", fontsize=8.3, color=INK)
    ax.set_yticks(y, [s[0] for s in steps])
    ax.set_xlim(0, 2200)
    ax.set_xlabel("Project results (project × corporate indicator)")
    xgrid(ax)
    save(fig, "f9_audit")


# ---------------------------------------------------------------- F10 scatter
def f10():
    pts = D["psm"]["points"]
    fig, ax = plt.subplots(figsize=(HALF, 3.1))
    ax.plot([0, 100], [0, 100], color=FAINT, lw=1, ls=(0, (4, 3)))
    for f, c, lab in [(0, S1, "Not FCS"), (1, S2, "FCS")]:
        P = [p for p in pts if p["fcv"] == f]
        ax.scatter([p["e"] * 100 for p in P], [p["a"] * 100 for p in P], s=14, color=c, edgecolor="white", lw=0.6,
                   label=f"{lab} (n={len(P)})", zorder=3, alpha=.95)
    ax.set_xlim(0, 102); ax.set_ylim(0, 102)
    ax.set_xticks([0, 25, 50, 75, 100]); ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_xlabel("Planned share of women (%)"); ax.set_ylabel("Achieved share of women (%)")
    ax.grid(color=GRID, lw=0.8)
    ax.legend(frameon=False, fontsize=7.5, loc="upper left", handletextpad=0.2)
    ax.text(97, 6, "below the line:\nbehind plan", ha="right", fontsize=7, color=FAINT)
    save(fig, "f10_scatter")


# ---------------------------------------------------------------- F11 gap by result type (forest)
def f11():
    G = sorted(S["gap_by_sub"], key=lambda g: g["mean"])
    fig, ax = plt.subplots(figsize=(HALF, 3.1))
    y = np.arange(len(G))[::-1]
    ax.axvline(0, color=INK, lw=1)
    for yi, g in zip(y, G):
        c = S2 if g["ci"][1] < 0 else S1
        ax.hlines(yi, g["ci"][0], g["ci"][1], color=c, lw=2.2, alpha=.5)
        ax.scatter(g["mean"], yi, s=40, color=c, zorder=3, edgecolor="white", lw=1)
    labels = {"Health, nutrition & population services": "Health, nutrition &\npopulation services",
              "Water, sanitation and/or hygiene": "Water, sanitation\n& hygiene",
              "Actions advancing gender equality": "Gender-equality\nactions",
              "Actions expanding economic opportunity": "Economic-opportunity\nactions",
              "Financial services users": "Financial services"}
    ax.set_yticks(y, [f"{labels.get(g['label'], g['label'])} (n={g['n']})" for g in G], fontsize=7.6)
    ax.set_xlim(-20, 14)
    ax.set_xlabel("Mean gap, pp (achieved − planned\nshare of women), 95% cluster-bootstrap CI")
    xgrid(ax)
    save(fig, "f11_gap_by_type")


# ---------------------------------------------------------------- F12 love plot
def f12():
    B = D["psm"]["balance"]
    fig, ax = plt.subplots(figsize=(HALF, 3.1))
    y = np.arange(len(B))[::-1]
    ax.axvspan(-0.1, 0.1, color="#e4ede6", zorder=0)
    ax.axvline(0, color=INK, lw=1)
    for yi, b in zip(y, B):
        ax.annotate("", xy=(b["after"], yi), xytext=(b["before"], yi),
                    arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=1, shrinkA=4, shrinkB=5, mutation_scale=7))
        ax.scatter(b["before"], yi, s=26, facecolor="white", edgecolor=FAINT, lw=1.2, zorder=3)
        ax.scatter(b["after"], yi, s=30, color=S1, zorder=4, edgecolor="white", lw=0.8)
    ax.scatter([], [], s=26, facecolor="white", edgecolor=FAINT, label="Before matching")
    ax.scatter([], [], s=30, color=S1, label="After matching")
    ax.set_yticks(y, [b["covariate"] for b in B], fontsize=7.8)
    ax.set_xlim(-0.75, 1.0)
    ax.set_xlabel("Standardised mean difference (FCS − non-FCS)")
    ax.legend(frameon=False, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.45, -0.22), ncol=2)
    xgrid(ax)
    save(fig, "f12_balance")


# ---------------------------------------------------------------- F13 estimates forest
def f13():
    P = D["psm"]; R = S["psm_robustness"]
    rows = [("Raw difference (FCS − all non-FCS)", P["naive"], None, MUTED),
            ("PSM, 1:1 NN with caliper (main)", P["att"], P["ci"], S2),
            ("PSM without caliper", P["att_no_caliper"], None, MUTED),
            ("Regression adjustment, full sample", R["regression_full"]["coef"], R["regression_full"]["ci"], S1),
            ("Regression on matched sample", R["regression_matched"]["coef"], R["regression_matched"]["ci"], S1)]
    fig, ax = plt.subplots(figsize=(FULL, 2.2))
    y = np.arange(len(rows))[::-1]
    ax.axvline(0, color=INK, lw=1)
    for yi, (lab, est, ci, c) in zip(y, rows):
        if ci:
            ax.hlines(yi, ci[0], ci[1], color=c, lw=2.4, alpha=.55)
        ax.scatter(est, yi, s=46, color=c if c != MUTED else FAINT, zorder=3, edgecolor="white", lw=1)
        txt = f"{est:+.1f} pp" + (f"  [{ci[0]:+.1f}, {ci[1]:+.1f}]" if ci else "  (point estimate)")
        ax.text(12.5, yi, txt, va="center", fontsize=8, color=SOFT, family="IBM Plex Mono")
    ax.set_yticks(y, [r[0] for r in rows])
    ax.set_xlim(-12, 24)
    ax.set_xticks([-10, -5, 0, 5, 10])
    ax.set_xlabel("Difference in gender delivery gap, FCS vs. non-FCS (percentage points), with 95% CI")
    xgrid(ax)
    save(fig, "f13_estimates")


for f in [f1, f2, f3, f4, f5, f6, f7, f8, f9, f10, f11, f12, f13]:
    f()
print("figures:", sorted(p.name for p in OUT.glob("*.svg")))
