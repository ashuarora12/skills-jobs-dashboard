# skills-jobs-dashboard

Reproducible code, data and reports for three development-data projects by **Ashu Arora** ([ashuarora.com](https://ashuarora.com)). They cover health, jobs, gender and innovation. Every number in the dashboards and PDF reports is produced by the scripts in this repository; none is typed in by hand.

| Project | Question | Methods | Live | Report | Code |
|---|---|---|---|---|---|
| **Who Benefits? Health, Jobs & Gender in the WBG Portfolio** | Who do World Bank Group operations reach, do they measure the health workforce, and are women counted and reached as planned? | Rule-based text classification with hand-checked precision · cross-validated early-warning model · propensity-score matching | [Data story](https://ashuarora.com/who-benefits-flow) | [PDF, 22 pp.](who-benefits/outputs/who-benefits-report.pdf) | [`who-benefits/`](who-benefits) |
| **What Drives Global Patenting Activity?** | How much of cross-country variation in resident patent filings do economic fundamentals explain, and is it between or within countries? | OLS · panel fixed effects · Negative Binomial · Gradient Boosting / Random Forest with country-grouped CV | [Dashboard](https://ashuarora.com/patent-dashboard) | [Working paper, 16 pp.](wipo-report/outputs/patent-report.pdf) | [`wipo-report/`](wipo-report) |
| **Health Economics Data Finder** | Which datasets can support a given health-economics research design in India, and where do basic health risks cluster? | Curated, source-checked catalogue · design-fit ranking · country analysis of Scorecard indicators | [Tool](https://ashuarora.com/data-buff) | [Guide & briefs, 12 pp.](data-finder/outputs/data-finder-guide.pdf) | [`data-finder/`](data-finder) |

## Headline results

- **Who Benefits?** Across 1,131 projects in 125 countries (FY25 Scorecard results), 15 projects report an indicator about health workers and none links them to migration. 22% of results reported for women are a fixed share of the total rather than a count. The early-warning model reaches an out-of-sample AUC of 0.77. The matched comparison finds no detectable fragility penalty in the gender delivery gap (−1.3 pp, 95% CI −8.7 to +6.8).
- **Patenting.** GDP per capita, population and energy use explain 73% of cross-country variation in log patent filings (R² = 0.733, 141 countries). With country and year fixed effects (2,201 country-years, 2000–2021), the GDP-per-capita elasticity falls from 0.51 to 0.017 (p = 0.96): the income–patents link is a between-country pattern.
- **Data Finder.** 24 evaluation-ready datasets, 17 checked against official sources. Poverty tracks missing basic hygiene closely across countries (Spearman rank correlation reported in the guide).

## Repository layout

Each project folder is self-contained, with its own code, data, requirements and built outputs. A folder can be downloaded and re-run on its own.

```
who-benefits/
  pipeline.py, build_page.py, report_stats.py   analysis and dashboard build
  data/raw/        World Bank Group Scorecard exports, FY25 cycle
  validation/      hand-labelled samples used to measure classifier precision
  report/          report figures and PDF build
  outputs/         data story and dashboards (HTML), report (PDF)
wipo-report/
  make_figures.py, build_report.py              working-paper figures and PDF build
  outputs/         interactive dashboard (HTML), working paper (PDF)
data-finder/
  datasets.json    source-checked dataset catalogue
  build.py         builds the tool from the catalogue, data/raw/ and data/world_map.json
  guide/           country analysis, figures and user-guide PDF build
  outputs/         the tool (HTML), user guide and issue briefs (PDF)
```

## Reproduce

Python 3.11. Inside any project folder:

```bash
pip install -r requirements.txt
playwright install chromium        # used to render the PDFs
```

| Project | Commands (run inside the folder) |
|---|---|
| `who-benefits/` | `python3 pipeline.py && python3 build_page.py && python3 report_stats.py && python3 report/make_figures.py && python3 report/build_report.py` (about 1 minute) |
| `wipo-report/` | `python3 make_figures.py && python3 build_report.py` |
| `data-finder/` | `python3 build.py && cd guide && python3 analysis.py && python3 make_figures.py && python3 build_guide.py` |

Each project was rebuilt in isolation, with the other two folders absent. The rebuilt JSON outputs and HTML pages are identical to the published ones, and the PDFs rebuild with the same pages and fonts. Only timestamps and internal IDs inside the SVG figures change. Each folder's README has details.

**Note on the patent study.** The regression and machine-learning estimates were produced in a separate notebook and exported into `wipo-report/outputs/patent-dashboard.html`. This repository regenerates the working paper's figures and PDF from those exported results.

## Data and licences

- World Bank Group Scorecard and World Development Indicators data: © World Bank, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- Resident patent applications: WIPO, via World Bank indicator IP.PAT.RESD. Country panel: [Our World in Data](https://github.com/owid/co2-data) (CC BY 4.0).
- Map outlines: Natural Earth via world-atlas (public domain).
- Fonts (copies in each project): Source Sans 3, Source Serif 4, IBM Plex Mono (SIL Open Font License).

The analysis, text and reports are © Ashu Arora. This is independent work and is not endorsed by the World Bank Group or WIPO.
