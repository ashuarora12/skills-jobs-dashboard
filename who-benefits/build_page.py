"""Embed output/dashboard_data.json into page_template.html -> the site pages.

Builds two layouts from the same template, so data and chart code can't drift apart:
  who-benefits.html        long-scroll, five numbered sections (default)
  who-benefits-story.html  story-first: three headline findings up top, each
                           linking to its evidence; context and methods after
  who-benefits-studio.html a different visual design: sidebar app layout,
                           Space Grotesk / Inter type, teal & violet palette
  who-benefits-flow.html   standalone scroll-driven data story (flow_template.html):
                           animated dot grids, calm sage/sand palette, no Chart.js
"""
import re
from pathlib import Path

HERE = Path(__file__).parent
SITE = HERE.parent / "site"

template = (HERE / "page_template.html").read_text()
data = (HERE / "output" / "dashboard_data.json").read_text().replace("</", "<\\/")
assert "/*__DATA__*/null" in template


def block(html, start, end):
    i = html.index(start)
    j = html.index(end, i) + len(end)
    return html[i:j]


def story(html):
    sections = {k: block(html, f'<section id="{k}">', "</section>")
                for k in ["results", "themes", "delivery", "gender", "methods"]}
    hero = block(html, '<header class="hero">', "</header>")
    order = ["themes", "delivery", "gender", "results", "methods"]
    new_no = {k: f"{i + 1:02d}" for i, k in enumerate(order)}
    old_no = {"results": "01", "themes": "02", "delivery": "03", "gender": "04", "methods": "05"}
    remap = {old_no[k]: new_no[k] for k in old_no}

    heads = {
        "themes": "Finding 1 &middot; The health workforce is almost invisible in measured results",
        "delivery": "Finding 2 &middot; Results arrive late, and a model can flag which ones are at risk",
        "gender": "Finding 3 &middot; Women are often not counted directly, which hides any gap",
        "results": "Context &middot; Who is being reached?",
    }
    for k, s in sections.items():
        s = re.sub(r'<span class="section-no">\d\d</span>', f'<span class="section-no">{new_no[k]}</span>', s)
        if k in heads:
            s = re.sub(r"<h2>.*?</h2>", f"<h2>{heads[k]}</h2>", s, count=1)
        sections[k] = s

    # methods: keep the heading visible, fold the detail into an expandable panel
    m = sections["methods"]
    head_end = m.index('<p class="section-intro">')
    grid_start = m.index('<div class="method-grid">')
    related = m.index('<div class="callout note">')
    m = (m[:grid_start] +
         '<details class="methods-fold" open><summary>Show / hide provenance, limitations, privacy &amp; reproducibility</summary>' +
         m[grid_start:related] + '</details>' + m[related:])
    sections["methods"] = m

    findings = '''
<div class="findings" id="findings">
  <a class="finding" href="#themes"><span class="fk">Finding 1</span><span class="fn" id="f1n">–</span><span class="ft" id="f1t"></span><span class="fg">See the text classifier &darr;</span></a>
  <a class="finding" href="#delivery"><span class="fk">Finding 2</span><span class="fn" id="f2n">–</span><span class="ft" id="f2t"></span><span class="fg">See the early-warning model &darr;</span></a>
  <a class="finding" href="#gender"><span class="fk">Finding 3</span><span class="fn" id="f3n">–</span><span class="ft" id="f3t"></span><span class="fg">See the matched comparison &darr;</span></a>
</div>'''
    story_hero = f'''<header class="hero story">
  <p class="eyebrow">DATA SCIENCE PORTFOLIO PROJECT &middot; DEVELOPMENT ANALYTICS</p>
  <h1 style="max-width:24ch">Who benefits? Health, jobs &amp; gender in the World Bank Group portfolio</h1>
  <p class="lede">Three findings from the Bank Group's own FY25 results data on <span id="ledeN">–</span> projects. Each card links to the evidence, the method and its limits.</p>
  {findings}
  <div class="strip">
    <span><strong id="statProjects">–</strong> projects</span><span><strong id="statCountries">–</strong> countries</span>
    <span><strong id="statRecords">–</strong> project-indicator records</span><span><strong id="statHW">–</strong> measure health workers</span>
    <span class="strip-src">Source: WBG Scorecard, FY25 (30 June 2025) &middot; Python &rarr; static JSON &rarr; this page</span>
  </div>
  <span id="glanceHW" hidden></span>
</header>'''

    css = '''
  header.hero.story { padding-bottom: 34px; }
  .findings { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin: 6px 0 22px; }
  @media (max-width: 860px) { .findings { grid-template-columns: 1fr; } }
  .finding { display: flex; flex-direction: column; gap: 6px; background: var(--paper-raised); border: 1px solid var(--rule); border-top: 3px solid var(--gold); border-radius: 3px; padding: 18px 20px; text-decoration: none; color: var(--ink); }
  .finding:hover { border-color: var(--gold); }
  .finding .fk { font-family: 'IBM Plex Mono', monospace; font-size: 11px; letter-spacing: 0.05em; text-transform: uppercase; color: var(--gold); }
  .finding .fn { font-family: 'Source Serif 4', serif; font-size: 34px; font-weight: 700; line-height: 1.05; }
  .finding .ft { font-size: 14px; color: var(--ink-soft); line-height: 1.45; flex: 1; }
  .finding .fg { font-size: 12px; color: var(--blue); font-family: 'IBM Plex Mono', monospace; }
  .strip { display: flex; flex-wrap: wrap; gap: 8px 22px; font-size: 13px; color: var(--ink-faint); border-top: 1px solid var(--rule); padding-top: 14px; }
  .strip strong { color: var(--ink); font-family: 'IBM Plex Mono', monospace; font-weight: 500; }
  .strip .strip-src { flex-basis: 100%; font-size: 12px; }
  details.methods-fold > summary { cursor: pointer; font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: var(--ink-faint); margin-bottom: 16px; }
  details.methods-fold > summary:hover { color: var(--ink); }
</style>'''

    js = '''
<script>
(function () {
  const T = DATA.themes, M = DATA.model, A = DATA.gender_audit, P = DATA.psm;
  const hw = T.summary.find(x => x.key === 'health_workforce');
  const a0 = M.by_age[0], a3 = M.by_age[M.by_age.length - 1];
  const p = x => Math.round(x * 100) + '%';
  document.getElementById('ledeN').textContent = DATA.meta.projects.toLocaleString('en-US');
  document.getElementById('f1n').textContent = `${hw.projects} of ${T.n_projects.toLocaleString('en-US')}`;
  document.getElementById('f1t').textContent = `projects report an indicator about health workers, and ${T.health_workforce_and_migration} link them to labour mobility. Jobs and skills indicators appear in ${T.summary.find(x => x.key === 'jobs_skills').projects}.`;
  document.getElementById('f2n').textContent = `${p(a0.rate)} vs ${p(a3.rate)}`;
  document.getElementById('f2t').textContent = `of results trail schedule in projects under 3 years old vs. 7+ years. A cross-validated model ranks at-risk results with AUC ${M.models[M.best].auc.toFixed(2)}.`;
  document.getElementById('f3n').textContent = p(A.imputed / A.pairs);
  document.getElementById('f3t').textContent = `of the ${A.pairs.toLocaleString('en-US')} results reported for women use a fixed share of the total, not a count. Where women are counted, fragile settings show no detectable extra gap (${P.att > 0 ? '+' : ''}${P.att.toFixed(1)} pp, 95% CI ${P.ci[0].toFixed(1)} to +${P.ci[1].toFixed(1)}).`;
})();
</script>
</body>'''

    body = "\n\n".join(sections[k] for k in order)
    first = html.index('<section id="results">')
    last = html.index("</section>", html.index('<section id="methods">')) + len("</section>")
    out = html[:first] + body + html[last:]
    out = out.replace(hero, story_hero)
    out = out.replace("</style>", css, 1)
    # cross-references in prose ("section 03") follow the new numbering
    out = re.sub(r"([Ss]ection) 0(\d)", lambda mm: f"{mm.group(1)} {remap['0' + mm.group(2)]}", out)
    toc_old = block(out, '<nav class="toc"', "</nav>")
    out = out.replace(toc_old, '<nav class="toc" aria-label="Sections"><a href="#themes">01 Workforce</a><a href="#delivery">02 Delivery</a><a href="#gender">03 Gender</a><a href="#results">04 Context</a><a href="#methods">05 Methods</a></nav>')
    out = out.replace("</body>", js, 1) if out.count("</body>") == 1 else out
    out = out.replace("<title>Who Benefits? | Ashu Arora</title>", "<title>Who Benefits? (Story view) | Ashu Arora</title>")
    return out


