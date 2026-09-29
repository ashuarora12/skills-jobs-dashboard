"""
Build the WIPO working paper PDF in the same design as the Who Benefits report.

  python3 make_figures.py && python3 build_report.py

Text follows the author's Word working paper (WIPO_patent_analysis_report_ashu_arora.docx).
Figures are regenerated from the data embedded in patent-dashboard.html; tables are
as reported in the working paper (checked against the same data).
"""
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright
from pypdf import PdfReader, PdfWriter

HERE = Path(__file__).parent
BUILD = HERE / "build"
BUILD.mkdir(exist_ok=True)
CSS = "../style/report.css"
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
OUT_PDF = HERE / "outputs" / "patent-report.pdf"
TITLE = "What Drives Global Patenting Activity?"

src = (HERE / "outputs" / "patent-dashboard.html").read_text()
DATA = json.loads(re.search(r"const DATA = (\{.*?\});", src, re.S).group(1))
TOP5 = sorted(DATA["countries"], key=lambda c: -c["patents_residents"])[:5]
TOP5_SHARE = sum(c["patents_residents"] for c in TOP5) / DATA["total_patents"]
SRC = "Source: author's analysis of resident patent applications (WIPO, via World Bank indicator IP.PAT.RESD) and Our World in Data's country panel."


# ---------------------------------------------------------------- helpers
def fig(name, num, title, sub, note, acc="var(--navy)"):
    svg = (HERE / "figures" / f"{name}.svg").read_text()
    svg = re.sub(r"<\?xml.*?\?>", "", svg, flags=re.S)
    svg = re.sub(r"<!DOCTYPE.*?>", "", svg, flags=re.S)
    svg = re.sub(r'\swidth="[^"]+"\sheight="[^"]+"', "", svg, count=1)
    return (f'<figure style="--acc:{acc}"><div class="cap"><span class="fl">Figure {num}</span>{title}</div>'
            f'<div class="sub">{sub}</div><div class="art">{svg}</div><div class="note">{note}</div></figure>')


def chapter(n, cls, title, lede):
    return (f'<section class="pb"><div class="marker">@@CH{n}@@</div><div class="ch-open {cls}"><div class="num">{n}</div>'
            f'<div class="k">Section {n}</div><h1>{title}</h1><p>{lede}</p></div>')


def sec(num, cls, t):
    return f'<h2 class="sec"><span class="sn {cls}">{num}</span>{t}</h2>'


def tbl(cls, head, rows, align=None):
    align = align or [""] * len(head)
    h = "".join(f'<th class="{a}">{x}</th>' for x, a in zip(head, align))
    b = "".join("<tr>" + "".join(f'<td class="{a}">{x}</td>' for x, a in zip(r, align)) + "</tr>" for r in rows)
    return f'<table class="tbl"><tr class="{cls}">{h}</tr>{b}</table>'


def tcap(num, text):
    return f'<div class="tcap">Table {num} &nbsp;{text}</div>'


# MathML building blocks
NORMAL = ' mathvariant="normal"'
mi = lambda x, v=False: f"<mi{NORMAL if v else ''}>{x}</mi>"
mo = lambda x: f"<mo>{x}</mo>"
mn = lambda x: f"<mn>{x}</mn>"
sub = lambda b, s: f"<msub>{b}{s}</msub>"
row = lambda *xs: "<mrow>" + "".join(xs) + "</mrow>"
txt = lambda x, s: sub(mi(x, True), mi(s))
ln = lambda *xs: mi("ln", True) + mo("&#x2061;") + mo("(") + "".join(xs) + mo(")")
b = lambda k: sub(mi("β"), mn(k))


def eq(n, body):
    return (f'<div class="eqn"><math display="block">{body}</math><span class="eqno">({n})</span></div>')


def rhs(s):
    return (b(0) + mo("+") + b(1) + ln(txt("GDPpc", s)) + mo("+") + b(2) + ln(txt("Pop", s))
            + mo("+") + b(3) + ln(txt("EnergyPC", s)))


E1 = eq(1, txt("PatentsPerMillion", "i") + mo("=") + "<mfrac>" + txt("Patents", "i")
        + row(txt("Population", "i"), mo("/"), "<msup>" + mn("10") + mn("6") + "</msup>") + "</mfrac>")
E2 = eq(2, ln(mn("1"), mo("+"), txt("Patents", "i")) + mo("=") + rhs("i") + mo("+") + sub(mi("ε"), mi("i")))
E3 = eq(3, ln(mn("1"), mo("+"), txt("Patents", "it")) + mo("=") + sub(mi("α"), mi("i")) + mo("+") + sub(mi("γ"), mi("t"))
        + mo("+") + b(1) + ln(txt("GDPpc", "it")) + mo("+") + b(2) + ln(txt("Pop", "it"))
        + mo("+") + b(3) + ln(txt("EnergyPC", "it")) + mo("+") + sub(mi("ε"), mi("it")))
E4 = eq(4, "<mtable columnalign='left'><mtr><mtd>"
        + mi("E", True) + mo("[") + txt("Patents", "it") + mo("|") + sub(mi("X"), mi("it")) + mo("]") + mo("=")
        + mi("exp", True) + mo("(") + b(0) + mo("+") + b(1) + mi("ln", True) + txt("GDPpc", "it") + mo("+") + b(2)
        + mi("ln", True) + txt("Pop", "it") + mo("+") + b(3) + mi("ln", True) + txt("EnergyPC", "it") + mo(")")
        + "</mtd></mtr><mtr><mtd>" + mi("Var", True) + mo("=") + mi("μ") + mo("+") + mi("α") + "<msup>" + mi("μ") + mn("2") + "</msup>"
        + "</mtd></mtr></mtable>")
