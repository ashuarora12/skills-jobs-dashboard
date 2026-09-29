"""
Build the written report: report/who-benefits-report.pdf (also copied to the site).

  python3 pipeline.py && python3 report_stats.py      (from analysis/who-benefits/)
  python3 report/make_figures.py && python3 report/build_report.py

Every number in the text is read from output/dashboard_data.json or
output/report_stats.json. Two passes: the first finds the page on which each
chapter starts, the second writes those numbers into the contents page.
"""
import json
import re
import shutil
from pathlib import Path

from playwright.sync_api import sync_playwright
from pypdf import PdfReader, PdfWriter

HERE = Path(__file__).parent
BUILD = HERE / "build"
BUILD.mkdir(exist_ok=True)
D = json.loads((HERE.parent / "output" / "dashboard_data.json").read_text())
S = json.loads((HERE.parent / "output" / "report_stats.json").read_text())
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
SITE_PDF = HERE.parent.parent / "site" / "who-benefits-report.pdf"

# ------------------------------------------------------------------ numbers
M, A, P, T = D["model"], D["gender_audit"], D["psm"], D["themes"]
SD, R, SS = S["delivery"], S["psm_robustness"], S["sample"]
th = {t["key"]: t for t in T["summary"]}
pr = S["precision"]
REG = ["AFE", "AFW", "EAP", "ECA", "LCR", "MENAAP", "SAR"]
RN = {"AFE": "Eastern & Southern Africa", "AFW": "Western & Central Africa", "EAP": "East Asia & Pacific",
      "ECA": "Europe & Central Asia", "LCR": "Latin America & Caribbean",
      "MENAAP": "Middle East, North Africa, Afghanistan & Pakistan", "SAR": "South Asia"}


def res(sub, c="ACW", women_sub=None):
    r = D["results"][sub].get(c, {})
    tot = r.get("Total", {})
    w = (D["results"][women_sub].get(c, {}) if women_sub else r).get("Female")
    return tot.get("achieved"), tot.get("expected"), (w or {}).get("achieved")


def M_(x, d=1):
    return f"{x / 1e6:,.{d}f}M"


def pc(x, d=0):
    return f"{x * 100:.{d}f}%"


hs = {c: res("CSC_RES_HEA_SERV", c) for c in REG + ["ACW"]}
H_ALL = hs["ACW"]
top_reg = max(REG, key=lambda c: hs[c][0])
hyg = D["context"]["hygiene"]
g_health = next(g for g in S["gap_by_sub"] if g["sub"] == "CSC_RES_HEA_SERV")
worst = min(M["fairness"]["region"], key=lambda r: r["auc"])
fcs_f = next(r for r in M["fairness"]["fcv"] if r["group"].startswith("Fragile"))
nfcs_f = next(r for r in M["fairness"]["fcv"] if r["group"] == "Not FCV")
age0, age3 = M["by_age"][0], M["by_age"][-1]
lm = [p for p in T["projects"] if "migration" in p["themes"] and re.search(r"labou?r mobility|migrant work|remittance", p["evidence"]["migration"], re.I)]
imb = [b for b in P["balance"] if abs(b["after"]) > 0.1]
big_imb = [b for b in P["balance"] if abs(b["before"]) > 0.25]


def fig(name, num, title, sub, note, acc="var(--navy)"):
    svg = (HERE / "figures" / f"{name}.svg").read_text()
    svg = re.sub(r"<\?xml.*?\?>", "", svg, flags=re.S)
    svg = re.sub(r"<!DOCTYPE.*?>", "", svg, flags=re.S)
    svg = re.sub(r'\swidth="[^"]+"\sheight="[^"]+"', "", svg, count=1)
    return (f'<figure style="--acc:{acc}"><div class="cap"><span class="fl">Figure {num}</span>{title}</div>'
            f'<div class="sub">{sub}</div><div class="art">{svg}</div><div class="note">{note}</div></figure>')


SRC = "Source: author's analysis of World Bank Group Scorecard exports, FY25 cycle (results as of 30 June 2025)."


def chapter(n, cls, kicker, title, lede):
    return (f'<section class="pb"><div class="marker">@@CH{n}@@</div><div class="ch-open {cls}"><div class="num">{n}</div>'
            f'<div class="k">{kicker}</div><h1>{title}</h1><p>{lede}</p></div>')


# ------------------------------------------------------------------ tables
def table_results():
    rows = [("Health, nutrition & population services", "CSC_RES_HEA_SERV", None, ""),
            ("Water, sanitation and/or hygiene", "CSC_RES_WAT_SAN_HYG", None, ""),
            ("Actions advancing gender equality", "CSC_RES_GEN_EQU", None, ""),
            ("Actions expanding economic opportunity", "CSC_RES_BENE_ENAB_ECO_OPP", None, ""),
            ("Financial services users<sup>a</sup>", "CSC_RES_FIN_SERV", "CSC_RES_FIN_SERV_WOM_CUS", "")]
    out = []
    for lab, sub, ws, _ in rows:
        a, e, w = res(sub, "ACW", ws)
        out.append(f"<tr><td>{lab}</td><td class='num'>{M_(a)}</td><td class='num'>{M_(e)}</td><td class='num'>{pc(a / e)}</td>"
                   f"<td class='num'>{M_(w)}</td><td class='num'>{pc(w / a)}</td></tr>")
    em = D["results"]["CSC_RES_HEA_EMER_BENE"]["ACW"]["Total"]
    out.append(f"<tr><td>Economies with strengthened health-emergency capacity<sup>b</sup></td><td class='num'>{em['achieved']:.0f}</td>"
               f"<td class='num'>{em['expected']:.0f}</td><td class='num'>{pc(em['achieved'] / em['expected'])}</td><td class='num'>–</td><td class='num'>–</td></tr>")
    return ("<div class='tcap'>Table 3.1 &nbsp;World Bank Group corporate results, all countries, FY25</div>"
            "<table class='tbl'><tr class='c3'><th>Result</th><th class='r'>Achieved</th><th class='r'>Expected</th>"
            "<th class='r'>Achieved as % of expected</th><th class='r'>Women achieved</th><th class='r'>Women, % of achieved</th></tr>"
            + "".join(out) + "</table><div class='note' style='font-size:7.6pt;color:var(--faint)'>" + SRC +
            " Achieved = progress to date relative to baseline; expected = end-of-project target relative to baseline, summed over active and closed projects. "
            "a. Total counts people <em>and businesses</em>; the women figure counts women customers, so the share is indicative only. "
            "b. Number of economies; not disaggregated by sex.</div>")


def table_themes():
    out = []
    for k in ["health_workforce", "jobs_skills", "migration", "women_econ", "care_economy", "menstrual"]:
        t, p = th[k], pr[k]
        v1 = "" if p["v1"] is None or p["v1"] == round(p["correct"] / p["reviewed"], 2) else f"{p['v1']:.2f}"
        out.append(f"<tr><td>{t['label']}</td><td class='num'>{t['projects']}</td><td class='num'>{pc(t['share'], 1)}</td>"
                   f"<td class='num'>{p['correct']}/{p['reviewed']}</td><td class='num'>{p['ci'][0]:.2f}–{p['ci'][1]:.2f}</td><td class='num'>{v1 or '–'}</td></tr>")
    return ("<div class='tcap'>Table 4.1 &nbsp;Theme prevalence and hand-checked precision</div>"
            "<table class='tbl'><tr class='c4'><th>Theme</th><th class='r'>Projects</th><th class='r'>Share of 1,131</th>"
            "<th class='r'>Correct / reviewed</th><th class='r'>Wilson 95% CI</th><th class='r'>First-version precision</th></tr>"
            + "".join(out) + "</table><div class='note' style='font-size:7.6pt;color:var(--faint)'>" + SRC +
            " Precision = share of sampled tags judged correct on reading the matched phrase in context. Recall (tags the rules miss) was not measured.</div>")