def studio(html):
    """Completely different visual design (sidebar app, Space Grotesk/Inter, teal/violet),
    wrapping the same sections and the same chart code."""
    shell = (HERE / "redesign_shell.html").read_text()
    first = html.index('<section id="results">')
    last = html.index("</section>", html.index('<section id="methods">')) + len("</section>")
    sections = html[first:last]
    footer = block(html, "<footer>", "</footer>")
    script = block(html, "<script>\nconst DATA", "</script>")
    # chart fonts follow the new type system
    script = (script.replace("'IBM Plex Sans', sans-serif", "'Inter', sans-serif")
                    .replace("'IBM Plex Mono',monospace", "'JetBrains Mono',monospace")
                    .replace("'IBM Plex Mono', monospace", "'JetBrains Mono', monospace"))
    return (shell.replace("{{SECTIONS}}", sections).replace("{{FOOTER}}", footer)
                 .replace("{{SCRIPT}}", script))


pages = {"who-benefits.html": template, "who-benefits-story.html": story(template),
         "who-benefits-studio.html": studio(template),
         "who-benefits-flow.html": (HERE / "flow_template.html").read_text()}
for name, html in pages.items():
    path = SITE / name
    path.write_text(html.replace("/*__DATA__*/null", data))
    print(f"wrote {path} ({path.stat().st_size / 1024:.0f} KB)")