hm = lambda k: sub(mi("γ"), mi(k)) + sub(mi("h"), mi(k)) + mo("(") + mi("x") + mo(")")
E5 = eq(5, sub("<mover>" + mi("F") + mo("^") + "</mover>", mi("M")) + mo("(") + mi("x") + mo(")") + mo("=")
        + "<munderover>" + mo("∑") + row(mi("m"), mo("="), mn("1")) + mi("M") + "</munderover>" + hm("m")
        + "<mspace width='2em'/>" + sub(mi("F"), mi("m")) + mo("(") + mi("x") + mo(")") + mo("=")
        + sub(mi("F"), row(mi("m"), mo("−"), mn("1"))) + mo("(") + mi("x") + mo(")") + mo("+") + hm("m"))
yi, yh, yb = sub(mi("y"), mi("i")), sub("<mover>" + mi("y") + mo("^") + "</mover>", mi("i")), "<mover>" + mi("y") + mo("‾") + "</mover>"
E6 = eq(6, "<msup>" + mi("R") + mn("2") + "</msup>" + mo("=") + mn("1") + mo("−") + "<mfrac>"
        + row(mo("∑"), "<msup>" + row(mo("("), yi, mo("−"), yh, mo(")")) + mn("2") + "</msup>")
        + row(mo("∑"), "<msup>" + row(mo("("), yi, mo("−"), yb, mo(")")) + mn("2") + "</msup>") + "</mfrac>")
E7 = eq(7, sub("<mover>" + mi("ε") + mo("^") + "</mover>", mi("i")) + mo("=") + yi + mo("−") + yh
        + mo(",") + "<mspace width='1.5em'/>" + yi + mo("=") + ln(mn("1"), mo("+"), txt("Patents", "i")))


