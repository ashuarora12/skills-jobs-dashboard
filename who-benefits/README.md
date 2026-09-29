# Who Benefits? Health, Jobs & Gender in the WBG Portfolio

Source for the dashboard at `/who-benefits` (`site/who-benefits.html`) plus alternatives: story-first at `/who-benefits-story`, a sidebar design at `/who-benefits-studio` (`redesign_shell.html`), and a standalone scroll-driven data story at `/who-benefits-flow` (`flow_template.html`). All read the same `dashboard_data.json`.

## Rebuild

```bash
pip install -r requirements.txt
python3 pipeline.py     # raw Scorecard exports -> output/dashboard_data.json
python3 build_page.py   # embeds the JSON into page_template.html -> all site pages

# written report (PDF)
python3 report_stats.py            # uncertainty + robustness stats -> output/report_stats.json
python3 report/make_figures.py     # SVG figures -> report/figures/
python3 report/build_report.py     # -> report/who-benefits-report.pdf (+ copy on the site)
```

The report adds Wilson intervals for classifier precision, a cluster-bootstrap CI for the model AUC, a timing-only baseline, and regression-adjustment checks of the matched estimate.

Every number on the page comes from `pipeline.py`. Nothing is typed into the page by hand.

## Data (`data/raw/`)

World Bank Group Scorecard exports (scorecard.worldbank.org), FY25 cycle, results as of 30 June 2025:

| File | Content |
|---|---|
| `CSC_RES_HEA_SERV.xlsx` | People receiving quality health, nutrition & population services + project records |
| `CSC_RES_WAT_SAN_HYG_TOT.xlsx` | People provided with water, sanitation and/or hygiene + project records |
| `CSC_RES_GEN_EQU_BENE.xlsx` | Gender-equality / economic-opportunity actions + project records |
| `CSC_RES_FIN_SERV_WOM.xlsx` | Financial-services users incl. women + project records |
| `CSC_RES_HEA_EMER_BENE.xlsx` | Economies with strengthened health-emergency capacity |
| `SI_POV_DDAY_TO.xlsx`, `SI_POV_PROS.xlsx`, `SN_ITK_MSFI_ZS.xlsx`, `SH_H2O_STA_HYGN_TO.xlsx` | Scorecard vision (context) indicators |

Notes on the exports:
- `ACW` means **All countries**. The seven regions sum to it, and `pipeline.py` asserts this.
- Each figure appears twice, once with `Disability_Inclusive_Flag = Total` (all projects) and once with `Yes` (a subset). Only `Total` is used.
- Many female figures are derived as `total × fixed share` (`Progress_Disaggregation_Factor` strictly between 0 and 1). Those results can't show a gender delivery gap, so section 04 excludes them and reports how many there are.

## Methods

1. **Regional results.** Achieved vs. expected, and women's share, by region.
2. **Text classifier.** Regex rules over each project's development objective and indicator text. Precision is checked by hand on random samples in `validation/`. `theme_review_v1.csv` is the first rule set, which failed for the health-workforce and care-economy themes; `theme_review.csv` is the current one. The labels are a draft review and should be confirmed by the author.
3. **Delivery-gap model.** Predicts whether a result is *behind*, meaning share of target delivered < share of implementation period elapsed − 10 pp. It compares logistic regression with gradient boosting, uses 5-fold CV grouped by project, reports permutation importance and calibration, and breaks performance down by region, FCS status and income group.
4. **Gender delivery gap + propensity-score matching.** Compares FCS with non-FCS results using 1:1 nearest-neighbour matching with replacement (caliper 0.2 SD of the logit). The confidence interval comes from a bootstrap clustered by project, and balance is reported as standardised mean differences.

Uses only public, aggregated, project-level data; no personal data.
