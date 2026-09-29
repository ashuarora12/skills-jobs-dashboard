"""
Build the Data Finder guide: guide/data-finder-guide.pdf (copied to the site).

  python3 analysis.py && python3 make_figures.py && python3 build_guide.py

Numbers come from ../datasets.json (catalogue) and output/guide_stats.json
(Scorecard country analysis). India headline figures in Brief 3 are quoted from
official releases and labelled as such; they are not recomputed here.
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
CAT = json.loads((HERE.parent / "datasets.json").read_text())
S = json.loads((HERE / "output" / "guide_stats.json").read_text())
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
SITE_PDF = HERE.parent.parent / "site" / "data-finder-guide.pdf"
DS = CAT["datasets"]
BY = {d["id"]: d for d in DS}
N, NCHK = len(DS), sum(d["status"] == "checked" for d in DS)
short = lambda d: re.sub(r" \(.*\)$", "", d["name"])


def finder(theme=None, level=None, design=None):
    """Same scoring as the web page's guided search."""
    LV = CAT["levels"]
    out = []
    for d in DS:
        s, why, warn = 0.0, [], []
        if theme:
            if theme not in d["themes"]:
                continue
            s += 4 if d["themes"][0] == theme else 3
            why.append(CAT["themes"][theme] + (" (main focus)" if d["themes"][0] == theme else ""))
        if level:
            if LV[d["level"]] < LV[level]:
                continue
            s += 2 + (LV[d["level"]] - LV[level]) * .1
            why.append("to " + CAT["level_labels"][d["level"]].lower())
        if design:
            if design not in d["designs"]:
                continue
            s += 3
            why.append("fits " + CAT["designs"][design]["label"].lower())
        if d["access"] == "open":
            s += .5; why.append("open access")
        if d["status"] != "checked":
            s -= .3; warn.append("to verify")
        out.append((s, d, why, warn))
    return sorted(out, key=lambda x: -x[0])


def fig(name, num, title, sub, note, acc="var(--teal)"):
    svg = (HERE / "figures" / f"{name}.svg").read_text()
    svg = re.sub(r"<\?xml.*?\?>", "", svg, flags=re.S)
    svg = re.sub(r"<!DOCTYPE.*?>", "", svg, flags=re.S)
    svg = re.sub(r'\swidth="[^"]+"\sheight="[^"]+"', "", svg, count=1)
    return (f'<figure style="--acc:{acc}"><div class="cap"><span class="fl">Figure {num}</span>{title}</div>'
            f'<div class="sub">{sub}</div><div class="art">{svg}</div><div class="note">{note}</div></figure>')


def chapter(n, cls, kicker, title, lede, marker):
    return (f'<section class="pb"><div class="marker">@@{marker}@@</div><div class="ch-open {cls}"><div class="num">{n}</div>'
            f'<div class="k">{kicker}</div><h1>{title}</h1><p>{lede}</p></div>')


SC = "Source: author's analysis of World Bank Group Scorecard vision indicators (FY25 cycle); latest country-year from 2015 onward."
OFF = '<span class="official">Official release · quoted</span>'