# ---------------------------------------------------------------- body
def body(toc):
    toc_rows = [
        ("1", "c1", "Introduction", []),
        ("2", "c2", "Data", ["2.1 Sources", "2.2 Cleaning and validation", "2.3 Descriptive statistics (cross-section)", "2.4 Panel dataset"]),
        ("3", "c4", "Methodology", ["3.1 Outcome variable", "3.2 Baseline regression specification", "3.3 Panel fixed effects", "3.4 Count-data model", "3.5 Machine-learning comparison", "3.6 Validation"]),
        ("4", "c5", "Results", ["4.1 Baseline cross-sectional regression", "4.2 Panel fixed-effects results", "4.3 Count-model results", "4.4 Robustness across specifications", "4.5 Machine-learning comparison", "4.6 Over- and under-performers"]),
        ("5", "c3", "Discussion", []),
        ("6", "c6", "Limitations and future work", []),
        ("7", "c8", "Conclusion", []),
    ]
    toc_html = (f'<div class="toc-row"><span class="n cn">★</span><span class="t">Key messages</span><span class="pg">{toc.get("KM", "")}</span></div>'
                + "".join(f'<div class="toc-row"><span class="n {c}">{n}</span><span class="t">{t}</span><span class="pg">{toc.get("CH" + n, "")}</span></div>'
                          + (f'<div class="toc-subs">{" · ".join(s)}</div>' if s else "") for n, c, t, s in toc_rows)
                + f'<div class="toc-row"><span class="n cn">R</span><span class="t">References</span><span class="pg">{toc.get("REF", "")}</span></div>')
    B = lambda x: f"<b>{x}</b>"
    return f"""
<section class="about">
  <div class="front-h">Abstract</div>
  <p class="abs">This paper examines what predicts cross-country variation in resident patent filings, using two complementary datasets built from WIPO and World Bank patent statistics matched with Our World in Data's economic panel: a 141-country cross-section (most recent year per country) and a 2201-observation panel spanning 136 countries and 2000–2021. A baseline log-linear regression on the cross-section explains 73% of variance (R² = 0.733). Adding country and year fixed effects to the panel changes the picture substantially: the GDP-per-capita elasticity collapses from 0.51 (pooled, clustered SE) to a statistically indistinguishable-from-zero 0.017 (p = 0.96) once persistent country characteristics are absorbed, while population and energy-use elasticities remain large and significant. A Negative Binomial count model — the specification standard in the patents-econometrics literature since Hausman, Hall and Griliches (1984) — corroborates this pattern on the untransformed count data. Gradient Boosting and Random Forest, evaluated with country-grouped cross-validation to prevent leakage, offer at most a modest accuracy gain over the linear model. Korea, Japan, and China file substantially more patents than fundamentals predict; several resource-wealthy small economies file substantially fewer.</p>
  <h4>About this paper</h4>
  <p>Prepared as a data-science portfolio project for the WIPO Data Scientist posting (Vacancy 26261-TA). It is an independent working paper by the author and is not a WIPO publication. Findings and interpretations are the author's own.</p>
  <h4>Suggested citation</h4>
  <div class="cite">Arora, Ashu. 2026. <em>What Drives Global Patenting Activity? A Panel and Cross-Sectional Econometric Analysis of Resident Patent Filings, Economic Development, and Industrial Intensity.</em> Working paper, September 2026.</div>
  <h4>Contents</h4>
  <div class="toc">{toc_html}</div>
</section>

<section class="pb"><div class="marker">@@KM@@</div>
  <div class="km-head"><div class="k">Key messages</div><h2>Income, scale and industry: what predicts patenting</h2>
  <p>Resident patent filings across 141 countries (cross-section) and 136 countries, 2000–2021 (panel)</p></div>
  <div class="stats">
    <div class="stat c2"><b>2,292,209</b><span>resident patent filings covered, 141 countries</span></div>
    <div class="stat c1"><b>0.733</b><span>R² of the baseline cross-sectional regression</span></div>
    <div class="stat c5"><b>0.51 → 0.02</b><span>GDP-per-capita elasticity, pooled vs. country and year fixed effects</span></div>
    <div class="stat c4"><b>0.739</b><span>best out-of-sample R² (Gradient Boosting) vs. 0.726 linear</span></div>
  </div>
  <div class="km"><span class="n c2">1</span><div><h4>Fundamentals explain most cross-country variation</h4><p>GDP per capita, population and energy use per capita explain 73% of the variance in log resident patent filings across 141 countries (R² = 0.733).</p></div></div>
  <div class="km"><span class="n c5">2</span><div><h4>The income–patents link is a between-country pattern</h4><p>With country and year fixed effects, the GDP-per-capita elasticity falls from 0.51 to 0.017 (p = 0.96). Richer countries patent more, but the data do not show a country patenting more as its own income rises.</p></div></div>
  <div class="km"><span class="n c1">3</span><div><h4>Scale and industrial intensity are more robust</h4><p>Population (1.96, p = 0.001) and energy use per capita (0.68, p = 0.028) remain positive and significant with fixed effects; the population estimate is imprecise and should be read cautiously.</p></div></div>
  <div class="km"><span class="n c4">4</span><div><h4>Count models and machine learning do not overturn the pattern</h4><p>A Negative Binomial model on raw counts corroborates the pooled pattern. With country-grouped cross-validation, Gradient Boosting improves only modestly on the linear model (R² 0.739 vs. 0.726) and Random Forest does worse (0.690).</p></div></div>
  <div class="km"><span class="n c8">5</span><div><h4>Some countries punch above their weight</h4><p>Korea, Japan and China file substantially more than fundamentals predict; several small, resource-wealthy economies (Kuwait, the UAE, Bahrain) file substantially fewer.</p></div></div>
</section>

{chapter(1, 'c1', 'Introduction', 'Across the world’s countries, how much of the variation in resident patent filings do basic economic fundamentals explain?')}
<p>Patent activity is one of the most widely used proxies for a country's inventive capacity, and understanding what drives it matters directly for the kind of statistical and policy work the World Intellectual Property Organization (WIPO) produces: cross-country IP statistics, development indicators, and evidence for policymakers on how innovation systems relate to economic outcomes. This paper asks a simple version of that question — across the world's countries, how much of the variation in resident patent filings can be explained by basic economic fundamentals, which of that variation is a persistent between-country difference versus something that moves within a country over time, and which countries deviate most from what those fundamentals predict?</p>
<p>The question has a long empirical lineage. WIPO's own Global Innovation Index (co-published with Cornell and INSEAD) benchmarks over 130 economies each year on a weighted composite of roughly 80 indicators, and a large literature since at least Hausman, Hall and Griliches (1984) has studied patent counts econometrically, establishing that patent data are better modeled as counts — via Poisson or Negative Binomial regression — than analyzed as a continuous, normally-distributed outcome. This paper does not aim to out-perform either tradition; instead it combines them in a single, fully reproducible pipeline: an interpretable cross-sectional regression, a panel specification with country and year fixed effects that separates persistent cross-country differences from within-country movement, a count-data model consistent with the patents-econometrics literature, and a machine-learning benchmark evaluated with methodologically appropriate (grouped) cross-validation.</p>
<p>We combine WIPO's own patent-filing statistics with a country-level economic panel from Our World in Data and build two analysis datasets from the same underlying sources: a broad cross-section (one recent year per country, for descriptive work and the accompanying dashboard) and a genuine multi-year panel (2,201 country-year observations, 136 countries, 2000–2021) for the core econometric analysis. Every figure and coefficient in this report is computed from the accompanying notebook and dataset, not illustrative or approximate.</p>
<div class="flow">
  <div class="c2"><b>Cross-section</b>141 countries, latest year each; OLS and over/under-performers</div>
  <div class="c4"><b>Panel</b>2,201 country-years, 136 countries, 2000–2021</div>
  <div class="c5"><b>Specifications</b>Pooled OLS, country and year fixed effects, Negative Binomial</div>
  <div class="c1"><b>Benchmark</b>Gradient Boosting and Random Forest, country-grouped 5-fold CV</div>
</div>
</section>

{chapter(2, 'c2', 'Data', 'Two public sources, cleaned of regional aggregates and merged into a cross-section and a panel.')}
{sec('2.1', 't2', 'Sources')}
<p>Two public sources are combined:</p>
<ul>
<li><strong>Patent applications, residents</strong> (World Bank indicator IP.PAT.RESD) — originally compiled by WIPO’s <em>Patent Report: Statistics on Worldwide Patent Activity</em>. Covers 1980–2021 for most reporting countries.</li>
<li><strong>Country-year economic panel</strong> (Our World in Data), providing population, GDP, and energy consumption; the underlying series trace to the World Bank and the Maddison Project Database. Covers 2015–2022 for the window used here.</li>
</ul>
<p>Table 1 summarizes both sources.</p>
{tcap(1, 'Data sources used in this analysis')}
{tbl('c2', ['Source', 'Provider', 'Variables used', 'Coverage'], [
    ['<span class="mono">IP.PAT.RESD</span>', 'WIPO / World Bank', 'Resident patent applications', '1980–2021, 190 entities'],
    ['<span class="mono">owid-co2-data</span>', 'Our World in Data', 'Population, GDP, energy per capita', '1750–2023, 220+ entities']])}
{sec('2.2', 't2', 'Cleaning and validation')}
<p>Two data-quality issues require explicit handling:</p>
<ul>
<li>World Bank country panels mix individual countries with regional and income-group aggregates (e.g. "World", "High income", "East Asia &amp; Pacific") that carry the same three-letter code format. Left unfiltered, these aggregates would double-count activity and distort any cross-country model. We remove them using the World Bank’s own aggregate-entity code list before analysis.</li>
<li>Reporting lags differ by country and by source, so no single calendar year has complete coverage. We take each country’s most recent available observation in each source (patents through 2021; economic indicators through 2022) — standard practice for cross-sectional analysis of international statistics with uneven reporting, though it does mean the "year" compared across countries is not perfectly aligned.</li>
</ul>
<p>After merging on ISO-3 country code and dropping rows with missing values in any modeling variable, the analysis dataset covers <strong>141 countries and 2,292,209 resident patent filings</strong> in total — including every one of the world's ten largest absolute filers.</p>
{sec('2.3', 't2', 'Descriptive statistics (cross-section)')}
<p>The five largest filers by absolute count, from the cross-sectional dataset:</p>
<div class="keep">{tcap(2, 'Top 5 countries by absolute resident patent filings')}
{tbl('c2', ['Country', 'Resident patents', 'Per million people', 'GDP per capita (US$)'], [
    ['China', '1,426,644', '1001.0', '$18,921'], ['United States', '262,244', '767.8', '$57,075'],
    ['Japan', '222,452', '1752.8', '$38,239'], ['Korea, Rep.', '186,245', '3596.7', '$41,280'],
    ['Germany', '39,822', '473.6', '$46,495']], ['', 'num', 'num', 'num'])}</div>
<p style="margin-top:8pt">Patent counts, GDP, and population are all extremely right-skewed — a small number of very large filers/economies alongside a long tail of small ones — which motivates modeling in log space rather than levels (Section 3).</p>
{fig('f1_gdp_intensity', 1, 'GDP per capita vs. patenting intensity, 141 countries (both axes log-scaled)', 'Each dot is a country, coloured by region; latest available year', SRC, 'var(--blue)')}
{sec('2.4', 't2', 'Panel dataset')}
<p>The cross-section above collapses each country to a single year, which discards most of the available history and cannot separate a persistent, between-country association (rich countries simply patent more) from a within-country one (a given country patenting more as it grows richer). To address this, we build a second dataset that keeps the full country-year structure: merging the same two sources on country code and year for 2000–2021 yields <strong>2,201 country-year observations across 136 countries</strong>, averaging 16.2 years of coverage per country. This panel, not the single-year cross-section, is the basis for the fixed-effects and count-data models in Sections 3.3–3.4 and the results in Sections 4.2–4.5; the cross-section remains the basis for the descriptive figures above, the over/under-performer ranking in Section 4.6, and the accompanying dashboard.</p>
</section>

{chapter(3, 'c4', 'Methodology', 'A log-linear baseline, panel fixed effects, a count-data model and a grouped-validation machine-learning benchmark.')}
{sec('3.1', 't4', 'Outcome variable')}
<p>The primary normalized outcome used for cross-country comparison is patents per million people:</p>
{E1}
<p>For the regression, the outcome is modeled in log space to accommodate the extreme right-skew in raw patent counts: ln(1 + Patents), where the +1 offset (a standard "log1p" transform) allows countries with zero recorded filings in a given year to remain in the sample.</p>
{sec('3.2', 't4', 'Baseline regression specification')}
<p>We first estimate an ordinary least squares (OLS) regression of log patent filings on three log-transformed economic fundamentals — GDP per capita (development level), population (economic scale), and energy use per capita (a proxy for industrial/technological intensity) — on the cross-sectional dataset:</p>
{E2}
<p>All variables are logged so that the estimated coefficients (β₁, β₂, β₃) are interpretable directly as elasticities — the percentage change in patent filings associated with a 1% change in each predictor, holding the others fixed. This baseline is retained as an easily-communicated headline number, but Sections 3.3–3.4 go further using the panel dataset.</p>
{sec('3.3', 't4', 'Panel fixed effects')}
<p>A cross-sectional regression cannot distinguish a between-country association (rich countries simply patent more, for reasons that may have nothing to do with income itself) from a within-country one (a given country patenting more as its income rises). Using the panel dataset (Section 2.4), we re-estimate the same specification with country fixed effects αᵢ and year fixed effects γₜ added:</p>
{E3}
<p>The country fixed effects αᵢ absorb every time-invariant country characteristic — legal system, language, geography, long-run institutional quality — so the coefficients are identified purely from within-country movement over time; the year fixed effects γₜ absorb global shocks common to all countries in a given year (e.g. a worldwide dip in filings). Standard errors are clustered by country throughout to allow for arbitrary serial correlation within a country’s own time series.</p>
{sec('3.4', 't4', 'Count-data model')}
<p>Patent filings are non-negative integer counts, not a continuous, normally-distributed quantity, and the log(1+x) transform used above is a convenient approximation rather than a model of the actual data-generating process. Following the approach standard in the patents-econometrics literature since Hausman, Hall and Griliches (1984), we additionally fit a Negative Binomial regression directly on the untransformed counts:</p>
{E4}
<p>The Negative Binomial model adds a dispersion parameter α that lets the variance exceed the mean (Var = μ + αμ²), unlike the plainer Poisson model, which forces Var = μ. We first fit a Poisson specification and compare its implied variance to the raw variance of the data as a diagnostic; strong overdispersion supports using the Negative Binomial specification instead (Section 4.3).</p>
{sec('3.5', 't4', 'Machine-learning comparison')}
<p>As a further robustness check, we fit Gradient Boosting and Random Forest regressors on the same three predictors, using the panel dataset. Gradient Boosting builds an ensemble of shallow decision trees sequentially, with each new tree fit to the residual errors of the ensemble so far:</p>
{E5}
<p>where h<sub>m</sub>(x) is the m-th weak learner (a depth-2 decision tree here) and γ<sub>m</sub> its contribution weight. Random Forest instead averages many deep, independently-grown trees. Because both can capture non-linearities and interactions the linear model cannot, comparing them tells us whether such effects matter in practice for this question.</p>
{sec('3.6', 't4', 'Validation')}
<p>Both ML models are evaluated using 5-fold cross-validation, grouped by country: every observation from a given country falls entirely within one fold, so no model ever sees part of a country’s history during training and is tested on the rest of that same country — a leakage risk that a naive random split of panel data would not catch, since consecutive years from the same country are highly correlated. Reported R² and MAE are computed on these out-of-sample, grouped predictions:</p>
{E6}
</section>

{chapter(4, 'c5', 'Results', 'The income–patents association survives pooling and count models but not country fixed effects.')}
{sec('4.1', 't5', 'Baseline cross-sectional regression')}
<p>The cross-sectional regression explains 73.3% of the variance in log patent filings (R² = 0.733, adjusted R² = 0.727; F(3, 137) = 125.4, p &lt; 0.001; n = 141).</p>
<div class="keep">{tcap(3, 'Baseline OLS regression, cross-sectional dataset')}
{tbl('c5', ['Variable', 'Coefficient', 'Std. Error', 't-stat', 'p-value', '95% CI'], [
    ['Intercept', '−29.697', '1.834', '−16.19', B('&lt;0.001'), '[−33.32, −26.07]'],
    ['ln(GDP per capita)', '1.113', '0.348', '3.20', B('0.002'), '[0.42, 1.80]'],
    ['ln(Population)', '1.208', '0.078', '15.54', B('&lt;0.001'), '[1.05, 1.36]'],
    ['ln(Energy per capita)', '0.429', '0.274', '1.56', '0.120', '[−0.11, 0.97]']], ['', 'num', 'num', 'num', 'num', 'num'])}
<div class="note">Dependent variable: ln(1 + resident patent applications). Bold p-values are significant at the 5% level.</div></div>
<p>All three coefficients carry the theoretically expected positive sign, with population the strongest and most precisely estimated predictor. Section 4.2 asks whether this cross-sectional pattern survives once we control for persistent, unobserved country characteristics.</p>
{sec('4.2', 't5', 'Panel fixed-effects results')}
<p>Re-estimating on the 2,201-observation panel (136 countries, 2000–2021) without fixed effects but with country-clustered standard errors reproduces the cross-sectional pattern closely (Table 4, column 1). Adding country and year fixed effects (column 2) changes it substantially:</p>
<div class="keep">{tcap(4, 'Pooled vs. fixed-effects estimates on the panel dataset')}
{tbl('c5', ['Variable', 'Pooled (panel, clustered SE)', 'Fixed effects (country + year)'], [
    ['ln(GDP per capita)', '0.51 *', '0.02'], ['ln(Population)', '1.20 ***', '1.96 ***'], ['ln(Energy per capita)', '1.01 ***', '0.68 **']], ['', 'num', 'num'])}
<div class="note">Dependent variable: ln(1 + resident patent applications). *** p&lt;0.01, ** p&lt;0.05, * p&lt;0.1. Fixed-effects model: within R² = 0.160, overall R² = 0.338, 136 entities.</div></div>
<ul>
<li><strong>GDP per capita</strong>’s coefficient falls from 0.51 (pooled) to 0.017 and becomes statistically indistinguishable from zero (p = 0.96) once country and year fixed effects are included. In other words, the well-known cross-country correlation between income and patenting appears to be almost entirely a between-country pattern — richer countries simply patent more, for reasons fixed effects absorb — rather than evidence that a country patents more as its own income rises.</li>
<li><strong>Population</strong>’s coefficient rises sharply, from 1.20 to 1.96 (p = 0.001), though with a wide confidence interval [0.79, 3.14]. Within a country, population changes slowly and smoothly, so this within-country estimate should be read cautiously — it is likely partly absorbing a general growth trend in filings common to countries with growing populations, rather than a precise causal elasticity.</li>
<li><strong>Energy use per capita</strong> remains positive and significant in both specifications (1.01 pooled; 0.68 with fixed effects, p = 0.028), suggesting industrial/technological intensity has both a between- and a within-country association with patenting activity.</li>
</ul>
<p>An F-test for poolability strongly rejects the restriction that fixed effects are jointly zero (p &lt; 0.001), confirming that unobserved, persistent country characteristics matter and that the pooled specification alone would be misleading.</p>
{sec('4.3', 't5', 'Count-model results')}
<p>The raw patent-count data are highly overdispersed: across the panel, the variance of resident patent counts exceeds the mean by a factor of roughly 523,391, driven by the enormous gap between a handful of very large filers (China, the United States) and the long tail of small ones — far more dispersion than the Poisson model’s assumption that variance equals the mean allows for. This motivates the Negative Binomial specification (Section 3.4), whose fitted dispersion parameter α̂ = 1.34 is itself highly significant (p &lt; 0.001), confirming overdispersion directly.</p>
<div class="keep">{tcap(5, 'Negative Binomial regression on raw resident patent counts (panel dataset)')}
{tbl('c5', ['Variable', 'Coefficient', 'Std. Error', 't-stat', 'p-value', '95% CI'], [
    ['ln(GDP per capita)', '0.218', '0.064', '3.42', '&lt;0.001', '[0.09, 0.34]'],
    ['ln(Population)', '1.236', '0.015', '81.32', '&lt;0.001', '[1.21, 1.27]'],
    ['ln(Energy per capita)', '1.338', '0.051', '26.33', '&lt;0.001', '[1.24, 1.44]']], ['', 'num', 'num', 'num', 'num', 'num'])}
<div class="note">Coefficients are elasticities via the log link, directly comparable to the OLS specifications above.</div></div>
<p>Modeling the counts directly, all three predictors are positive and highly significant, more closely resembling the pooled cross-sectional pattern than the fixed-effects one. This is expected: like the pooled OLS, the Negative Binomial specification here does not include country fixed effects, so it is answering the between-country question, not the within-country one — a useful reminder that model class (linear vs. count) and specification (pooled vs. fixed-effects) are separate choices that both matter.</p>
{sec('4.4', 't5', 'Robustness across specifications')}
<p>Figure 2 places all three specifications’ coefficients and 95% confidence intervals side by side. The pattern is consistent across GDP per capita’s confidence interval crossing zero only in the fixed-effects specification, while population and energy use per capita remain positive throughout:</p>
{fig('f2_coefplot', 2, 'Coefficient estimates and 95% confidence intervals across the three main specifications', 'Panel dataset, 2,201 country-years, 136 countries; dashed line at zero', SRC + ' Pooled and fixed-effects intervals are recovered from the reported coefficients and p-values (normal approximation); Negative Binomial intervals as in Table 5.', 'var(--clay)')}
{sec('4.5', 't5', 'Machine-learning comparison')}
<p>Using the panel dataset with country-grouped 5-fold cross-validation (Section 3.6), Gradient Boosting and Random Forest are compared against the pooled linear model:</p>
{tcap(6, 'Five-fold, country-grouped cross-validated out-of-sample performance, panel dataset')}
{tbl('c5', ['Model', 'Out-of-sample R²', 'Out-of-sample MAE'], [
    ['Linear (pooled)', '0.726', '1.059'], [B('Gradient Boosting'), B('0.739'), B('1.054')], ['Random Forest', '0.690', '1.165']], ['', 'num', 'num'])}
<p style="margin-top:8pt">Gradient Boosting improves modestly on the linear model (R² 0.739 vs. 0.726); Random Forest performs worse (R² 0.690), plausibly because it does not share Gradient Boosting’s sequential error-correction and overfits the noisier within-country variation once grouped cross-validation removes the easy wins a random split would allow. As with the cross-sectional comparison, the modest gap between linear and non-linear models favors leading with the interpretable specification.</p>
<div class="pair">
{fig('f3_importance', 3, 'Gradient Boosting feature importance (panel dataset)', 'Impurity-based importance, sums to 1', SRC, 'var(--plum)')}
{fig('f4_fit', 4, 'Cross-sectional model fit: actual vs. OLS-predicted log patent filings', '141 countries; dashed line = perfect fit', SRC, 'var(--blue)')}
</div>
{fig('f5_top15', 5, 'Top 15 countries by absolute resident patent filings (cross-section)', 'Latest available year (2021 for all 15)', SRC, 'var(--blue)')}
{sec('4.6', 't5', 'Over- and under-performers')}
<p>Returning to the cross-sectional dataset, subtracting each country’s model-predicted filing rate from its actual rate identifies countries whose innovation output deviates most from what economic fundamentals alone would predict. This is a between-country lens, consistent with the pooled (not fixed-effects) specification, and is best read as "which countries look unusual given where they sit globally" rather than a claim about within-country causal effects:</p>
{E7}
{fig('f6_residuals', 6, 'Countries filing substantially more (blue) or fewer (red) patents than their GDP per capita and population predict', 'Eight largest positive and eight largest negative residuals from the baseline OLS regression, 141 countries', SRC, 'var(--rose)')}
<div class="keep">{tcap(7, 'Largest positive and negative regression residuals, cross-sectional dataset')}
{tbl('c5', ['Over-performers', 'Residual', 'Under-performers', 'Residual'], [
    ['Barbados', '+4.01', 'Kuwait', '−5.16'], ['Korea, Rep.', '+3.76', 'Tanzania', '−3.30'], ['Liberia', '+3.53', 'Angola', '−3.16'],
    ['Japan', '+3.16', 'United Arab Emirates', '−3.13'], ['China', '+3.00', 'Bahrain', '−3.00']], ['', 'num', '', 'num'])}</div>
<p style="margin-top:8pt">Korea, Japan, and China are the clearest over-performers — consistent with well-documented, deliberately built national innovation systems (R&amp;D tax incentives, university-industry linkages, and patent-friendly IP institutions). Several small oil-exporting economies (Kuwait, the UAE, Bahrain) sit among the under-performers: their high GDP per capita reflects resource wealth rather than a domestic innovation base, so the model "expects" more filing activity than these economies actually produce. A few very-low-count countries appear as apparent over-performers purely because one or two patents against a tiny population baseline produces a large residual in log space — these should be read as statistical noise rather than evidence of a strong innovation ecosystem.</p>
</section>

{chapter(5, 'c3', 'Discussion', 'Specification matters as much as model class.')}
<p>The central methodological finding is that specification matters as much as model class here. A pooled cross-sectional regression — whether OLS on log-transformed counts or a Negative Binomial model on the raw counts — finds GDP per capita, population, and energy use per capita all significantly associated with patenting activity, in line with a large existing literature linking innovation output to economic scale and development level. But once country and year fixed effects absorb persistent, unobserved country characteristics, GDP per capita’s association with patenting essentially disappears. The honest reading is that the well-known cross-country income-patents correlation is largely a between-country pattern — something about which countries are rich, not what happens when a given country gets richer — and that a naive policy claim of the form "raising GDP per capita will increase patenting" is not well supported by this analysis. Population and energy use per capita are more robust to this test, though the population estimate in particular should be read cautiously given how little population varies within a country over two decades.</p>
<div class="pull">Which parts of an association are between-country composition, and which are within-country dynamics? The two imply different policy levers.</div>
<p>This distinction is itself the paper’s main contribution beyond reproducing a known correlation: for an organization producing cross-country IP statistics, being able to say which parts of an association are between-country composition and which are genuinely within-country dynamics is more useful than a single pooled correlation, because the two imply different policy levers. The over/under-performer ranking in Section 4.6 operationalizes the intuitive but often qualitative claim that "country X punches above its weight in innovation" into a specific, reproducible number — understood, per the discussion above, as a between-country statement.</p>
<p>The comparison across model classes (OLS, panel fixed effects, Negative Binomial, Gradient Boosting, Random Forest) also has a methodological lesson beyond this specific dataset: it is worth explicitly testing whether a flexible or differently-specified model changes the substantive conclusion before defaulting to a single specification. Here, the ML models do not improve accuracy much and do not overturn the qualitative pattern, but the panel fixed-effects model does change a key coefficient’s sign of significance — which is exactly the kind of result a single cross-sectional regression would have missed entirely.</p>
</section>

{chapter(6, 'c6', 'Limitations and future work', 'What the estimates can and cannot support, and the natural next extensions.')}
<ul class="lim">
<li><strong>Filings, not quality.</strong> Resident patent applications measure filing activity, not innovation quality, and are shaped by each country’s own patent office incentives and legal system — China’s rapid growth in filings, for instance, partly reflects domestic policy incentives to file rather than issued-patent quality or citation impact alone.</li>
<li><strong>Not a causal design.</strong> The panel fixed-effects model controls for confounding by persistent country characteristics and common annual shocks, but it is not a causal identification strategy in the sense of an instrumental variable or natural experiment; the near-zero within-country GDP coefficient rules out a particular naive causal story but does not itself establish that GDP genuinely has no effect on patenting.</li>
<li><strong>Omitted controls.</strong> We attempted to add R&amp;D expenditure (% of GDP), tertiary education enrollment, and institutional-quality indicators (e.g. the World Bank’s Worldwide Governance Indicators, or UNDP’s Human Development Index) as additional controls, since omitted institutional quality is a natural concern for the between-country estimates. The R&amp;D and governance series could not be reliably retrieved in full through this pipeline’s public-data tooling, and the UNDP Human Development Report’s composite time series is too large to retrieve completely through the same channel; both remain natural, concrete next additions rather than results reported here.</li>
<li><strong>Year alignment.</strong> Patent and economic-indicator reporting years are not perfectly aligned across all countries in the cross-sectional dataset (Section 2.2); the panel dataset, which requires an exact year match between sources, avoids this issue but at the cost of retaining somewhat fewer very small countries than the cross-section.</li>
<li><strong>Population elasticity.</strong> The population coefficient in the fixed-effects model, while statistically significant, is imprecisely estimated and may partly reflect a shared time trend rather than a clean population elasticity; a specification with country-specific time trends would be a natural robustness check.</li>
</ul>
</section>

{chapter(7, 'c8', 'Conclusion', 'Fundamentals explain much of patenting, but income’s role is mainly between countries.')}
<p>Across a 2,201-observation panel of 136 countries spanning 2000–2021, economic fundamentals explain a substantial share of patenting activity, but the story is more nuanced than a single cross-sectional regression suggests. Population and energy use per capita are robustly associated with patent filings both between and within countries; GDP per capita’s well-known cross-sectional association with patenting is, on this evidence, primarily a between-country pattern that does not survive controlling for persistent country characteristics. A Negative Binomial specification, consistent with the classic patents-econometrics literature, corroborates the pooled pattern on the untransformed count data, and neither Gradient Boosting nor Random Forest improves materially on the linear specification once cross-validation is done correctly (grouped by country). Korea, Japan, and China file substantially more than their fundamentals predict, a pattern consistent with sustained, deliberate innovation-policy investment. The full data pipeline, model code, and interactive dashboard accompanying this report are built to be extended — with R&amp;D expenditure, institutional-quality controls, and a proper instrumental-variable strategy for GDP — as a next phase of this analysis.</p>

<div class="marker">@@REF@@</div>
<h2 class="sec" style="margin-top:22pt">References</h2>
<ol class="refs">
<li>World Intellectual Property Organization (WIPO). <em>Patent Report: Statistics on Worldwide Patent Activity</em>. Distributed via World Bank indicator IP.PAT.RESD, World Development Indicators.</li>
<li>Cornell University, INSEAD, and WIPO. <em>The Global Innovation Index</em>. Annual, co-published report benchmarking national innovation performance.</li>
<li>Hausman, J., Hall, B. H., &amp; Griliches, Z. (1984). Econometric Models for Count Data with an Application to the Patents-R&amp;D Relationship. <em>Econometrica</em>, 52(4), 909–938.</li>
<li>Our World in Data. <em>CO2 and Greenhouse Gas Emissions</em> dataset (population and GDP series, ultimately sourced from the World Bank and the Maddison Project Database).</li>
<li>World Bank. <em>World Development Indicators</em>. https://data.worldbank.org</li>
<li>United Nations Development Programme (UNDP). <em>Human Development Report, Composite Indices Complete Time Series</em>. https://hdr.undp.org</li>
</ol>
</section>
"""