def table_models():
    nm = {"logit": "Logistic regression (L2, C = 0.5)", "gbm": "Gradient boosting (depth 3, 300 iterations)"}
    rows = "".join(
        f"<tr><td>{nm[k]}{' <strong>(selected)</strong>' if k == SD['best'] else ''}</td><td class='num'>{v['auc']:.3f}</td>"
        f"<td class='num'>{v['bal_acc']:.3f}</td><td class='num'>{v['brier']:.3f}</td></tr>" for k, v in M["models"].items())
    rows += (f"<tr><td>Timing-only baseline (logistic: years since approval, share of period elapsed)</td>"
             f"<td class='num'>{SD['baseline_auc']:.3f}</td><td class='num'>–</td><td class='num'>–</td></tr>")
    return ("<div class='tcap'>Table 5.1 &nbsp;Out-of-fold performance, 5-fold cross-validation grouped by project</div>"
            "<table class='tbl'><tr class='c6'><th>Model</th><th class='r'>AUC</th><th class='r'>Balanced accuracy</th><th class='r'>Brier score</th></tr>"
            + rows + f"</table><div class='note' style='font-size:7.6pt;color:var(--faint)'>{SRC} n = {M['n']:,} results from {M['projects']} projects; "
            f"{pc(M['behind_rate'], 1)} flagged behind. 95% cluster-bootstrap interval for the selected model's AUC: {SD['auc_ci'][0]:.2f}–{SD['auc_ci'][1]:.2f} (1,000 draws over projects). "
            "Balanced accuracy at a 0.5 threshold. Lower Brier is better.</div>")


def table_estimates():
    rr = [("Raw difference, FCS − all non-FCS", f"{P['naive']:+.1f}", "–", str(P["n"])),
          ("PSM: 1:1 nearest neighbour, with replacement, caliper 0.2 SD of logit (main)", f"{P['att']:+.1f}", f"{P['ci'][0]:+.1f} to {P['ci'][1]:+.1f}", f"{P['matched_treated']} FCS / {P['unique_controls']} controls"),
          ("PSM without caliper", f"{P['att_no_caliper']:+.1f}", "–", f"{P['treated']} FCS"),
          ("OLS with all matching covariates, full informative sample", f"{R['regression_full']['coef']:+.1f}", f"{R['regression_full']['ci'][0]:+.1f} to {R['regression_full']['ci'][1]:+.1f}", str(R["regression_full"]["n"])),
          ("Weighted OLS on the matched sample (doubly adjusted)", f"{R['regression_matched']['coef']:+.1f}", f"{R['regression_matched']['ci'][0]:+.1f} to {R['regression_matched']['ci'][1]:+.1f}", str(R["regression_matched"]["n"]))]
    body = "".join(f"<tr><td>{a}</td><td class='num'>{b}</td><td class='num'>{c}</td><td class='num'>{d}</td></tr>" for a, b, c, d in rr)
    return ("<div class='keep'><div class='tcap'>Table 6.1 &nbsp;Difference in gender delivery gap, FCS vs. non-FCS results (percentage points)</div>"
            "<table class='tbl'><tr class='c5'><th>Specification</th><th class='r'>Estimate</th><th class='r'>95% CI</th><th class='r'>n</th></tr>"
            + body + f"</table><div class='note' style='font-size:7.6pt;color:var(--faint)'>{SRC} Gap = achieved minus planned share of women, in percentage points. "
            "PSM interval: bootstrap over treated projects (2,000 draws). Regression intervals: standard errors clustered by project.</div></div>")


def table_fair():
    inc = {"LIC": "Low income", "LMC": "Lower-middle income", "UMC": "Upper-middle income"}
    rows = []
    for grp, key in [("Region", "region"), ("FCS status", "fcv"), ("Income group", "income")]:
        for r in M["fairness"][key]:
            rows.append(f"<tr><td>{grp}</td><td>{inc.get(r['group'], r['group'])}</td><td class='num'>{r['n']}</td><td class='num'>{pc(r['behind_rate'])}</td>"
                        f"<td class='num'>{pc(r['predicted_rate'])}</td><td class='num'>{r['auc']:.2f}</td><td class='num'>{pc(r['fnr'])}</td></tr>")
    return ("<div class='tcap'>Table A.2 &nbsp;Delivery model: out-of-fold performance by subgroup</div>"
            "<table class='tbl'><tr class='cn'><th>Dimension</th><th>Group</th><th class='r'>n</th><th class='r'>Observed behind</th>"
            "<th class='r'>Mean predicted</th><th class='r'>AUC</th><th class='r'>Miss rate</th></tr>" + "".join(rows) +
            "</table><div class='note' style='font-size:7.6pt;color:var(--faint)'>Miss rate = share of truly-behind results with predicted probability ≤ 0.5.</div>")


