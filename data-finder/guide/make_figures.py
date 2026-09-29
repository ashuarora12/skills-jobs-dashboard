"""Figures for the Data Finder guide -> guide/figures/*.svg"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

HERE = Path(__file__).parent
FONTS = HERE / "fonts"
OUT = HERE / "figures"
OUT.mkdir(exist_ok=True)
for f in FONTS.glob("*.ttf"):
    fm.fontManager.addfont(str(f))
S = json.loads((HERE / "output" / "guide_stats.json").read_text())

INK, SOFT, FAINT, GRID = "#183B39", "#4E6865", "#7C8F8C", "#E3EAE7"
TEAL, CLAY, SAGE, MUTED = "#0F766E", "#B96A3E", "#84A98C", "#C9D6D2"
plt.rcParams.update({
    "font.family": "Source Sans 3 ExtraLight", "font.size": 9, "text.color": INK, "axes.edgecolor": GRID,
    "axes.labelcolor": SOFT, "xtick.color": FAINT, "ytick.color": SOFT, "xtick.labelsize": 8.5, "ytick.labelsize": 8.5,
    "axes.spines.top": False, "axes.spines.right": False, "svg.fonttype": "path", "axes.axisbelow": True,
})
FULL, HALF = 6.7, 3.25


def save(fig, name):
    fig.savefig(OUT / f"{name}.svg", bbox_inches="tight", pad_inches=0.04, transparent=True)
    plt.close(fig)


# ---------------------------------------------------------------- G1 multiple-burden hotspots (heat table)
def g1():
    H = S["hotspots"]
    cols = ["food", "hygiene", "sanitation", "water", "poverty", "climate"]
    heads = ["Food & nutrition\ninsecurity", "No basic\nhygiene", "No basic\nsanitation", "No basic\ndrinking water", "Poverty\n($3.00/day)", "High climate-\nhazard risk"]
    M = np.array([[np.nan if h[c] is None else h[c] for c in cols] for h in H], dtype=float)
    cmap = LinearSegmentedColormap.from_list("c", ["#F7EFE3", "#E8CDA8", "#D9A06F", "#B96A3E", "#7E3B20"])
    fig, ax = plt.subplots(figsize=(FULL, 4.4))
    ax.imshow(np.nan_to_num(M, nan=-1), cmap=cmap, vmin=0, vmax=100, aspect="auto")
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            if np.isnan(v):
                ax.add_patch(plt.Rectangle((j - .5, i - .5), 1, 1, color="#EEF2F0"))
                ax.text(j, i, "n/a", ha="center", va="center", fontsize=7.5, color=FAINT)
            else:
                ax.text(j, i, f"{v:.0f}%", ha="center", va="center", fontsize=8, color="white" if v > 55 else INK)
    ax.set_xticks(range(len(cols)), heads, fontsize=8)
    ax.xaxis.tick_top()
    ax.set_yticks(range(len(H)), [f"{h['name']}" for h in H], fontsize=8.3)
    ax.axvline(4.5, color="white", lw=4)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    save(fig, "g1_hotspots")


# ---------------------------------------------------------------- G2 poverty vs no hygiene
def g2():
    P = S["scatter"]
    a = S["assoc"]["hygiene"]
    fig, ax = plt.subplots(figsize=(FULL, 3.3))
    x = np.array([p["x"] for p in P]); y = np.array([p["y"] for p in P])
    ax.scatter(x, y, s=18, color=TEAL, alpha=.8, edgecolor="white", lw=.6, zorder=3)
    for p in P:
        if p["iso"] in ("IND", "LBR", "ETH", "NGA", "BGD", "PAK", "NPL", "MDG") :
            ax.annotate(p["name"].split(",")[0], (p["x"], p["y"]), xytext=(5, 3), textcoords="offset points", fontsize=7.5, color=SOFT)
    ind = [p for p in P if p["iso"] == "IND"]
    if ind:
        ax.scatter(ind[0]["x"], ind[0]["y"], s=40, color=CLAY, zorder=4, edgecolor="white", lw=1)
    ax.set_xlabel("Poverty at $3.00/day (% of population)")
    ax.set_ylabel("Without basic hygiene (%)")
    ax.set_xlim(-2, 100); ax.set_ylim(-2, 100)
    ax.grid(color=GRID, lw=.8)
    ax.text(98, 5, f"Spearman rho = {a['rho']:.2f}, n = {a['n']} countries", ha="right", fontsize=8.3, color=INK)
    save(fig, "g2_poverty_hygiene")


# ---------------------------------------------------------------- G3 India vs South Asia vs world
def g3():
    keys = ["hygiene", "sanitation", "water", "climate"]
    labs = ["No basic hygiene", "No basic sanitation", "No basic drinking water", "High climate-hazard risk"]
    I = S["india"]
    fig, ax = plt.subplots(figsize=(FULL, 2.6))
    y = np.arange(len(keys))[::-1]
    h = .26
    for k, (g, c, lab) in enumerate([("IND", CLAY, "India"), ("SAS", SAGE, "South Asia"), ("WLD", MUTED, "World")]):
        vals = [I[kk].get(g, {}).get("v", np.nan) for kk in keys]
        ax.barh(y + (1 - k) * h, vals, h * .92, color=c, label=lab)
        for yi, v, kk in zip(y, vals, keys):
            yr = I[kk].get(g, {}).get("t", "")
            ax.text(v + .4, yi + (1 - k) * h, f"{v:.1f}% ({yr})", va="center", fontsize=7.3, color=SOFT)
    ax.set_yticks(y, labs)
    ax.set_xlim(0, 30)
    ax.set_xlabel("% of population")
    ax.grid(axis="x", color=GRID, lw=.8)
    ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    save(fig, "g3_india")


# ---------------------------------------------------------------- G4 India financing and maternal context (official headline figures)
def g4():
    fig, axes = plt.subplots(1, 3, figsize=(FULL, 2.5), gridspec_kw={"width_ratios": [1.1, 1.2, 1]})
    ax = axes[0]
    yrs, vals = ["2013–14", "2021–22", "2022–23"], [64.2, 39.4, 43.4]
    ax.bar(range(3), vals, .6, color=[MUTED, MUTED, CLAY])
    for i, v in enumerate(vals):
        ax.text(i, v + 1.5, f"{v:.1f}%", ha="center", fontsize=8.5, fontweight=600)
    ax.set_xticks(range(3), yrs, fontsize=8)
    ax.set_ylim(0, 75); ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_title("Out-of-pocket share of total\nhealth expenditure (NHA)", fontsize=8.5, loc="left")
    ax = axes[1]
    x = np.arange(2)
    ax.bar(x - .18, [14.1, 19.1], .34, color=MUTED, label="2017–18")
    ax.bar(x + .18, [47.4, 44.3], .34, color=TEAL, label="2025")
    for xi, a, b in zip(x, [14.1, 19.1], [47.4, 44.3]):
        ax.text(xi - .18, a + 1.5, f"{a}", ha="center", fontsize=8); ax.text(xi + .18, b + 1.5, f"{b}", ha="center", fontsize=8, fontweight=600)
    ax.set_xticks(x, ["Rural", "Urban"])
    ax.set_ylim(0, 72); ax.set_yticks([]); ax.spines["left"].set_visible(False)
    ax.legend(frameon=False, fontsize=7.5, loc="upper center", ncol=2, bbox_to_anchor=(.5, 1.0))
    ax.set_title("Reported health insurance\ncoverage, % (NSS 75th vs 80th)", fontsize=8.5, loc="left")
    ax = axes[2]
    ax.bar([0, 1], [93, 88], .55, color=[MUTED, CLAY])
    for i, v in enumerate([93, 88]):
        ax.text(i, v + 2, str(v), ha="center", fontsize=8.5, fontweight=600)
    ax.axhline(70, color=INK, lw=1, ls=(0, (3, 2)))
    ax.text(0.5, 73, "SDG\n< 70", fontsize=7, ha="center", va="bottom", color=INK, linespacing=1)
    ax.set_xticks([0, 1], ["2019–21", "2020–22"]); ax.set_ylim(0, 110); ax.set_yticks([]); ax.spines["left"].set_visible(False)
    ax.set_title("Maternal mortality ratio per\n100,000 live births (SRS)", fontsize=8.5, loc="left")
    fig.subplots_adjust(wspace=.35)
    save(fig, "g4_india_context")


for f in [g1, g2, g3, g4]:
    f()
print(sorted(p.name for p in OUT.glob("*.svg")))
