# Health Economics Data Finder

Live: [ashuarora.com/data-buff](https://ashuarora.com/data-buff) · Guide: [`outputs/data-finder-guide.pdf`](outputs/data-finder-guide.pdf)

This folder is self-contained: catalogue, data, code and built outputs. Requirements: `pip install -r requirements.txt`, plus `playwright install chromium` for the PDF.

```bash
python3 build.py   # datasets.json + Scorecard vision data + world map -> outputs/data-buff.html
```

- `datasets.json` is the hand-curated catalogue. Each entry has `status` (`checked` or `to_verify`) and, when checked, an `evidence` link to the source used, plus `checked_on` at the top of the file. New entries must carry a source link before they are marked `checked`.
- The hotspot map uses World Bank Group Scorecard vision indicators from `data/raw/`: food and nutrition insecurity, basic hygiene, sanitation and drinking water (shown as the share without access), and poverty at $3.00 a day. Only the latest country-year from 2015 onward is shown; nothing is estimated or filled in.
- Country outlines are in `data/world_map.json` (Natural Earth via world-atlas, projected to 960 × 500 px), rounded to whole pixels at build time. The guide's climate-hazard indicator is `data/raw/EN_CLM_VULN.xlsx`.
- `template.html` keeps the original Data Buff design system; the build only embeds data.

## User guide & issue briefs (PDF)

```bash
cd guide
python3 analysis.py        # Scorecard country analysis -> output/guide_stats.json
python3 make_figures.py    # SVG figures -> figures/
python3 build_guide.py     # -> ../outputs/data-finder-guide.pdf
```

Part A explains the Finder (worked example computed with the page's own ranking logic, design guide, ten comparability traps). Part B has four briefs: where basic health risks cluster (computed), India in the global picture (computed), financial protection and maternal health in India (official headline figures, quoted and labelled), and health workforce and migration (qualitative, with a data map).