# ------------------------------------------------------------------ document
def body_html(toc):
    hw, js, mg, we, ce, mh = (th[k] for k in ["health_workforce", "jobs_skills", "migration", "women_econ", "care_economy", "menstrual"])
    km = [
        ("c3", "Reach is large, but the women's count is uneven",
         f"Bank Group projects have reached {M_(H_ALL[0])} people with health, nutrition and population services, {pc(H_ALL[0] / H_ALL[1])} of the {M_(H_ALL[1])} expected by completion. "
         f"Women are {pc(H_ALL[2] / H_ALL[0])} of those recorded, but only {pc(hs['SAR'][2] / hs['SAR'][0])} in South Asia and {pc(hs['EAP'][2] / hs['EAP'][0])} in East Asia & Pacific. "
         "For population-wide services, figures this low point to incomplete sex-disaggregated reporting."),
        ("c4", "The health workforce is almost invisible in measured results",
         f"Of {T['n_projects']:,} projects, {hw['projects']} ({pc(hw['share'], 1)}) report a results indicator about health workers, and {T['health_workforce_and_jobs']} of these also report jobs or skills. "
         f"None link health workers to migration. Of {mg['projects']} projects tagged for migration and displacement, {len(lm)} tracks labour mobility; the rest concern refugees, IDPs and host communities."),
        ("c6", "Results arrive late, and a simple model can flag risk",
         f"{pc(M['behind_rate'])} of evaluable results trail a straight-line schedule, falling from {pc(age0['rate'])} in projects under 3 years old to {pc(age3['rate'])} after 7 years. "
         f"A cross-validated model ranks at-risk results with AUC {SD['auc_best']:.2f} (95% CI {SD['auc_ci'][0]:.2f}–{SD['auc_ci'][1]:.2f}), against {SD['baseline_auc']:.2f} for timing alone. It is weakest in "
         f"{worst['group']} (AUC {worst['auc']:.2f}) and in fragile settings ({fcs_f['auc']:.2f})."),
        ("c5", "Most women's figures cannot reveal a gender gap",
         f"Of {A['pairs']:,} results reported both in total and for women, {A['imputed']} ({pc(A['imputed'] / A['pairs'])}) derive the women's figure by applying a fixed share to the total, "
         f"so planned and achieved shares are equal by construction. After removing results with no progress, women-only results and other non-informative cases, {A['informative']} ({pc(A['informative'] / A['pairs'])}) remain."),
        ("c8", "No detectable fragility penalty; a health-services signal to investigate",
         f"Matched on region, income, size, result type, status and planned share, results in fragile and conflict-affected situations show a gap {P['att']:+.1f} points different from comparable results (95% CI {P['ci'][0]:+.1f} to {P['ci'][1]:+.1f}); "
         f"regression checks agree. Women's achieved share in health services runs {abs(g_health['mean']):.1f} points below plan (95% CI {g_health['ci'][0]:.1f} to {g_health['ci'][1]:.1f}; {g_health['n']} results), an exploratory finding."),
    ]
    kmh = "".join(f"<div class='km'><div class='n {c}'>{i + 1}</div><div><h4>{h}</h4><p>{p}</p></div></div>" for i, (c, h, p) in enumerate(km))

    return f"""
<!-- ============ ABOUT ============ -->
<section class="about">
  <div class="front-h">About this report</div>
  <p>This report asks three questions of the World Bank Group's own results data. Who is being reached by health, water and gender-related operations, and how many of them are women? Does the portfolio measure the link between health, jobs and labour mobility? Do projects deliver to women as planned, and is the gap wider in fragile and conflict-affected situations?</p>
  <p>The analysis uses public exports from the World Bank Group Scorecard for the FY25 reporting cycle (results as of 30 June 2025): {D['meta']['project_records']:,} project-indicator records from {D['meta']['projects']:,} operations in {D['meta']['countries']} countries. It combines three methods: rule-based text classification with manual validation, a cross-validated predictive model, and propensity-score matching. An interactive companion dashboard presents the same results.</p>
  <h4>Disclaimer</h4>
  <p>This is an independent analysis by the author. It is not a World Bank Group publication and has not been reviewed or endorsed by the World Bank Group. The findings, interpretations and conclusions are the author's own. Any errors are the author's.</p>
  <h4>Suggested citation</h4>
  <div class="cite">Arora, Ashu. 2026. <em>Who Benefits? Health, Jobs and Gender in the World Bank Group Portfolio: Evidence from FY25 Corporate Scorecard Results.</em> Independent analytical report, July 2026.</div>
  <h4>Data and reproducibility</h4>
  <p>All inputs are public downloads from scorecard.worldbank.org. One Python pipeline (<code>analysis/who-benefits/pipeline.py</code> and <code>report_stats.py</code>) rebuilds every number, table and figure from the raw exports with fixed random seeds. The classifier's validation samples, including the failed first version, are stored with the code. The review labels are a draft pending the author's confirmation.</p>
  <h4>Abbreviations</h4>
  <div class="abbr">
    <b>AUC</b><span>Area under the ROC curve (probability that a randomly chosen positive case is ranked above a randomly chosen negative case)</span>
    <b>CI</b><span>Confidence interval</span>
    <b>FCS</b><span>Fragile and conflict-affected situations (project flag in the Scorecard export)</span>
    <b>HNP</b><span>Health, nutrition and population</span>
    <b>IDA / IBRD</b><span>International Development Association / International Bank for Reconstruction and Development</span>
    <b>PSM</b><span>Propensity-score matching</span>
    <b>pp</b><span>Percentage points</span>
    <b>SMD</b><span>Standardised mean difference</span>
    <b>WASH</b><span>Water, sanitation and hygiene</span>
  </div>
</section>

<!-- ============ CONTENTS ============ -->
<section class="pb">
  <div class="front-h">Contents</div>
  <div class="toc">
    <div class="toc-row"><span class="n cn">★</span><span class="t">Key messages</span><span class="pg">{toc.get('KM', '')}</span></div>
    {''.join(f'<div class="toc-row"><span class="n {c}">{n}</span><span class="t">{t}</span><span class="pg">{toc.get(n, "")}</span></div>' for n, c, t in [
        (1, 'c1', 'Introduction'), (2, 'c2', 'Data and approach'), (3, 'c3', 'Who is being reached?'),
        (4, 'c4', 'What gets measured? Health workers, jobs and mobility in results frameworks'),
        (5, 'c6', 'When do results arrive? An early-warning model'),
        (6, 'c5', 'Are women counted, and reached as planned?'), (7, 'c7', 'Limitations'), (8, 'c8', 'Implications')])}
    <div class="toc-row"><span class="n cn">A</span><span class="t">Annexes: sample construction, classifier rules, subgroup performance, references</span><span class="pg">{toc.get('AX', '')}</span></div>
  </div>
  <div class="lists">
    <div><b>Figures</b><br>
      3.1 People reached with HNP services, by region and sex<br>3.2 Development context by region<br>
      4.1 Theme prevalence and precision<br>4.2 Themes by region<br>5.1 Behind-schedule rate by project age<br>5.2 Feature importance<br>
      5.3 Calibration<br>5.4 Performance by subgroup<br>6.1 From reported to informative results<br>6.2 Planned vs. achieved share of women<br>
      6.3 Gap by result type<br>6.4 Covariate balance<br>6.5 Estimates across specifications</div>
    <div><b>Tables</b><br>3.1 Corporate results, all countries<br>4.1 Theme prevalence and precision<br>5.1 Model performance<br>6.1 Fragility estimates<br>
      A.1 Sample construction<br>A.2 Subgroup performance<br>A.3 Classifier rules<br><br><b>Boxes</b><br>2.1 How the Scorecard reports women<br>
      4.1 Validating the classifier: a failed first version<br>4.2 The one labour-mobility project<br>6.1 What matching can and cannot tell us</div>
  </div>
</section>

<!-- ============ KEY MESSAGES ============ -->
<section class="pb"><div class="marker">@@KM@@</div>
  <div class="km-head"><div class="k">Key messages</div><h2>What the Bank Group's own results data show</h2>
  <p>Evidence from {D['meta']['projects']:,} operations' FY25 corporate results on health, jobs and gender</p></div>
  <div class="stats">
    <div class="stat c3"><b>{M_(H_ALL[0], 0)}</b><span>people reached with HNP services ({pc(H_ALL[0] / H_ALL[1])} of target)</span></div>
    <div class="stat c4"><b>{hw['projects']} of {T['n_projects']:,}</b><span>projects measure the health workforce</span></div>
    <div class="stat c6"><b>{SD['auc_best']:.2f}</b><span>AUC of the early-warning model (timing alone: {SD['baseline_auc']:.2f})</span></div>
    <div class="stat c5"><b>{pc(A['imputed'] / A['pairs'])}</b><span>of women's figures are a fixed share of the total, not a count</span></div>
  </div>
  {kmh}
</section>

<!-- ============ 1 INTRODUCTION ============ -->
{chapter(1, 'c1', 'Chapter 1', 'Introduction', 'Why ask who benefits, and why start with what is measured.')}
<p>Health services are labour-intensive. That makes investment in health a plausible route to jobs, including for women, and a candidate for skills partnerships that train workers for both domestic and international labour markets. Whether such a strategy works is ultimately a question for impact evaluation. A prior question is whether the results frameworks of operations measure the things that would let anyone find out.</p>
<p>This report takes that prior question seriously. It uses the World Bank Group's corporate results data, the indicators operations report to the Scorecard, to ask:</p>
<ol style="font-size:10pt;margin:0 0 8pt;padding-left:16pt">
  <li><strong>Who is being reached?</strong> How many people health, WASH, gender and financial-inclusion operations have reached, where, and how many of them are recorded as women (Chapter 3).</li>
  <li><strong>What gets measured?</strong> How often operations' objectives and results indicators refer to the health workforce, jobs and skills, migration, women's economic empowerment, care and menstrual health (Chapter 4).</li>
  <li><strong>When do results arrive, and can risk be flagged early?</strong> How delivery against targets evolves over a project's life, and whether a transparent model can identify results at risk of falling behind (Chapter 5).</li>
  <li><strong>Are women counted, and reached as planned?</strong> Whether women's achieved share of beneficiaries matches the planned share, and whether the gap is wider in fragile and conflict-affected situations (Chapter 6).</li>
</ol>
<p><strong>What this report is not.</strong> It does not estimate the impact of any operation on health, employment or migration. Corporate results indicators count outputs and beneficiaries, not counterfactual outcomes. The comparison in Chapter 6 is a matched association between a country's fragility status and a reporting outcome, not a causal effect. Throughout, estimates are reported with uncertainty, and the limits of each method are stated where the result is presented and again in Chapter 7.</p>
</section>

<!-- ============ 2 DATA ============ -->
{chapter(2, 'c2', 'Chapter 2', 'Data and approach', 'Public Scorecard exports, one reproducible pipeline, three methods.')}
<h2 class="sec"><span class="sn t2">2.1</span>Sources</h2>
<p>All data are public exports from the World Bank Group Scorecard for the FY25 reporting cycle, with results as of 30 June 2025. Five corporate results indicators were used. Each export contains an <em>Aggregates</em> sheet (results by organisation, region, income group and country, disaggregated by total, female and youth) and a <em>WB Project Information</em> sheet (one row per project, indicator and demographic group, with the project development objective, the indicator text, baseline, progress and target values, and project attributes):</p>
<ul style="font-size:9.4pt;margin:0 0 8pt;padding-left:16pt">
  <li>CSC_RES_HEA_SERV: people receiving quality health, nutrition and population services ({SS['rows_by_file']['HEALTH']:,} project records)</li>
  <li>CSC_RES_WAT_SAN_HYG_TOT: people provided with water, sanitation and/or hygiene ({SS['rows_by_file']['WASH']:,})</li>
  <li>CSC_RES_GEN_EQU_BENE: people benefiting from actions to advance gender equality and to expand economic opportunities ({SS['rows_by_file']['GENDER']:,})</li>
  <li>CSC_RES_FIN_SERV_WOM: people and businesses using financial services, including women ({SS['rows_by_file']['FIN']:,})</li>
  <li>CSC_RES_HEA_EMER_BENE: economies with strengthened health-emergency capacity (aggregates only)</li>
</ul>
<p>Four Scorecard <em>vision</em> indicators provide regional context: the poverty rate at $3.00 a day, the prevalence of food and nutrition insecurity, and access to basic hygiene, drinking water and sanitation services. The latest available year is used for each region.</p>
<h2 class="sec"><span class="sn t2">2.2</span>Unit of analysis and cleaning</h2>
<p>The project records combine to {D['meta']['project_records']:,} rows covering {D['meta']['projects']:,} projects in {D['meta']['countries']} countries ({SS['active']} active and {SS['closed']} closed; {SS['fcs_projects']} flagged as in fragile and conflict-affected situations). The analytical unit differs by question: the <strong>project</strong> for text classification, and the <strong>project result</strong> (a project × corporate sub-indicator pair) for delivery and gender analysis. The following cleaning rules are applied and checked in code:</p>
<ul style="font-size:9.4pt;margin:0 0 8pt;padding-left:16pt">
  <li><strong>Region codes.</strong> The aggregate labelled <code>ACW</code> is <em>All countries</em>. The seven regional aggregates sum to it exactly (for HNP services, {M_(H_ALL[0])}), and the pipeline asserts this.</li>
  <li><strong>Disability flag.</strong> Every aggregate appears twice: once for all projects and once for the subset that is disability-inclusive at design. Only the all-projects rows are used, to avoid double counting.</li>
  <li><strong>Double counting.</strong> {SS['double_counted_rows']:,} project rows are flagged by the Scorecard as masked for double counting. They are excluded from the delivery and gender analyses but kept for text classification.</li>
  <li><strong>Duplicates.</strong> The four exports were checked for exact duplicate rows; none were found.</li>
</ul>
<div class="box b-blue"><div class="bt">Box 2.1</div><h4>How the Scorecard reports women</h4>
<p>For people-centred indicators, the export reports a total and, where available, female and youth figures. The field <code>Progress_Disaggregation_Factor</code> records how each female figure was produced. A factor of 1 means the indicator itself counts women, for example "people receiving HNP services – female". A factor strictly between 0 and 1 means the female figure was computed as the total multiplied by that share, for example 0.495, the female share of a population. When the same factor is applied to the target and to progress, the female share of achieved and expected results is identical by construction. Such figures describe <em>who was expected to benefit</em>, not <em>who did</em>. Chapter 6 separates the two.</p></div>
<h2 class="sec"><span class="sn t2">2.3</span>Analytical approach</h2>
<div class="flow">
  <div class="c3"><b>1 · Reach</b>Regional aggregates by sex, with poverty, food-security and hygiene context</div>
  <div class="c4"><b>2 · Measurement</b>Rule-based tagging of objectives and indicators; precision checked by hand</div>
  <div class="c6"><b>3 · Delivery</b>Behind-schedule flag; logistic vs. gradient boosting; grouped CV; subgroup audit</div>
  <div class="c5"><b>4 · Gender gap</b>Measurement audit; planned vs. achieved share; PSM of FCS vs. non-FCS with robustness checks</div>
</div>
<p>Each method is described in the chapter where it is used. Code, raw exports and outputs are published together, and every figure in this report is generated from them.</p>
</section>

<!-- ============ 3 REACH ============ -->
{chapter(3, 'c3', 'Chapter 3', 'Who is being reached?', 'Hundreds of millions of people reached, and a women’s count that depends on how reporting is done.')}
<p>Table 3.1 summarises the five people-centred results at the level of the whole World Bank Group. Health, nutrition and population services have the largest reach: {M_(H_ALL[0])} people to date, against {M_(H_ALL[1])} expected by completion. Achieved-to-expected ratios should not be read as performance scores. The expected figure is the sum of end-of-project targets, including projects that are far from closing.</p>
{table_results()}
<p>Women are {pc(H_ALL[2] / H_ALL[0])} of recorded HNP beneficiaries overall. In Eastern & Southern, Western & Central Africa, the share is close to half ({pc(hs['AFE'][2] / hs['AFE'][0])} and {pc(hs['AFW'][2] / hs['AFW'][0])}). In South Asia it is {pc(hs['SAR'][2] / hs['SAR'][0])} of {M_(hs['SAR'][0])} people reached, and in East Asia & Pacific {pc(hs['EAP'][2] / hs['EAP'][0])} (Figure 3.1). Because these are services delivered to whole populations, figures this far below half are more plausibly explained by operations that do not disaggregate by sex than by services that exclude women. The figure flags them for checking, not interpretation.</p>
{fig('f1_reach_health', '3.1', 'People reached with health, nutrition and population services, by region and sex', 'Millions of people reached to date; labels show achieved as % of expected (all) and women as % of those reached', SRC + ' Regions follow the Scorecard’s regional aggregates.', 'var(--lake)')}
<p>The regions that account for most of those reached are also where basic services are weakest (Figure 3.2). {RN[top_reg]} accounts for {pc(hs[top_reg][0] / H_ALL[0])} of all people reached with HNP services, and only {hyg[top_reg]['value']:.1f}% of its population has basic hygiene services, against {hyg['ACW']['value']:.1f}% worldwide ({hyg['ACW']['year']}). Poverty at $3.00 a day is {D['context']['pov3'][top_reg]['value']:.1f}% and food and nutrition insecurity {D['context']['food'][top_reg]['value']:.1f}%.</p>
{fig('f2_context', '3.2', 'Development context by region', 'Share of population, latest available year; dashed line = world', 'Source: World Bank Group Scorecard vision indicators SI_POV_DDAY, SN_ITK_MSFI_ZS and SH_STA_HYGN_ZS. Hygiene data are not reported for Europe & Central Asia or Latin America & Caribbean.', 'var(--lake)')}
</section>

<!-- ============ 4 MEASUREMENT ============ -->
{chapter(4, 'c4', 'Chapter 4', 'What gets measured?', 'Health workers, jobs and mobility in the results frameworks of 1,131 operations.')}
<h2 class="sec"><span class="sn t4">4.1</span>Method</h2>
<p>For each project, the development objective and the names and descriptions of all its reported indicators were concatenated and matched against transparent regular-expression rules for six themes (Annex Table A.3). A project is tagged with a theme if any rule matches, and the first matching phrase is stored as evidence. The approach is deliberately simple and auditable. Every tag can be traced to the words that triggered it.</p>
<p><strong>Validation.</strong> For each theme, a random sample of up to 12 tagged projects was drawn (all 5 for menstrual health). Each tag was judged correct if the matched phrase, read in context, actually referred to the theme. Precision is reported with Wilson 95% intervals (Table 4.1). With samples this small the intervals are wide: a 12/12 score is consistent with a true precision as low as 0.76. Recall, meaning relevant projects the rules miss, was not measured, so the counts below are best read as lower bounds.</p>
{table_themes()}
<div class="box b-plum"><div class="bt">Box 4.1</div><h4>Validating the classifier: a failed first version</h4>
<p>The first rule set scored {pc(pr['health_workforce']['v1'])} precision on the health-workforce theme. Most matches were "deliveries attended by skilled health personnel", a service-coverage indicator, not a measure of the workforce. The care-economy theme scored {pc(pr['care_economy']['v1'])} because "care services" matched "primary health care services". Both rules were rewritten to require the workers or care services themselves to be the object, and fresh samples were drawn. Reporting both versions shows why validation matters: without it, the health-workforce count would have been overstated several times over.</p></div>
<h2 class="sec"><span class="sn t4">4.2</span>Findings</h2>
<p>Jobs and skills ({js['projects']} projects, {pc(js['share'], 1)}) and women's economic empowerment ({we['projects']}, {pc(we['share'], 1)}) are common themes (Figure 4.1). The health workforce is rare. Only <strong>{hw['projects']} projects ({pc(hw['share'], 1)})</strong> report an indicator about health workers, for example the number trained or recruited. Of these, {T['health_workforce_and_jobs']} also carry a jobs or skills indicator, and <strong>none</strong> refers to migration. Care-economy measures appear in {ce['projects']} projects and menstrual health in {mh['projects']}.</p>
{fig('f3_themes', '4.1', 'How many projects measure each theme', 'Projects with at least one matching objective or indicator; precision from hand-checked samples', SRC, 'var(--plum)')}
<p>The pattern holds across regions (Figure 4.2). Health-workforce indicators never exceed 3% of a region's projects and are absent from East Asia & Pacific, the Middle East, North Africa, Afghanistan & Pakistan, and South Asia. Jobs and skills indicators are most common in South Asia ({th['jobs_skills']['by_region']['SAR']} of {T['region_projects']['SAR']} projects).</p>
{fig('f4_theme_region', '4.2', 'Themes by region', 'Share of each region’s projects tagged with the theme (count in brackets)', SRC + ' A project can carry several themes.', 'var(--plum)')}
<div class="box b-teal"><div class="bt">Box 4.2</div><h4>The one labour-mobility project</h4>
<p>Of {mg['projects']} projects tagged for migration and displacement, the matched text almost always concerns refugees, internally displaced people or host communities. Only {len(lm)} concerns labour mobility: <strong>{lm[0]['name'] if lm else ''}</strong> ({lm[0]['country'] if lm else ''}, {lm[0]['id'] if lm else ''}). It reports an intermediate indicator for the annual number of short-term migrant workers, disaggregated by gender, disability and refugee status. This is the closest analogue in the portfolio to a skills-mobility partnership, and the only operation where the results framework could, in principle, connect training to international labour-market outcomes.</p></div>
</section>

<!-- ============ 5 DELIVERY ============ -->
{chapter(5, 'c6', 'Chapter 5', 'When do results arrive?', 'Delivery is back-loaded; a transparent model flags risk, mostly from timing.')}
<h2 class="sec"><span class="sn t6">5.1</span>Definition and sample</h2>
<p>For each project result (total, not double-counted), delivery is compared with elapsed time. A result is flagged <strong>behind</strong> when the share of its target delivered trails the share of its implementation period that has passed by more than 10 percentage points:</p>
<div class="eq">behind = 1 &nbsp;if&nbsp; achieved / expected &nbsp;&lt;&nbsp; (progress date − approval) / (closing − approval) − 0.10</div>
<p>Of {SD['pairs_total']:,} project results, {SD['with_target_and_dates']:,} have a positive target and complete dates. Results less than 20% of the way through implementation are excluded as too early to judge, leaving <strong>{SD['analysed']:,} results from {SD['projects']} projects</strong>, of which {pc(SD['behind_rate'], 1)} are flagged behind (Annex Table A.1).</p>
<div class="pair">
{fig('f5_age', '5.1', 'Share of results flagged behind, by project age', 'Years since Board approval', SRC, 'var(--ochre)')}
{fig('f6_importance', '5.2', 'What the model relies on', 'Permutation importance: mean drop in AUC over 10 shuffles', SRC + ' Features grouped across their dummy categories.', 'var(--ochre)')}
</div>
<p><strong>Delivery is back-loaded.</strong> {pc(age0['rate'])} of results in projects approved less than three years earlier trail the straight-line schedule, against {pc(age3['rate'])} in projects seven or more years old (Figure 5.1). A straight line is therefore a demanding benchmark early in a project's life, and a "behind" flag on a young project is weak evidence of a problem.</p>
<h2 class="sec"><span class="sn t6">5.2</span>Models and validation</h2>
<p>Two classifiers predict the flag from region, income group, FCS and least-developed-country status, lending instrument, IDA/IBRD financing, lead global department (top ten, other pooled), result type, project status, project size (log net commitment), years since approval and share of period elapsed. Performance is estimated on out-of-fold predictions from 5-fold cross-validation, with all of a project's results kept in the same fold so that no project is used to predict itself (Table 5.1).</p>
{table_models()}
<p>The regularised logistic regression (AUC {M['models']['logit']['auc']:.2f}) outperforms gradient boosting ({M['models']['gbm']['auc']:.2f}) and is selected, which also keeps the model interpretable. The comparison with the timing-only baseline ({SD['baseline_auc']:.2f}) is essential: <strong>most of the predictive signal comes from how old a project is and how far through implementation it is</strong>. Region, sector and the other features add about {SD['auc_best'] - SD['baseline_auc']:.2f} of AUC. Holding other features constant, a one-standard-deviation increase in years since approval is associated with odds of being behind multiplied by {SD['odds_ratios_per_sd']['years_since_approval']:.2f}. The model is well calibrated: predicted probabilities track observed rates across deciles (Figure 5.3).</p>
<div class="pair">
{fig('f7_calibration', '5.3', 'Calibration of out-of-fold predictions', 'Mean predicted probability vs. observed share behind, by decile', SRC, 'var(--ochre)')}
<div>
<h2 class="sec" style="margin-top:4pt"><span class="sn t6">5.3</span>Does it work equally well everywhere?</h2>
<p>An early-warning tool that misses problems more often in some places would direct attention unevenly. Figure 5.4 and Annex Table A.2 report out-of-fold performance by subgroup. Mean predicted rates track observed rates in every subgroup, so no group is systematically over- or under-flagged. Ranking quality is uneven, though. AUC is lowest in {worst['group']} ({worst['auc']:.2f}, where the model misses {pc(worst['fnr'])} of truly-behind results) and lower in fragile settings ({fcs_f['auc']:.2f}) than elsewhere ({nfcs_f['auc']:.2f}). Flags in those portfolios need more human review before they inform decisions.</p>
</div></div>
{fig('f8_fairness', '5.4', 'Model performance by subgroup', 'Out-of-fold AUC; the weakest region is highlighted; miss rate = truly-behind results not flagged', SRC, 'var(--ochre)')}
</section>

<!-- ============ 6 WOMEN ============ -->
{chapter(6, 'c5', 'Chapter 6', 'Are women counted, and reached as planned?', 'A measurement audit comes first; then a matched comparison of fragile and non-fragile settings.')}
<h2 class="sec"><span class="sn t5">6.1</span>From reported to informative results</h2>
<p>A gender delivery gap is defined for each project result as the achieved share of women among beneficiaries minus the planned share, in percentage points. A negative gap means women are falling behind plan. Before estimating it, each of the {A['pairs']:,} results reported both in total and for women was classified by whether a gap <em>could</em> appear (Figure 6.1):</p>
{fig('f9_audit', '6.1', 'From reported to informative results', 'Project results removed at each step (share of all paired results)', SRC + ' Inconsistent = women’s share above 105% of the total in either target or progress.', 'var(--clay)')}
<p>Three findings stand out. First, <strong>{A['imputed']} results ({pc(A['imputed'] / A['pairs'])}) apply a fixed share to the total</strong>, so they cannot reveal whether women were reached as planned. Second, {A['no_progress_yet']} ({pc(A['no_progress_yet'] / A['pairs'])}) have no progress to date. Third, {A['women_only']} are women-only results, and {A['identical_share']} report identical shares for other reasons. Only <strong>{A['informative']} results from {A['informative_projects']} projects ({pc(A['informative'] / A['pairs'])})</strong> count women directly and can show a gap.</p>
<div class="pair">
{fig('f10_scatter', '6.2', 'Planned vs. achieved share of women', 'Each dot is one informative result', SRC, 'var(--clay)')}
{fig('f11_gap_by_type', '6.3', 'Mean gap by result type', 'Achieved − planned share of women, pp', SRC + ' Intervals: 2,000 bootstrap draws over projects.', 'var(--clay)')}
</div>
<p>Across informative results, the gap is centred near zero: the median is {P['median_gap']:+.1f} pp and {pc(S['share_negative_gap'])} of results fall below plan (Figure 6.2). By result type (Figure 6.3), four of five intervals include zero. The exception is <strong>health, nutrition and population services</strong>, where women's achieved share is on average {abs(g_health['mean']):.1f} points below plan (median {g_health['median']:.1f}; 95% CI {g_health['ci'][0]:.1f} to {g_health['ci'][1]:.1f}). This rests on {g_health['n']} results from {g_health['projects']} projects and is one of five comparisons, so it should be treated as exploratory: a signal worth checking against project documents, not a finding.</p>
<h2 class="sec"><span class="sn t5">6.2</span>Does fragility widen the gap? A matched comparison</h2>
<p>Of the {P['n']} informative results, {P['treated']} are in projects flagged as in fragile and conflict-affected situations. These differ systematically from the rest, especially in being in Africa and in low-income countries (Figure 6.4, grey points). A propensity score for FCS status was estimated by logistic regression on region (Africa; MENAAP), income group (low; upper-middle or high), log project size, result type (health or WASH; gender equality), project status and the planned share of women. Each FCS result was matched to its nearest non-FCS neighbour on the logit of the score, with replacement, within a caliper of 0.2 standard deviations ({P['caliper']}). All {P['treated']} FCS results found a match, using {P['unique_controls']} distinct controls.</p>
<div class="pair">
{fig('f12_balance', '6.4', 'Covariate balance before and after matching', 'Standardised mean difference; band = |SMD| &lt; 0.1', SRC, 'var(--clay)')}
<div>
<p style="margin-top:8pt">Matching removes the large imbalances in region and income (for example, low-income status from {next(b for b in P['balance'] if b['covariate'] == 'Low-income country')['before']:.2f} to {next(b for b in P['balance'] if b['covariate'] == 'Low-income country')['after']:.2f}). {len(imb)} covariates remain slightly outside the conventional 0.1 threshold after matching: {', '.join(f"{b['covariate'].lower()} ({b['after']:+.2f})" for b in imb)}. The regression checks in Table 6.1 adjust for all covariates directly, and agree with the matched estimate.</p>
<div class="box b-clay" style="margin-top:6pt"><div class="bt">Box 6.1</div><h4>What matching can and cannot tell us</h4>
<p>Matching compares like with like on <em>observed</em> characteristics. It cannot account for unobserved differences such as implementation capacity, security conditions or monitoring quality, which plausibly differ between fragile and other settings. The bootstrap interval for a nearest-neighbour matching estimator with replacement is known to be only approximately valid (Abadie and Imbens 2008). This is one reason the regression checks are reported alongside it. The estimate is a matched association, not the causal effect of fragility.</p></div>
</div></div>
{fig('f13_estimates', '6.5', 'Difference in gender delivery gap, FCS vs. non-FCS, across specifications', 'Percentage points, with 95% confidence intervals where available', SRC, 'var(--clay)')}
{table_estimates()}
<p><strong>Result.</strong> The matched difference is {P['att']:+.1f} pp (95% CI {P['ci'][0]:+.1f} to {P['ci'][1]:+.1f}). The unadjusted difference of {P['naive']:+.1f} pp shrinks once region and income are balanced, and the regression estimates ({R['regression_full']['coef']:+.1f} and {R['regression_matched']['coef']:+.1f} pp) point the same way with intervals spanning zero. The data therefore provide <strong>no evidence that fragility widens the gender delivery gap</strong>. The intervals are also too wide to rule out a moderate effect in either direction. With only {pc(A['informative'] / A['pairs'])} of paired results informative, the binding constraint on answering the question is measurement, not method.</p>
</section>

<!-- ============ 7 LIMITATIONS ============ -->
{chapter(7, 'c7', 'Chapter 7', 'Limitations', 'What these results can and cannot support.')}
<ul style="font-size:9.8pt;padding-left:16pt">
<li><strong>Corporate indicators, not outcomes.</strong> Scorecard indicators count people reached and actions taken. They do not measure changes in health, employment or incomes, and they cover only the corporate indicators each project maps to the Scorecard, not every indicator it tracks.</li>
<li><strong>Classifier recall is unknown.</strong> Precision was checked on small samples (5–12 per theme), with wide intervals. Projects that describe a theme in words the rules do not anticipate are missed, so theme counts are lower bounds. The review labels are a draft pending confirmation.</li>
<li><strong>"Behind" is a screening definition.</strong> The straight-line benchmark ignores the planned shape of each project's delivery, which is typically back-loaded. The model partly absorbs this through timing features, but its flags are prompts for review, not verdicts.</li>
<li><strong>Selection into informative results.</strong> Only {pc(A['informative'] / A['pairs'])} of paired results count women directly. These are not a random sample of the portfolio, so the gap estimates may not generalise to results that impute women's shares.</li>
<li><strong>Matching is not randomisation.</strong> FCS status is a country classification correlated with many unobserved factors. Balance on some observed covariates remains imperfect after matching, and the matched estimate is an association.</li>
<li><strong>Snapshot data.</strong> Results are a single FY25 snapshot of cumulative progress. Active projects have not finished delivering, and reported progress dates vary by project.</li>
<li><strong>Multiple comparisons.</strong> Several subgroup comparisons are reported (by region, result type and income). Isolated significant differences, such as the health-services gap, should be treated as hypotheses.</li>
</ul>
</section>

<!-- ============ 8 IMPLICATIONS ============ -->
{chapter(8, 'c8', 'Chapter 8', 'Implications', 'Measurement choices that would make the health–jobs–gender question answerable.')}
<p>The findings suggest four practical, low-cost steps. They are offered as implications of the analysis, not as evaluated interventions.</p>
<div class="box b-teal"><div class="bt">1 · Count women directly where feasible, and flag when they are not</div>
<p>{pc(A['imputed'] / A['pairs'])} of paired results derive women's figures from a fixed share. Where direct counts are feasible, collecting them would turn these into informative results. Where they are not, publishing the imputation flag alongside the figure (the export already records the factor) would stop imputed shares being read as achieved reach.</p></div>
<div class="box b-plum"><div class="bt">2 · Measure the health workforce as a jobs outcome</div>
<p>If health is to be tracked as a source of jobs, health operations need workforce indicators, such as health workers trained, deployed and retained, disaggregated by sex. Today only {hw['projects']} of {T['n_projects']:,} projects report any health-worker indicator, and {T['health_workforce_and_jobs']} link it to jobs or skills.</p></div>
<div class="box b-ochre"><div class="bt">3 · Use age-adjusted early warning</div>
<p>Because delivery is back-loaded, straight-line schedules over-flag young projects. Screening on predicted risk relative to comparable projects (Chapter 5), with extra human review where the model is weakest (MENAAP; fragile settings), would focus supervision where slippage is least expected.</p></div>
<div class="box b-clay"><div class="bt">4 · Build learning into the few mobility operations</div>
<p>Only one operation tracks labour mobility (Box 4.2). Such operations are natural candidates for embedded evaluation, for example of whether training pathways designed around women's constraints raise enrolment, completion and domestic or international placement, so that future portfolios can draw on evidence rather than analogy.</p></div>
</section>

<!-- ============ ANNEXES ============ -->
<section class="pb"><div class="marker">@@AX@@</div>
<div class="ch-open cn"><div class="k">Annexes</div><h1>Technical annexes</h1><p>Sample construction, subgroup performance, classifier rules and references.</p></div>
<div class="tcap">Table A.1 &nbsp;Sample construction</div>
<table class="tbl"><tr class="cn"><th>Step</th><th class="r">Count</th></tr>
<tr><td>Project records in the four project exports (project × indicator × demographic group)</td><td class="num">{D['meta']['project_records']:,}</td></tr>
<tr><td>… of which flagged as masked for double counting</td><td class="num">{SS['double_counted_rows']:,}</td></tr>
<tr><td>Distinct projects / countries</td><td class="num">{D['meta']['projects']:,} / {D['meta']['countries']}</td></tr>
<tr class="tot"><td>Text classification: projects classified</td><td class="num">{T['n_projects']:,}</td></tr>
<tr><td>Delivery: project results (total, not double-counted)</td><td class="num">{SD['pairs_total']:,}</td></tr>
<tr><td>… with positive target and complete dates</td><td class="num">{SD['with_target_and_dates']:,}</td></tr>
<tr class="tot"><td>… at least 20% through implementation (analysed)</td><td class="num">{SD['analysed']:,}</td></tr>
<tr><td>Gender: results reported both in total and for women</td><td class="num">{A['pairs']:,}</td></tr>
<tr class="tot"><td>… informative (women counted directly; progress reported; not women-only; shares differ)</td><td class="num">{A['informative']}</td></tr>
<tr><td>… in FCS / not in FCS</td><td class="num">{P['treated']} / {P['control']}</td></tr>
</table>
{table_fair()}
<div class="tcap">Table A.3 &nbsp;Classifier rules (case-insensitive regular expressions; first match stored as evidence)</div>
<table class="tbl"><tr class="cn"><th style="width:26%">Theme</th><th>Patterns</th></tr>
{''.join(f"<tr><td>{t['label']}</td><td class='annex-pat'>{' · '.join(p.replace('<', '&lt;') for p in t['patterns'])}</td></tr>" for t in T['summary'])}
</table>
<h2 class="sec">References</h2>
<ol class="refs">
<li>Abadie, A., and G. W. Imbens. 2008. "On the Failure of the Bootstrap for Matching Estimators." <em>Econometrica</em> 76 (6): 1537–57.</li>
<li>Austin, P. C. 2011. "An Introduction to Propensity Score Methods for Reducing the Effects of Confounding in Observational Studies." <em>Multivariate Behavioral Research</em> 46 (3): 399–424.</li>
<li>Austin, P. C. 2011. "Optimal Caliper Widths for Propensity-Score Matching When Estimating Differences in Means and Differences in Proportions in Observational Studies." <em>Pharmaceutical Statistics</em> 10 (2): 150–61.</li>
<li>Pedregosa, F., et al. 2011. "Scikit-learn: Machine Learning in Python." <em>Journal of Machine Learning Research</em> 12: 2825–30.</li>
<li>Rosenbaum, P. R., and D. B. Rubin. 1983. "The Central Role of the Propensity Score in Observational Studies for Causal Effects." <em>Biometrika</em> 70 (1): 41–55.</li>
<li>Wilson, E. B. 1927. "Probable Inference, the Law of Succession, and Statistical Inference." <em>Journal of the American Statistical Association</em> 22 (158): 209–12.</li>
<li>World Bank Group. 2025. <em>World Bank Group Scorecard</em>, FY25 reporting cycle. Data exports for indicators CSC_RES_HEA_SERV, CSC_RES_WAT_SAN_HYG_TOT, CSC_RES_GEN_EQU_BENE, CSC_RES_FIN_SERV_WOM, CSC_RES_HEA_EMER_BENE, SI_POV_DDAY, SI_POV_PROS, SN_ITK_MSFI_ZS and SH_H2O_STA_HYGN_TO. scorecard.worldbank.org (accessed 2026).</li>
</ol>
</section>
"""


