"""Figures for the WIPO working paper -> figures/*.svg

All numbers are read from the data embedded in the patent dashboard
(outputs/patent-dashboard.html: DATA = cross-section,
PANEL = panel estimates), which the notebook exported.
Figure 2 CIs for the pooled and FE specifications are recovered from the
reported coefficient and p-value (normal approximation, se = |b| / z(p/2));
Negative Binomial CIs are those reported in Table 5.
"""
import json
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
import numpy as np
from scipy.stats import norm

HERE = Path(__file__).parent
FONTS = HERE / "style" / "fonts"
OUT = HERE / "figures"
OUT.mkdir(exist_ok=True)
for f in FONTS.glob("*.ttf"):
    fm.fontManager.addfont(str(f))

src = (HERE / "outputs" / "patent-dashboard.html").read_text()
grab = lambda k: json.loads(re.search(r"const " + k + r" = (\{.*?\});", src, re.S).group(1))
DATA, PANEL = grab("DATA"), grab("PANEL")
C = DATA["countries"]

INK, SOFT, FAINT, GRID, MUTED = "#12263f", "#4a5568", "#7b8494", "#e8e4da", "#cdc7ba"
BLUE, CLAY, TEAL, PLUM, RED = "#3380b5", "#c9774a", "#0e7c74", "#6b4e9b", "#b04a5a"
plt.rcParams.update({
    "font.family": "Source Sans 3 ExtraLight", "font.size": 9, "text.color": INK, "axes.edgecolor": GRID,
    "axes.labelcolor": SOFT, "xtick.color": FAINT, "ytick.color": SOFT, "xtick.labelsize": 8.5, "ytick.labelsize": 8.5,
    "axes.spines.top": False, "axes.spines.right": False, "svg.fonttype": "path", "axes.axisbelow": True,
})
FULL, HALF = 6.7, 3.25
REG = {"EAP": "#0e7c74", "ECA": "#3380b5", "LAC": "#c9774a", "MNA": "#b8860b", "NAM": "#6b4e9b", "SAS": "#b04a5a", "SSA": "#7b8494"}


def save(fig, name):
    fig.savefig(OUT / f"{name}.svg", bbox_inches="tight", pad_inches=0.04, transparent=True)
    plt.close(fig)


def f1():
    fig, ax = plt.subplots(figsize=(FULL, 3.6))
    regs = {}
    for c in C:
        if c["patents_per_million"] > 0:
            regs.setdefault((c["region_code"], c["region_name"]), []).append(c)
    for (code, name), cs in sorted(regs.items()):
        ax.scatter([c["gdp_per_capita"] for c in cs], [c["patents_per_million"] for c in cs], s=20,
                   color=REG.get(code, FAINT), alpha=.85, edgecolor="white", lw=.5, label=name, zorder=3)
    for c in C:
        if c["iso_code"] in ("KOR", "JPN", "CHN", "USA", "DEU", "IND", "KWT", "BRB", "QAT", "NGA"):
            ax.annotate(c["country_name"].replace(", Rep.", ""), (c["gdp_per_capita"], c["patents_per_million"]),
                        xytext=(4, 3), textcoords="offset points", fontsize=7.5, color=SOFT)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("GDP per capita (US$, log scale)")
    ax.set_ylabel("Resident patents per million people (log scale)")
    ax.grid(color=GRID, lw=.7, which="major")
    ax.legend(frameon=False, fontsize=7.5, loc="upper left", ncol=2, handletextpad=.2, columnspacing=.8)
    save(fig, "f1_gdp_intensity")
    return sum(len(v) for v in regs.values())


def ci_from_p(b, p):
    z = norm.isf(max(p, 1e-300) / 2)
    se = abs(b) / z
    return b - 1.96 * se, b + 1.96 * se


def f2():
    vars_ = ["ln(GDP per capita)", "ln(Population)", "ln(Energy per capita)"]
    nb_ci = {"ln(GDP per capita)": (0.09, 0.34), "ln(Population)": (1.21, 1.27), "ln(Energy per capita)": (1.24, 1.44)}
    specs = [("pooled", "Pooled OLS (panel)", BLUE), ("fe", "Fixed effects", CLAY), ("nb", "Negative Binomial", TEAL)]
    fig, axes = plt.subplots(1, 3, figsize=(FULL, 2.2), sharey=True)
    out = {}
    for ax, v in zip(axes, vars_):
        for k, (s, lab, col) in enumerate(specs):
            e = PANEL["specs"][s][v]
            lo, hi = nb_ci[v] if s == "nb" else ci_from_p(e["coef"], e["p"])
            out[(s, v)] = (round(lo, 2), round(hi, 2))
            y = 2 - k
            ax.plot([lo, hi], [y, y], color=col, lw=2.2, solid_capstyle="round")
            ax.scatter(e["coef"], y, s=34, color=col, edgecolor="white", lw=1, zorder=3)
            ax.text(hi + .08, y, f"{e['coef']:.3f}", va="center", fontsize=7.5, color=SOFT)
        ax.axvline(0, color=INK, lw=.8, ls=(0, (3, 2)))
        ax.set_title(v, fontsize=8.8, loc="left", color=INK)
        ax.grid(axis="x", color=GRID, lw=.7)
        ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
        lo_all = min(out[(s, v)][0] for s, _, _ in specs); hi_all = max(out[(s, v)][1] for s, _, _ in specs)
        ax.set_xlim(min(-.3, lo_all - .2), hi_all + .7)
    axes[0].set_yticks([2, 1, 0], [s[1] for s in specs])
    axes[0].set_ylim(-.6, 2.6)
    axes[1].set_xlabel("Coefficient (elasticity) with 95% confidence interval")
    fig.subplots_adjust(wspace=.12)
    save(fig, "f2_coefplot")
    return {f"{s}|{v}": ci for (s, v), ci in out.items()}