def body(toc):
    ex = finder("mch_gender", "district", "did_rcs")
    ex_html = "".join(
        f"<div class='rk'><span class='n'>{i + 1}</span><div><b>{short(d)}</b> "
        f"{'<span class=st-ok>Checked</span>' if d['status'] == 'checked' else '<span class=st-tv>To verify</span>'}<br>"
        f"<small>{' · '.join(why)}{' · ' + ', '.join(warn) if warn else ''}</small><br><small>Watch out: {d['cautions'][0]}</small></div></div>"
        for i, (s, d, why, warn) in enumerate(ex[:4]))
    design_rows = "".join(
        f"<tr><td><b>{v['label']}</b></td><td>{v['note']}</td><td>{', '.join(short(d) for d in DS if k in d['designs'])}</td></tr>"
        for k, v in CAT["designs"].items())
    catalogue = "".join(
        f"<tr><td>{short(d)}</td><td>{d['scope']}</td><td>{d['structure']}</td><td>{CAT['level_labels'][d['level']]}</td>"
        f"<td>{d['access']}</td><td>{'<span class=st-ok>Checked</span>' if d['status'] == 'checked' else '<span class=st-tv>To verify</span>'}</td></tr>"
        for d in DS)
    traps = [
        ("Infant mortality: NFHS vs SRS", BY["nfhs"]["cautions"][0]),
        ("NSS health rounds", BY["nss_health"]["cautions"][0] + " " + BY["nss_health"]["cautions"][1]),
        ("Consumption surveys", BY["hces"]["cautions"][0]),
        ("PLFS", BY["plfs"]["cautions"][0] + " " + BY["plfs"]["cautions"][2]),
        ("Migration definitions", BY["nss64"]["cautions"][0]),
        ("Administrative data (HMIS)", BY["hmis"]["cautions"][0] + " " + BY["hmis"]["cautions"][1]),
        ("DHS cluster coordinates", BY["dhs"]["cautions"][0]),
        ("Global Burden of Disease", BY["gbd"]["cautions"][0]),
        ("Health accounts", BY["nha"]["cautions"][0] + " " + BY["ghed"]["cautions"][0]),
        ("District boundaries", "District boundaries change between survey rounds and censuses; harmonise to a fixed boundary set (for example 2011) before building district panels."),
    ]
    trap_html = "".join(f"<li><strong>{a}.</strong> {b}</li>" for a, b in traps)
    a, I, H = S["assoc"], S["india"], S["hotspots"]
    return f"""
<section class="about">
  <div class="front-h">About this guide</div>
  <p>This guide accompanies the <strong>Health Economics Data Finder</strong> (ashuarora.com/data-buff). The Finder is a curated catalogue of {N} evaluation-ready datasets for health economics in India, with global comparators. Part A explains how to use the Finder, how to match data to research designs, and the comparability traps that most often undermine studies. Part B applies the same data to four short issue briefs.</p>
  <h4>Sourcing</h4>
  <p>{NCHK} of the {N} catalogue entries were checked against official or authoritative sources on {CAT['checked_on']}. The rest are marked <span class="st-tv">To verify</span>, with the open point stated. The country analysis in Part B is computed from World Bank Group Scorecard vision indicators by a reproducible script. India headline figures in Brief 3 are quoted from official releases and marked {OFF}; they are not recomputed here.</p>
  <h4>Disclaimer</h4>
  <p>This is an independent guide by the author. It is not endorsed by any of the data custodians it describes, and it does not host or redistribute their data. Findings and interpretations are the author's own.</p>
  <h4>Suggested citation</h4>
  <div class="cite">Arora, Ashu. 2026. <em>Health Economics Data Finder: User Guide and Issue Briefs.</em> September 2026. ashuarora.com/data-buff.</div>
  <h4>Contents</h4>
  <div class="toc">
    {''.join(f'<div class="toc-row"><span class="n {c}">{n}</span><span class="t">{t}</span><span class="pg">{toc.get(m, "")}</span></div>' for n, c, t, m in [
        ('A', 'c1', 'Using the Data Finder: worked example, design guide, comparability traps', 'A'),
        ('B1', 'c5', 'Where basic health risks cluster', 'B1'), ('B2', 'c2', 'India in the global picture', 'B2'),
        ('B3', 'c4', 'Financial protection and maternal health in India', 'B3'), ('B4', 'c6', 'Health workforce and migration', 'B4'),
        ('C', 'cn', 'Limitations, catalogue and references', 'C')])}
  </div>
</section>

{chapter('A', 'c1', 'Part A', 'Using the Data Finder', 'From a research question to a shortlist of datasets, with the traps flagged up front.', 'A')}
<h2 class="sec"><span class="sn t1">A.1</span>What the Finder does</h2>
<p>Each of the {N} datasets is described by the properties that decide whether a study is feasible: its <strong>structure</strong> (panel, repeated cross-section, administrative records, aggregates or modelled estimates), the <strong>finest geography</strong> it supports, its rounds and latest release, whether results are broken down by <strong>sex</strong>, the <strong>research designs</strong> it can serve, its <strong>access</strong> conditions, and its <strong>comparability cautions</strong>. The page has five tools:</p>
<table class="tbl"><tr class="c1"><th style="width:24%">Tool</th><th>Use it to</th></tr>
<tr><td><b>Guided search</b></td><td>Rank datasets for a theme, a minimum geography and a design, with the reasons for each match and the main caution.</td></tr>
<tr><td><b>Catalogue</b></td><td>Search by keyword and filter by scope, theme, access and verification status; open any entry for full details and the official link.</td></tr>
<tr><td><b>Compare</b></td><td>Sort all datasets side by side by structure, finest level, latest release, sex breakdown and access.</td></tr>
<tr><td><b>Designs</b></td><td>See which datasets suit each identification strategy.</td></tr>
<tr><td><b>Hotspot map</b></td><td>See country-level exposure to basic health risks and jump to the datasets that measure them at finer resolution.</td></tr></table>

<h2 class="sec"><span class="sn t1">A.2</span>Worked example</h2>
<div class="ex"><div class="q">“Did a maternal-health programme rolled out district by district increase institutional deliveries?”</div>
<div class="sel">Guided search: <b>Maternal & child health, gender</b> · <b>District or finer</b> · <b>Difference-in-differences with repeated cross-sections</b></div>
{ex_html}</div>
<p><strong>Reading the result.</strong> HMIS gives monthly, facility-reported service counts suited to an event study around rollout dates, but it counts services, not population rates. NFHS provides district-representative rates across rounds for a classic difference-in-differences design, but district samples are small. A natural design uses HMIS for timing and dynamics, with NFHS as the population-based check. DHS appears because it fits the design, but India's DHS surveys <em>are</em> the NFHS, so it adds cross-country comparison rather than new Indian data.</p>

<h2 class="sec"><span class="sn t1">A.3</span>Matching data to design</h2>
<table class="tbl"><tr class="c1"><th style="width:20%">Design</th><th style="width:36%">What it needs</th><th>Datasets in the Finder</th></tr>{design_rows}</table>

<h2 class="sec"><span class="sn t1">A.4</span>Ten comparability traps</h2>
<ol style="font-size:9.2pt;padding-left:16pt;color:var(--soft)">{trap_html}</ol>
</section>

{chapter('B1', 'c5', 'Brief 1', 'Where basic health risks cluster', 'Poverty, food insecurity and missing water, sanitation and hygiene overlap in the same countries.', 'B1')}
<p><strong>Question.</strong> Are basic health risks spread across many countries, or concentrated in a few that face several at once?</p>
<p><strong>Method.</strong> For each country, take the latest value from 2015 onward of five risks: food and nutrition insecurity; the shares of people <em>without</em> basic hygiene, sanitation and drinking water (100 minus the reported access share); and poverty at $3.00 a day. A country is flagged on a risk if it is in the top quarter of countries for that risk (thresholds: food insecurity ≥ {S['q75']['food']}%, no hygiene ≥ {S['q75']['hygiene']}%, no sanitation ≥ {S['q75']['sanitation']}%, no drinking water ≥ {S['q75']['water']}%, poverty ≥ {S['q75']['poverty']}%). Only the {S['n_full']} countries that report all five risks are compared.</p>
<p><strong>Findings.</strong> Risks cluster. <strong>{S['n_hot4plus']} countries are in the top quarter on at least four of the five risks, and {S['n_hot5']} on all five.</strong> {len([n for n in S['hot4_names'] if n != 'Djibouti'])} of the {S['n_hot4plus']} are in Sub-Saharan Africa{'; the other is Djibouti' if 'Djibouti' in S['hot4_names'] else ''}. Figure B1.1 shows the 15 countries with the highest burden. Across all countries, poverty moves closely with each risk (Spearman rank correlation with poverty: no hygiene {a['hygiene']['rho']:.2f}, n = {a['hygiene']['n']}; no sanitation {a['sanitation']['rho']:.2f}; no drinking water {a['water']['rho']:.2f}; food insecurity {a['food']['rho']:.2f}; high climate-hazard risk {a['climate']['rho']:.2f}).</p>
{fig('g1_hotspots', 'B1.1', f"15 of the {S['n_hot5']} countries in the top quarter on all five risks", 'Share of population, latest year from 2015; climate-hazard exposure shown for context (n/a = not reported)', SC + ' Ordered by number of risks flagged, then by share without basic hygiene.', 'var(--clay)')}
{fig('g2_poverty_hygiene', 'B1.2', 'Poverty and missing basic hygiene go together', f"Each dot is a country ({a['hygiene']['n']} with both measures)", SC, 'var(--clay)')}
<div class="box b-clay"><div class="bt">Interpretation and next steps</div>
<p>These are country-level associations, not causal effects: poverty, weak infrastructure and poor services share common causes. The overlap does suggest that single-sector programmes in these countries face compounding risks. To study it within countries, the Finder points to <strong>DHS</strong> and <strong>MICS</strong> (household water, sanitation, hygiene and child nutrition, with displaced GPS clusters in DHS) and to <strong>LSMS</strong> panels for poverty dynamics. A useful design links DHS clusters to climate exposure (spatial linkage), while respecting the coordinate displacement.</p></div>
</section>

{chapter('B2', 'c2', 'Brief 2', 'India in the global picture', 'India is below the world average on basic-service deprivation and climate-hazard exposure.', 'B2')}
<p><strong>Findings.</strong> On the Scorecard's latest values, India fares better than both South Asia and the world on missing basic hygiene ({I['hygiene']['IND']['v']}% of the population, against {I['hygiene']['SAS']['v']}% in South Asia and {I['hygiene']['WLD']['v']}% worldwide) and on high climate-hazard risk ({I['climate']['IND']['v']}% against {I['climate']['SAS']['v']}% and {I['climate']['WLD']['v']}%). It is close to both on sanitation ({I['sanitation']['IND']['v']}%) and in line with South Asia on drinking water ({I['water']['IND']['v']}%, half the world rate of {I['water']['WLD']['v']}%) (Figure B2.1).</p>
{fig('g3_india', 'B2.1', 'India, South Asia and the world', 'Share of population; year of latest value in brackets', SC, 'var(--blue)')}
<div class="box b-blue"><div class="bt">Two cautions</div>
<p><strong>Food insecurity</strong> has no Scorecard value for India, so India cannot be placed on that measure. <strong>Poverty at $3.00 a day</strong> is reported for India for {I['poverty']['IND']['t']} ({I['poverty']['IND']['v']}%) but for South Asia and the world for {I['poverty']['SAS']['t']}. The years differ and the regional figure includes India, so the two should not be compared directly. National averages also hide large differences between states; the district-level NFHS-6 fact sheets and the Health Dynamics of India tables are the next step for sub-national analysis.</p></div>
</section>

{chapter('B3', 'c4', 'Brief 3', 'Financial protection and maternal health in India', 'Insurance coverage has risen sharply; out-of-pocket spending fell for a decade, then ticked up.', 'B3')}
<p>This brief quotes headline figures from official releases {OFF}. They are reported as published, not recomputed; the Finder entries link to each source.</p>
{fig('g4_india_context', 'B3.1', 'Three official headline indicators', 'National Health Accounts; NSS Household Social Consumption: Health; Sample Registration System', 'Sources: NHA Estimates for India 2022–23 (NHSRC/MoHFW); NSS 80th round, Household Social Consumption: Health, January–December 2025, compared with the 75th round (2017–18) (NSO, MoSPI); SRS Special Bulletin on Maternal Mortality 2020–22 (Office of the Registrar General). As reported in the official releases.', 'var(--plum)')}
<p><strong>Financial protection.</strong> Out-of-pocket spending fell from 64.2% of total health expenditure in 2013–14 to 39.4% in 2021–22, then rose to 43.4% in 2022–23. Over roughly the same period, reported health insurance coverage rose from 14.1% (rural) and 19.1% (urban) in 2017–18 to 47.4% and 44.3% in 2025, with rural coverage now above urban.</p>
<p><strong>Maternal health.</strong> The maternal mortality ratio fell from 93 per 100,000 live births in 2019–21 to 88 in 2020–22. The SDG 2030 target is below 70.</p>
<div class="box b-plum"><div class="bt">Researchable questions and data</div><ul>
<li><strong>Did the insurance expansion reduce catastrophic health spending?</strong> Compare NSS 75th (2017–18) and 80th (2025) rounds across states with different scheme roll-out intensity (difference-in-differences with repeated cross-sections). Watch the recall periods and questionnaire changes, and the 2022–23 rise in out-of-pocket share, which suggests coverage has not translated evenly into protection.</li>
<li><strong>Is the maternal-mortality gap now about quality rather than access?</strong> With institutional delivery near universal, use HMIS for service-quality indicators over time (interrupted time series), NFHS-6 for antenatal-care content by district, and SRS for mortality trends. SRS reports maternal mortality only for larger states, in three-year pools.</li></ul></div>
</section>

{chapter('B4', 'c6', 'Brief 4', 'Health workforce and migration', 'India is a major origin of doctors and nurses working in OECD countries, yet domestic workforce data sit in separate sources.', 'B4')}
<p><strong>What is known.</strong> The OECD's <em>International Migration Outlook 2025</em> identifies India among the main countries of origin of both foreign-born doctors and nurses working in OECD countries. At home, the Health Dynamics of India tables report sanctioned posts, staff in position and shortfalls in public facilities by district.</p>
<p><strong>The measurement gap.</strong> No single source links training, domestic deployment and international migration of health workers. The Finder's migration and workforce sources each cover one piece:</p>
<table class="tbl"><tr class="c6"><th style="width:30%">Question</th><th>Datasets</th></tr>
<tr><td>How many health workers are in post, where, and what are the shortfalls?</td><td>Health Dynamics of India (district tables); WHO National Health Workforce Accounts (cross-country density)</td></tr>
<tr><td>Who works in health occupations, and on what terms?</td><td>PLFS (occupation, wages; district-representative from 2025)</td></tr>
<tr><td>How many leave, and to where?</td><td>OECD health workforce migration indicators (destination-country data); KNOMAD migrant stocks and remittances</td></tr>
<tr><td>Internal migration patterns</td><td>NSS 64th round (2007–08), PLFS 2020–21 migration module, Census 2011 D-series tables</td></tr></table>
<div class="box b-ochre"><div class="bt">Researchable question</div>
<p><strong>Does international recruitment of nurses reduce nurse availability in origin states?</strong> One design combines destination-country demand shocks (from OECD inflow data) with state-level exposure through historical migration networks (a shift-share design), and measures domestic outcomes with Health Dynamics of India staffing and PLFS employment. Key cautions: OECD data count workers by country of training or birth, not Indian state of origin, and public-sector staffing tables miss the private sector.</p></div>
</section>

<section class="pb"><div class="marker">@@C@@</div>
<div class="ch-open cn"><div class="k">Part C</div><h1>Limitations, catalogue and references</h1><p>What this guide can and cannot support.</p></div>
<ul style="font-size:9.4pt;padding-left:16pt">
<li><strong>Catalogue.</strong> Metadata only. {N - NCHK} entries are still marked to verify. Details such as release status change; check the custodian's site before starting a study.</li>
<li><strong>Country analysis.</strong> Country values use each country's latest year from 2015 onward, so years differ across countries. The hotspot comparison covers only the {S['n_full']} countries reporting all five risks, which over-represents lower-income countries. Correlations are descriptive.</li>
<li><strong>Official figures.</strong> Brief 3 quotes published headline figures; definitions (for example, whether coverage is counted per person or per household) follow the original releases.</li>
</ul>
<div class="tcap">Table C.1 &nbsp;The catalogue</div>
<table class="tbl"><tr class="cn"><th>Dataset</th><th>Scope</th><th>Structure</th><th>Finest level</th><th>Access</th><th>Status</th></tr>{catalogue}</table>
<h2 class="sec">References</h2>
<ol class="refs">
<li>Ministry of Health and Family Welfare / National Health Systems Resource Centre. 2026. <em>National Health Accounts Estimates for India 2022–23</em>. New Delhi.</li>
<li>National Statistics Office, MoSPI. 2026. <em>Household Social Consumption: Health, NSS 80th Round (January–December 2025)</em>. New Delhi.</li>
<li>Office of the Registrar General, India. 2025. <em>Special Bulletin on Maternal Mortality in India 2020–22</em>. Sample Registration System.</li>
<li>OECD. 2025. <em>International Migration Outlook 2025</em>. Chapter: International migration of health professionals to OECD countries. Paris: OECD Publishing.</li>
<li>World Bank Group. 2025. <em>World Bank Group Scorecard</em>, FY25 cycle: vision indicators SN_ITK_MSFI_ZS, SH_STA_HYGN_ZS, SH_STA_BASS_ZS, SH_H2O_BASW_ZS, SI_POV_DDAY, EN_CLM_VULN. scorecard.worldbank.org (accessed 2026).</li>
<li>Dataset custodians and sources for each catalogue entry are linked in the Finder (ashuarora.com/data-buff).</li>
</ol>
</section>
"""


