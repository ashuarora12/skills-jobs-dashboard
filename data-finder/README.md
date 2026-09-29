# Health Economics Data Finder

Source for `/data-buff` (`site/data-buff.html`).

```bash
python3 build.py   # datasets.json + Scorecard vision data + world map -> data-buff.html
```

- `datasets.json` is the hand-curated catalogue. Each entry has `status` (`checked` or `to_verify`) and, when checked, an `evidence` link to the source used, plus `checked_on` at the top of the file. New entries must carry a source link before they are marked `checked`.
- The hotspot map uses World Bank Group Scorecard vision indicators from `../who-benefits/data/raw/`: food and nutrition insecurity, basic hygiene, sanitation and drinking water (shown as the share without access), and poverty at $3.00 a day. Only the latest country-year from 2015 onward is shown; nothing is estimated or filled in.
- Country outlines are taken from the patent dashboard's map (Natural Earth via world-atlas), rounded to whole pixels.
- `template.html` keeps the original Data Buff design system; the build only embeds data.

## User guide & issue briefs (PDF)

```bash
cd guide
python3 analysis.py        # Scorecard country analysis -> output/guide_stats.json
python3 make_figures.py    # SVG figures -> figures/
python3 build_guide.py     # -> data-finder-guide.pdf (+ copy on the site)
```

Part A explains the Finder (worked example computed with the page's own ranking logic, design guide, ten comparability traps). Part B has four briefs: where basic health risks cluster (computed), India in the global picture (computed), financial protection and maternal health in India (official headline figures, quoted and labelled), and health workforce and migration (qualitative, with a data map).