EXTRA = """<style>
.abs { font-size: 10pt !important; color: var(--ink) !important; line-height: 1.55; }
.toc-subs { font-size: 8.4pt; color: var(--faint); padding: 1pt 0 4pt 26pt; line-height: 1.4; }
.eqn { display: flex; align-items: center; margin: 8pt 0 10pt; break-inside: avoid; }
.eqn math { flex: 1; font-size: 11pt; color: var(--navy); font-family: 'SS4', serif; }
.eqn .eqno { font-family: 'SS3'; font-size: 9pt; color: var(--faint); width: 22pt; text-align: right; }
ul { padding-left: 15pt; margin: 0 0 8pt; } li { margin-bottom: 4pt; text-align: justify; }
ul.lim li { margin-bottom: 7pt; }
.stat b { font-size: 17pt; }
</style>"""


def page(b_):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{TITLE}</title>'
            f'<link rel="stylesheet" href="{CSS}">{EXTRA}</head><body>{b_}</body></html>')


COVER = """<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="__CSS__">
<style>
@page { size: A4; margin: 0; }
body { margin: 0; }
.cover { width: 210mm; height: 297mm; background: #0f2a44; position: relative; overflow: hidden; color: #fff; }
.band { position: absolute; left: -20mm; right: -20mm; height: 22mm; transform: rotate(-12deg); }
.b1 { top: 38mm; background: #3380b5; } .b2 { top: 60mm; background: #0e7c74; } .b3 { top: 82mm; background: #6b4e9b; }
.b4 { top: 104mm; background: #c9774a; } .b5 { top: 126mm; background: #b8860b; } .b6 { top: 148mm; background: #b04a5a; }
.dots { position: absolute; right: 16mm; top: 16mm; display: grid; grid-template-columns: repeat(12, 3.2mm); gap: 1.6mm; }
.dots i { width: 3.2mm; height: 3.2mm; border-radius: 50%; background: rgba(255,255,255,.18); }
.dots i.on { background: #f2c14e; }
.title { position: absolute; left: 20mm; right: 20mm; bottom: 58mm; }
.k { font-family: 'SS3'; font-size: 10pt; letter-spacing: .22em; text-transform: uppercase; color: #9fd3cc; font-weight: 600; }
h1 { font-family: 'SS4'; font-weight: 700; font-size: 40pt; line-height: 1.04; margin: 6mm 0 5mm; }
.st { font-family: 'SS4'; font-size: 14pt; line-height: 1.35; color: #d7e0ea; max-width: 160mm; }
.meta { position: absolute; left: 20mm; right: 20mm; bottom: 18mm; display: flex; justify-content: space-between; align-items: flex-end; font-family: 'SS3'; font-size: 10pt; color: #c6d2df; border-top: 0.6pt solid rgba(255,255,255,.3); padding-top: 5mm; }
.meta b { color: #fff; font-size: 13pt; font-weight: 600; display: block; }
.shade { position: absolute; left: 0; right: 0; bottom: 0; height: 150mm; background: linear-gradient(180deg, rgba(15,42,68,0), #0f2a44 38%); }
</style></head><body><div class="cover">
<div class="band b1"></div><div class="band b2"></div><div class="band b3"></div><div class="band b4"></div><div class="band b5"></div><div class="band b6"></div>
<div class="shade"></div>
<div class="dots">__DOTS__</div><div style="position:absolute;right:16mm;top:74mm;width:67mm;font-family:'SS3';font-size:7.5pt;color:rgba(255,255,255,.6);text-align:right">Each dot is one of the 141 countries analysed; gold = the five largest filers, which account for __SHARE__ of their 2,292,209 resident filings</div>
<div class="title"><div class="k">Working paper · September 2026</div>
<h1>What Drives Global<br>Patenting Activity?</h1>
<div class="st">A Panel and Cross-Sectional Econometric Analysis of Resident Patent Filings, Economic Development, and Industrial Intensity</div></div>
<div class="meta"><div><b>Ashu Arora</b>MA, Economics, Johns Hopkins University<br>School of Advanced International Studies, Washington, D.C.</div><div style="text-align:right">Data: WIPO / World Bank; Our World in Data<br>Not a WIPO publication</div></div>
<div style="position:absolute;left:20mm;bottom:8mm;font-family:'SS3';font-size:7.5pt;color:rgba(255,255,255,.55)">&copy; Ashu Arora</div>
</div></body></html>"""