def page(b):
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Data Finder Guide</title><link rel="stylesheet" href="../guide.css"></head><body>{b}</body></html>'


COVER = """<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="../guide.css">
<style>@page { size: A4; margin: 0; } body { margin: 0; }
.cover { width: 210mm; height: 297mm; background: #173F3B; position: relative; overflow: hidden; color: #fff; }
.grid { position: absolute; right: -10mm; top: 18mm; display: grid; grid-template-columns: repeat(6, 24mm); gap: 4mm; transform: rotate(-8deg); }
.grid i { height: 24mm; border-radius: 5mm; background: #84A98C; opacity: .55; }
.grid i:nth-child(3n) { background: #0F766E; opacity: .9; } .grid i:nth-child(4n) { background: #C6D9CE; opacity: .5; }
.grid i:nth-child(7n) { background: #B96A3E; opacity: .9; } .grid i:nth-child(11n) { background: #F3EBDD; opacity: .7; }
.shade { position: absolute; left: 0; right: 0; bottom: 0; height: 165mm; background: linear-gradient(180deg, rgba(23,63,59,0), #173F3B 40%); }
.title { position: absolute; left: 20mm; right: 20mm; bottom: 62mm; }
.k { font-family: 'SS3'; font-size: 10pt; letter-spacing: .22em; text-transform: uppercase; color: #BFE0D6; font-weight: 600; }
h1 { font-family: 'SS4'; font-weight: 700; font-size: 40pt; line-height: 1.04; margin: 6mm 0 5mm; }
.st { font-family: 'SS4'; font-size: 15pt; line-height: 1.35; color: #D7EAE5; max-width: 150mm; }
.meta { position: absolute; left: 20mm; right: 20mm; bottom: 18mm; display: flex; justify-content: space-between; align-items: flex-end; font-family: 'SS3'; font-size: 10pt; color: #C4D8D2; border-top: 0.6pt solid rgba(255,255,255,.3); padding-top: 5mm; }
.meta b { color: #fff; font-size: 13pt; font-weight: 600; display: block; }
</style></head><body><div class="cover">
<div class="grid">__GRID__</div><div class="shade"></div>
<div class="title"><div class="k">User guide &amp; issue briefs · September 2026</div>
<h1>Health Economics<br>Data Finder</h1>
<div class="st">How to find evaluation-ready health data, with four briefs on where health risks cluster, India's position, financial protection and the health workforce</div></div>
<div class="meta"><div><b>Ashu Arora</b>MA, Economics, Johns Hopkins University<br>School of Advanced International Studies, Washington, D.C.</div><div style="text-align:right">Companion to ashuarora.com/data-buff</div></div>
<div style="position:absolute;left:20mm;bottom:8mm;font-family:'SS3';font-size:7.5pt;color:rgba(255,255,255,.55)">&copy; Ashu Arora</div>
</div></body></html>"""