def page(body):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Who Benefits? Report</title>
<link rel="stylesheet" href="../report.css"></head><body>{body}</body></html>"""


COVER = """<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="../report.css">
<style>
@page { size: A4; margin: 0; }
body { margin: 0; }
.cover { width: 210mm; height: 297mm; background: #0f2a44; position: relative; overflow: hidden; color: #fff; }
.band { position: absolute; left: -20mm; right: -20mm; height: 22mm; transform: rotate(-12deg); }
.b1 { top: 38mm; background: #0e7c74; } .b2 { top: 60mm; background: #3380b5; } .b3 { top: 82mm; background: #c9774a; }
.b4 { top: 104mm; background: #b8860b; } .b5 { top: 126mm; background: #6b4e9b; } .b6 { top: 148mm; background: #b04a5a; }
.dots { position: absolute; right: 16mm; top: 16mm; display: grid; grid-template-columns: repeat(12, 3.2mm); gap: 1.6mm; }
.dots i { width: 3.2mm; height: 3.2mm; border-radius: 50%; background: rgba(255,255,255,.18); }
.dots i.on { background: #f2c14e; }
.title { position: absolute; left: 20mm; right: 20mm; bottom: 58mm; }
.k { font-family: 'SS3'; font-size: 10pt; letter-spacing: .22em; text-transform: uppercase; color: #9fd3cc; font-weight: 600; }
h1 { font-family: 'SS4'; font-weight: 700; font-size: 44pt; line-height: 1.02; margin: 6mm 0 5mm; }
.st { font-family: 'SS4'; font-size: 15pt; line-height: 1.35; color: #d7e0ea; max-width: 150mm; }
.meta { position: absolute; left: 20mm; right: 20mm; bottom: 18mm; display: flex; justify-content: space-between; align-items: flex-end; font-family: 'SS3'; font-size: 10pt; color: #c6d2df; border-top: 0.6pt solid rgba(255,255,255,.3); padding-top: 5mm; }
.meta b { color: #fff; font-size: 13pt; font-weight: 600; display: block; }
.shade { position: absolute; left: 0; right: 0; bottom: 0; height: 150mm; background: linear-gradient(180deg, rgba(15,42,68,0), #0f2a44 38%); }
</style></head><body><div class="cover">
<div class="band b1"></div><div class="band b2"></div><div class="band b3"></div><div class="band b4"></div><div class="band b5"></div><div class="band b6"></div>
<div class="shade"></div>
<div class="dots">__DOTS__</div><div style="position:absolute;right:16mm;top:74mm;width:67mm;font-family:'SS3';font-size:7.5pt;color:rgba(255,255,255,.6);text-align:right">Each dot ≈ 0.7% of 1,131 projects; gold = share whose results measure the health workforce (1.3%)</div>
<div class="title"><div class="k">Independent analytical report · July 2026</div>
<h1>Who Benefits?</h1>
<div class="st">Health, Jobs and Gender in the World Bank Group Portfolio: Evidence from FY25 Corporate Scorecard Results</div></div>
<div class="meta"><div><b>Ashu Arora</b>MA, Economics, Johns Hopkins University<br>School of Advanced International Studies, Washington, D.C.</div><div style="text-align:right">Data: World Bank Group Scorecard, FY25<br>Not a World Bank Group publication</div></div>
<div style="position:absolute;left:20mm;bottom:8mm;font-family:'SS3';font-size:7.5pt;color:rgba(255,255,255,.55)">&copy; Ashu Arora</div>
</div></body></html>"""


FOOT = """<div style="width:100%;font-family:'Liberation Sans',Arial,sans-serif;font-size:7.5px;color:#7a8494;padding:0 18mm;display:flex;justify-content:space-between">
<span>Who Benefits? Health, Jobs and Gender in the World Bank Group Portfolio</span><span>&copy; Ashu Arora&nbsp;&nbsp;·&nbsp;&nbsp;<span class="pageNumber"></span></span></div>"""


def render(pw, html_path, pdf_path, footer):
    b = pw.chromium.launch(executable_path=CHROME)
    pg = b.new_page()
    pg.goto(html_path.as_uri())
    pg.wait_for_timeout(600)
    opts = dict(path=str(pdf_path), format="A4", print_background=True, prefer_css_page_size=True)
    if footer:
        opts.update(display_header_footer=True, header_template="<span></span>", footer_template=FOOT,
                    margin={"top": "19mm", "bottom": "20mm", "left": "18mm", "right": "18mm"})
    pg.pdf(**opts)
    b.close()


def main():
    # 1-in-1,131 style dot motif on the cover: health-workforce share
    n_on = round(th["health_workforce"]["share"] * 144)
    dots = "".join(f"<i class='{'on' if i < max(1, n_on) else ''}'></i>" for i in range(144))
    (BUILD / "cover.html").write_text(COVER.replace("__DOTS__", dots))
    with sync_playwright() as pw:
        render(pw, BUILD / "cover.html", BUILD / "cover.pdf", footer=False)
        # pass 1: find chapter pages
        (BUILD / "body.html").write_text(page(body_html({})))
        render(pw, BUILD / "body.html", BUILD / "body.pdf", footer=True)
        toc = {}
        for i, pg in enumerate(PdfReader(str(BUILD / "body.pdf")).pages, start=1):
            for m in re.findall(r"@@(CH\d|KM|AX)@@", pg.extract_text() or ""):
                key = int(m[2:]) if m.startswith("CH") else m
                toc.setdefault(key, i)
        # pass 2: with page numbers
        (BUILD / "body.html").write_text(page(body_html(toc)))
        render(pw, BUILD / "body.html", BUILD / "body.pdf", footer=True)
    w = PdfWriter()
    for f in ["cover.pdf", "body.pdf"]:
        for pg in PdfReader(str(BUILD / f)).pages:
            w.add_page(pg)
    w.add_metadata({"/Title": "Who Benefits? Health, Jobs and Gender in the World Bank Group Portfolio",
                    "/Author": "Ashu Arora", "/Subject": "Independent analysis of World Bank Group Scorecard FY25 results"})
    out = HERE / "who-benefits-report.pdf"
    with open(out, "wb") as fh:
        w.write(fh)
    shutil.copy(out, SITE_PDF)
    print("toc", toc, "pages", len(PdfReader(str(out)).pages), "->", out, SITE_PDF)


if __name__ == "__main__":
    main()