def f3():
    imp = PANEL["ml"]["gbr"]["importances"]
    labs = {"log_gdp_per_capita": "ln(GDP per capita)", "log_population": "ln(Population)", "log_energy_per_capita": "ln(Energy per capita)"}
    items = sorted(imp.items(), key=lambda x: x[1])
    fig, ax = plt.subplots(figsize=(HALF, 1.7))
    ax.barh(range(3), [v for _, v in items], .6, color=[MUTED if v < .1 else PLUM for _, v in items])
    for i, (_, v) in enumerate(items):
        ax.text(v + .01, i, f"{v:.2f}", va="center", fontsize=8, color=INK)
    ax.set_yticks(range(3), [labs[k] for k, _ in items])
    ax.set_xlim(0, .65); ax.set_xlabel("Share of total importance")
    ax.grid(axis="x", color=GRID, lw=.7)
    ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
    save(fig, "f3_importance")


def f4():
    fig, ax = plt.subplots(figsize=(HALF, 2.9))
    x = np.array([c["ols_pred"] for c in C]); y = x + np.array([c["ols_resid"] for c in C])
    lo, hi = min(x.min(), y.min()) - .5, max(x.max(), y.max()) + .5
    ax.plot([lo, hi], [lo, hi], color=INK, lw=.8, ls=(0, (3, 2)))
    ax.scatter(x, y, s=14, color=BLUE, alpha=.8, edgecolor="white", lw=.4, zorder=3)
    ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
    ax.set_xlabel("OLS-predicted ln(1 + patents)"); ax.set_ylabel("Actual ln(1 + patents)")
    ax.grid(color=GRID, lw=.7)
    ax.text(hi - .3, lo + .5, f"R² = {DATA['ols_r2_insample']:.3f}, n = {len(C)}", ha="right", fontsize=8, color=INK)
    save(fig, "f4_fit")


def f5():
    top = sorted(C, key=lambda c: -c["patents_residents"])[:15][::-1]
    fig, ax = plt.subplots(figsize=(FULL, 3.2))
    v = [c["patents_residents"] / 1000 for c in top]
    ax.barh(range(15), v, .7, color=[CLAY if c["iso_code"] == "CHN" else BLUE for c in top])
    for i, c in enumerate(top):
        ax.text(v[i] + 12, i, f"{c['patents_residents']:,}", va="center", fontsize=7.8, color=SOFT)
    ax.set_yticks(range(15), [c["country_name"] for c in top])
    ax.set_xlim(0, 1650); ax.set_xlabel("Resident patent applications (thousands), latest year")
    ax.grid(axis="x", color=GRID, lw=.7)
    ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
    save(fig, "f5_top15")
    return [(c["country_name"], c["patents_residents"], c["patents_year"]) for c in top[::-1]]


def f6():
    s = sorted(C, key=lambda c: c["ols_resid"])
    sel = s[:8] + s[-8:]
    sel = sorted(sel, key=lambda c: c["ols_resid"])
    fig, ax = plt.subplots(figsize=(FULL, 3.4))
    r = [c["ols_resid"] for c in sel]
    ax.barh(range(16), r, .68, color=[BLUE if v > 0 else RED for v in r])
    for i, v in enumerate(r):
        ax.text(v + (.08 if v > 0 else -.08), i, f"{v:+.2f}", va="center", ha="left" if v > 0 else "right", fontsize=7.8, color=SOFT)
    ax.set_yticks(range(16), [c["country_name"] for c in sel])
    ax.axvline(0, color=INK, lw=.8)
    ax.set_xlim(-6.2, 5.2)
    ax.set_xlabel("Residual: actual minus predicted ln(1 + patents)")
    ax.grid(axis="x", color=GRID, lw=.7)
    ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
    save(fig, "f6_residuals")
    return [(c["country_name"], c["ols_resid"]) for c in sel]


if __name__ == "__main__":
    print("f1 n plotted", f1())
    print("f2 CIs", f2())
    f3(); f4()
    print("f5", f5())
    print("f6", f6())