FOOT = """<div style="width:100%;font-family:'Liberation Sans',Arial,sans-serif;font-size:7.5px;color:#7C8F8C;padding:0 18mm;display:flex;justify-content:space-between">
<span>Health Economics Data Finder: User Guide and Issue Briefs</span><span>&copy; Ashu Arora&nbsp;&nbsp;·&nbsp;&nbsp;<span class="pageNumber"></span></span></div>"""


def render(pw, html, pdf, footer):
    b = pw.chromium.launch(executable_path=CHROME)
    pg = b.new_page()
    pg.goto(html.as_uri())
    pg.wait_for_timeout(600)
    opts = dict(path=str(pdf), format="A4", print_background=True, prefer_css_page_size=True)
    if footer:
        opts.update(display_header_footer=True, header_template="<span></span>", footer_template=FOOT,
                    margin={"top": "19mm", "bottom": "20mm", "left": "18mm", "right": "18mm"})
    pg.pdf(**opts)
    b.close()


def main():
    (BUILD / "cover.html").write_text(COVER.replace("__GRID__", "<i></i>" * 36))
    with sync_playwright() as pw:
        render(pw, BUILD / "cover.html", BUILD / "cover.pdf", False)
        (BUILD / "body.html").write_text(page(body({})))
        render(pw, BUILD / "body.html", BUILD / "body.pdf", True)
        toc = {}
        for i, pg in enumerate(PdfReader(str(BUILD / "body.pdf")).pages, start=1):
            for m in re.findall(r"@@(A|B\d|C)@@", pg.extract_text() or ""):
                toc.setdefault(m, i)
        (BUILD / "body.html").write_text(page(body(toc)))
        render(pw, BUILD / "body.html", BUILD / "body.pdf", True)
    w = PdfWriter()
    for f in ["cover.pdf", "body.pdf"]:
        for pg in PdfReader(str(BUILD / f)).pages:
            w.add_page(pg)
    w.add_metadata({"/Title": "Health Economics Data Finder: User Guide and Issue Briefs", "/Author": "Ashu Arora"})
    out = HERE / "data-finder-guide.pdf"
    with open(out, "wb") as fh:
        w.write(fh)
    shutil.copy(out, SITE_PDF)
    print("toc", toc, "pages", len(PdfReader(str(out)).pages))


if __name__ == "__main__":
    main()