FOOT = """<div style="width:100%;font-family:'Liberation Sans',Arial,sans-serif;font-size:7.5px;color:#7a8494;padding:0 18mm;display:flex;justify-content:space-between">
<span>What Drives Global Patenting Activity? · Working paper</span><span>&copy; Ashu Arora&nbsp;&nbsp;·&nbsp;&nbsp;<span class="pageNumber"></span></span></div>"""


def render(pw, html, pdf, footer):
    br = pw.chromium.launch(executable_path=CHROME)
    pg = br.new_page()
    pg.goto(html.as_uri())
    pg.wait_for_timeout(600)
    opts = dict(path=str(pdf), format="A4", print_background=True, prefer_css_page_size=True)
    if footer:
        opts.update(display_header_footer=True, header_template="<span></span>", footer_template=FOOT,
                    margin={"top": "19mm", "bottom": "20mm", "left": "18mm", "right": "18mm"})
    pg.pdf(**opts)
    br.close()


def main():
    dots = "".join('<i class="on"></i>' if i < 5 else "<i></i>" for i in range(141))
    (BUILD / "cover.html").write_text(COVER.replace("__DOTS__", dots).replace("__CSS__", CSS)
                                      .replace("__SHARE__", f"{TOP5_SHARE:.0%}"))
    with sync_playwright() as pw:
        render(pw, BUILD / "cover.html", BUILD / "cover.pdf", False)
        (BUILD / "body.html").write_text(page(body({})))
        render(pw, BUILD / "body.html", BUILD / "body.pdf", True)
        toc = {}
        for i, pg in enumerate(PdfReader(str(BUILD / "body.pdf")).pages, start=1):
            for m in re.findall(r"@@(CH\d|KM|REF)@@", pg.extract_text() or ""):
                toc.setdefault(m, i)
        (BUILD / "body.html").write_text(page(body(toc)))
        render(pw, BUILD / "body.html", BUILD / "body.pdf", True)
    w = PdfWriter()
    for f in ["cover.pdf", "body.pdf"]:
        for pg in PdfReader(str(BUILD / f)).pages:
            w.add_page(pg)
    w.add_metadata({"/Title": TITLE, "/Author": "Ashu Arora"})
    out = OUT_PDF
    with open(out, "wb") as fh:
        w.write(fh)
    print("toc", toc, "pages", len(PdfReader(str(out)).pages), "top5 share", round(TOP5_SHARE, 4))


if __name__ == "__main__":
    main()
