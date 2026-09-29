# What Drives Global Patenting Activity? — working paper (PDF)

Builds `patent-report.pdf` (on the site at `/patent-report.pdf`) from the author's Word working paper, in the same design as the Who Benefits report.

```bash
python3 make_figures.py    # Figures 1–6 as SVG -> figures/
python3 build_report.py    # -> wipo-patent-report.pdf (+ copy on the site)
```

- **Figures** are regenerated from the results embedded in `../site/patent-dashboard.html` (`DATA` = 141-country cross-section, `PANEL` = panel estimates). Figure 2's pooled and fixed-effects confidence intervals are recovered from the reported coefficients and p-values (normal approximation); the Negative Binomial intervals are those in Table 5.
- **Text and tables** follow the working paper.
- Fonts and the stylesheet are shared with `../who-benefits/report/`.
