# What Drives Global Patenting Activity? — working paper (PDF)

Live dashboard: [ashuarora.com/patent-dashboard](https://ashuarora.com/patent-dashboard) · Working paper: [`outputs/patent-report.pdf`](outputs/patent-report.pdf)

This folder is self-contained. It holds the interactive dashboard (`outputs/patent-dashboard.html`) and builds the working paper PDF from it. Requirements: `pip install -r requirements.txt`, plus `playwright install chromium` for the PDF.

```bash
python3 make_figures.py    # Figures 1–6 as SVG -> figures/
python3 build_report.py    # -> outputs/patent-report.pdf
```

- **Figures** are regenerated from the results embedded in `outputs/patent-dashboard.html` (`DATA` = 141-country cross-section, `PANEL` = panel estimates). Figure 2's pooled and fixed-effects confidence intervals are recovered from the reported coefficients and p-values (normal approximation); the Negative Binomial intervals are those in Table 5.
- **Text and tables** follow the working paper.
- The regression and machine-learning estimates were produced in a separate notebook and exported into the dashboard; this folder does not re-estimate them.
- Fonts and stylesheet: `style/`.
