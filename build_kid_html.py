"""
build_kid_html.py — Génère les KID HTML à partir des KID Markdown.

  STRATEGY_KID.md       → STRATEGY_KID.html        (fiche complète + schéma pipeline)
  STRATEGY_KID_SHORT.md → STRATEGY_KID_SHORT.html  (synthèse 1 page, sans le grand schéma)

Thème "A4 dark" + graphique Highcharts du score de régime Risk On / Risk Off.

Usage : python build_kid_html.py   → écrit les deux .html
Dépendance : pip install markdown
"""

from pathlib import Path
import markdown

ROOT = Path(__file__).parent

HEAD = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>__TITLE__</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<script src="https://code.highcharts.com/highcharts.js"></script>
<style>
:root{
  --bg:#0a0f24; --card:#0e1530; --card2:#111a3a; --line:#1e3f66;
  --txt:#e8eefc; --muted:#9fb3d4; --accent:#00bfff; --accent2:#66ccff; --link:#7cc0ff;
  --code:#0c1430; --green:#5ce0a8; --red:#ff7a8a; --amber:#ffcf6b;
}
*{box-sizing:border-box;}
html,body{background:var(--bg);margin:0;padding:0;}
body{font-family:'Inter',sans-serif;color:var(--txt);line-height:1.55;font-size:14px;}
.page{width:210mm;max-width:210mm;margin:24px auto;padding:18mm 16mm;background:var(--bg);
  border-radius:10px;box-shadow:0 0 30px rgba(0,0,0,.85);}
.hero{background:linear-gradient(135deg,#0e1733 0%,#0a0f24 70%);border:1px solid var(--line);
  border-radius:12px;padding:26px 28px;margin-bottom:22px;}
.hero .tag{color:var(--accent);font-weight:700;letter-spacing:.18em;font-size:11px;text-transform:uppercase;}
.hero h1{margin:6px 0 4px;font-size:30px;font-weight:800;color:#fff;border:none;padding:0;}
.hero p{margin:6px 0 0;color:var(--muted);font-size:13px;}
#chart{height:300px;margin:14px 0 4px;}
.chart-card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px 6px;margin:18px 0 26px;}
.chart-card .cap{color:var(--muted);font-size:12px;margin:0 4px 6px;}
h1,h2,h3,h4{color:#fff;font-weight:700;line-height:1.25;}
h1{font-size:24px;border-bottom:2px solid var(--line);padding-bottom:6px;margin:34px 0 14px;}
h2{font-size:19px;color:var(--accent2);margin:30px 0 12px;padding-bottom:5px;border-bottom:1px solid var(--line);}
h3{font-size:15.5px;color:var(--accent2);margin:22px 0 8px;}
h4{font-size:14px;color:var(--link);margin:16px 0 6px;}
p{margin:9px 0;}
a{color:var(--link);text-decoration:none;} a:hover{text-decoration:underline;}
strong{color:#fff;font-weight:700;}
hr{border:none;border-top:1px solid var(--line);margin:26px 0;}
ul,ol{padding-left:22px;} li{margin:4px 0;}
blockquote{border-left:3px solid var(--accent);background:var(--card);margin:12px 0;padding:8px 16px;
  color:var(--muted);border-radius:0 8px 8px 0;}
blockquote strong{color:var(--accent2);}
code{font-family:'JetBrains Mono',monospace;font-size:12.5px;background:var(--code);color:#bcd6ff;
  padding:1.5px 6px;border-radius:5px;border:1px solid var(--line);}
pre{background:var(--code);border:1px solid var(--line);border-radius:10px;padding:14px 16px;overflow-x:auto;
  font-family:'JetBrains Mono',monospace;font-size:12.5px;line-height:1.5;color:#cfe0ff;}
pre code{background:none;border:none;padding:0;color:inherit;font-size:12.5px;}
table{border-collapse:collapse;width:100%;margin:14px 0;font-size:12.8px;border-radius:8px;overflow:hidden;}
th,td{border:1px solid var(--line);padding:7px 11px;text-align:left;vertical-align:top;}
th{background:var(--card2);color:var(--accent2);font-weight:600;}
tr:nth-child(even) td{background:rgba(255,255,255,.02);}
tr:hover td{background:rgba(0,191,255,.06);}
@media print{
  @page{size:A4;margin:10mm;}
  body{background:#fff;}
  .page{box-shadow:none;margin:0;width:auto;padding:0;}
}
@media (max-width:840px){.page{width:auto;padding:18px;margin:0;}}
</style>
</head>
<body>
<div class="page">
  <div class="hero">
    <div class="tag">__TAG__</div>
    <h1>__H1__</h1>
    <p>__SUB__</p>
  </div>

  <div class="chart-card">
    <p class="cap">Le <b>score de régime</b> &isin; [&minus;1, +1] : au-dessus de <code>+0.20</code> &rarr;
       <span style="color:#5ce0a8">Risk On</span> (on penche vers l'offensif) ; en-dessous de <code>&minus;0.20</code> &rarr;
       <span style="color:#ff7a8a">Risk Off</span> (on penche vers le défensif). Une <b>bascule</b> déclenche un rebalancement le jour même.</p>
    <div id="chart"></div>
  </div>
"""

PIPELINE_SVG = """
  <div class="chart-card">
    <p class="cap">Le pipeline en un coup d'&oelig;il : <b>lire la phase de marché</b> &rarr; <b>pencher la grille</b>
       (secteur &times; r&eacute;gion) &rarr; <b>budg&eacute;ter les cases</b> &rarr; <b>choisir les meilleures actions</b>.
        R&eacute;-&eacute;valu&eacute; chaque semaine et &agrave; chaque bascule de r&eacute;gime.</p>
    <svg viewBox="0 0 900 560" width="100%" style="font-family:Inter,sans-serif;">
      <defs>
        <marker id="ar" markerWidth="9" markerHeight="9" refX="4.5" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 Z" fill="#3a6ea5"/>
        </marker>
      </defs>
      <g text-anchor="middle">
        <rect x="40" y="14" width="820" height="40" rx="8" fill="#0e1733" stroke="#1e3f66"/>
        <text x="450" y="39" fill="#cfe0ff" font-size="13.5">Univers ACWI — actions liquides (USD) &nbsp;+&nbsp; panel d'ETF (lecture du r&eacute;gime, jamais d&eacute;tenus)</text>
        <line x1="450" y1="55" x2="450" y2="72" stroke="#3a6ea5" stroke-width="1.4" marker-end="url(#ar)"/>
        <rect x="120" y="74" width="660" height="52" rx="8" fill="#0e2540" stroke="#00bfff" stroke-width="1.4"/>
        <text x="450" y="95" fill="#7cc0ff" font-size="14" font-weight="700">&#9312; R&Eacute;GIME Risk On / Risk Off &nbsp;&middot;&nbsp; score &isin; [&minus;1,+1]</text>
        <text x="450" y="113" fill="#9fb3d4" font-size="10.5">ETF : momentum large &middot; cycliques/d&eacute;fensifs &middot; courbe &middot; cr&eacute;dit &middot; or &middot; USD &middot; EM/DM &nbsp;(&Eacute;TAPE 1)</text>
        <line x1="450" y1="127" x2="450" y2="146" stroke="#3a6ea5" stroke-width="1.4" marker-end="url(#ar)"/>
        <rect x="120" y="148" width="660" height="40" rx="8" fill="#0e1530" stroke="#1e3f66"/>
        <text x="450" y="167" fill="#cfe0ff" font-size="13">&#9313; BAROM&Egrave;TRE &mdash; grille secteur &times; r&eacute;gion, tilt modul&eacute; par le r&eacute;gime</text>
        <text x="450" y="182" fill="#7f9bc4" font-size="10.5">tilt = biais_statique &times; r&eacute;gime + momentum_z &nbsp;(&Eacute;TAPE 2)</text>
      </g>
      <g text-anchor="middle" font-size="11.5">
        <rect x="150" y="200" width="270" height="38" rx="8" fill="#10241c" stroke="#5ce0a8"/>
        <text x="285" y="218" fill="#5ce0a8" font-weight="700">OFFENSIF (Risk On)</text>
        <text x="285" y="232" fill="#8fc9b0" font-size="9.5">tech &middot; conso cyclique &middot; industrie &middot; mat&eacute;riaux</text>
        <rect x="480" y="200" width="270" height="38" rx="8" fill="#241318" stroke="#ff7a8a"/>
        <text x="615" y="218" fill="#ff9aa6" font-weight="700">D&Eacute;FENSIF (Risk Off)</text>
        <text x="615" y="232" fill="#cf9aa2" font-size="9.5">sant&eacute; &middot; conso de base &middot; utilities</text>
      </g>
      <g stroke="#3a6ea5" stroke-width="1.4" marker-end="url(#ar)">
        <line x1="285" y1="188" x2="285" y2="198"/><line x1="615" y1="188" x2="615" y2="198"/>
        <line x1="285" y1="239" x2="420" y2="258"/><line x1="615" y1="239" x2="480" y2="258"/>
      </g>
      <g text-anchor="middle">
        <rect x="120" y="260" width="660" height="40" rx="8" fill="#0e1530" stroke="#1e3f66"/>
        <text x="450" y="279" fill="#cfe0ff" font-size="13">&#9314; BUDGETS par cat&eacute;gorie &mdash; &prop; tilt, plafonds cat&eacute;gorie/r&eacute;gion (water-filling)</text>
        <text x="450" y="294" fill="#7f9bc4" font-size="10.5">&Sigma; = 1 &nbsp;(&Eacute;TAPE 3)</text>
        <line x1="450" y1="301" x2="450" y2="320" stroke="#3a6ea5" stroke-width="1.4" marker-end="url(#ar)"/>
        <rect x="120" y="322" width="660" height="52" rx="8" fill="#0e2540" stroke="#00bfff" stroke-width="1.4"/>
        <text x="450" y="343" fill="#7cc0ff" font-size="14" font-weight="700">&#9315; S&Eacute;LECTION &mdash; fondamental PIT (qualit&eacute;+croissance) + momentum</text>
        <text x="450" y="361" fill="#9fb3d4" font-size="10.5">10&ndash;20 lignes &middot; budget de cat&eacute;gorie r&eacute;parti &middot; plafond 12 %/position &nbsp;(&Eacute;TAPE 4)</text>
        <line x1="450" y1="375" x2="450" y2="394" stroke="#3a6ea5" stroke-width="1.4" marker-end="url(#ar)"/>
        <rect x="300" y="396" width="300" height="40" rx="8" fill="#0e2540" stroke="#66ccff" stroke-width="1.5"/>
        <text x="450" y="421" fill="#cfe0ff" font-size="13.5" font-weight="700">PORTEFEUILLE &mdash; 10 &agrave; 20 actions</text>
      </g>
      <g text-anchor="middle">
        <rect x="630" y="460" width="230" height="74" rx="8" fill="#1a1330" stroke="#a98bff"/>
        <text x="745" y="481" fill="#c9b6ff" font-size="12.5" font-weight="700">Rebalancement hybride</text>
        <text x="745" y="500" fill="#b9a6e8" font-size="10.5">cadence moteur quotidienne</text>
        <text x="745" y="515" fill="#b9a6e8" font-size="10.5">ancre hebdo (7 j) <tspan fill="#9fb3d4">OU</tspan></text>
        <text x="745" y="530" fill="#b9a6e8" font-size="10.5">bascule de r&eacute;gime &rarr; le jour m&ecirc;me</text>
      </g>
      <rect x="40" y="460" width="560" height="74" rx="8" fill="#0e1530" stroke="#1e3f66"/>
      <text x="60" y="483" fill="#9fb3d4" font-size="11">Anti-look-ahead : prix tronqu&eacute;s &agrave; <tspan fill="#bcd6ff">as_of</tspan> &middot; fondamentaux gat&eacute;s par <tspan fill="#bcd6ff">filing_date</tspan></text>
      <text x="60" y="503" fill="#9fb3d4" font-size="11">R&eacute;gime <tspan fill="#bcd6ff">rules</tspan> causal &middot; ex&eacute;cution diff&eacute;r&eacute;e d'1 barre &middot; d&eacute;list&eacute;s inclus</text>
      <text x="60" y="523" fill="#9fb3d4" font-size="11">Backtest == production (d&eacute;cision de rebal reconstruite chronologiquement)</text>
    </svg>
  </div>
"""

CHART_SCRIPT = """
<script>
(function(){
  var data=[], t, s;
  for(t=0;t<=120;t+=1){
    s = 0.55*Math.sin(t/13) + 0.30*Math.sin(t/5+1.0) + 0.18*Math.sin(t/29);
    s = Math.max(-1,Math.min(1,s));
    data.push([t, +s.toFixed(3)]);
  }
  Highcharts.chart('chart',{
    chart:{backgroundColor:'transparent',style:{fontFamily:'Inter,sans-serif'}},
    title:{text:null}, credits:{enabled:false}, legend:{enabled:false},
    xAxis:{title:{text:'temps',style:{color:'#9fb3d4'}},labels:{style:{color:'#9fb3d4'}},
      gridLineColor:'#13234a',lineColor:'#1e3f66',tickColor:'#1e3f66'},
    yAxis:{title:{text:'score de régime',style:{color:'#9fb3d4'}},labels:{style:{color:'#9fb3d4'}},
      min:-1.1,max:1.1,gridLineColor:'#13234a',
      plotLines:[
        {color:'#5ce0a8',width:1.2,value:0.20,dashStyle:'Dash',label:{text:' Risk On (+0.20)',style:{color:'#5ce0a8'},y:-4}},
        {color:'#ff7a8a',width:1.2,value:-0.20,dashStyle:'Dash',label:{text:' Risk Off (−0.20)',style:{color:'#ff7a8a'},y:14}},
        {color:'#3a6ea5',width:1,value:0}
      ]},
    tooltip:{backgroundColor:'#0e1530',borderColor:'#1e3f66',style:{color:'#e8eefc'},
      formatter:function(){return 'score : <b>'+this.y.toFixed(2)+'</b>';}},
    plotOptions:{series:{marker:{enabled:false}}},
    series:[{type:'line',data:data,lineWidth:2.4,zoneAxis:'y',
      zones:[{value:-0.20,color:'#ff7a8a'},{value:0.20,color:'#ffcf6b'},{color:'#5ce0a8'}]}]
  });
})();
</script>
</body>
</html>
"""


def render(md_name, out_name, title, tag, h1, sub, with_pipeline):
    body = markdown.markdown(
        (ROOT / md_name).read_text(encoding="utf-8"),
        extensions=["tables", "fenced_code", "toc", "sane_lists", "attr_list"],
    )
    head = (HEAD.replace("__TITLE__", title).replace("__TAG__", tag)
                .replace("__H1__", h1).replace("__SUB__", sub))
    html = head + (PIPELINE_SVG if with_pipeline else "") + body + "\n</div>\n" + CHART_SCRIPT
    (ROOT / out_name).write_text(html, encoding="utf-8")
    print(f"OK -> {out_name}  ({(ROOT / out_name).stat().st_size // 1024} Ko)")


def main():
    render("STRATEGY_KID.md", "STRATEGY_KID.html",
           "Dynamic Opportunity — Key Information Document",
           "Key Information Document",
           "Dynamic Opportunity — Rotation Risk On / Risk Off",
           "Rotation sectorielle &amp; géographique pilotée par un régime de marché lu sur ETF. "
           "Actions only (ETF exclus de l'investissable) · 10-20 lignes · univers ACWI · long uniquement.",
           with_pipeline=True)
    render("STRATEGY_KID_SHORT.md", "STRATEGY_KID_SHORT.html",
           "Dynamic Opportunity — KID court",
           "KID court · synthèse",
           "Dynamic Opportunity — l'essentiel",
           "Rotation Risk On / Risk Off : lire la phase de marché, pencher la grille "
           "secteur × région, choisir 10-20 actions. Synthèse en une page.",
           with_pipeline=False)


if __name__ == "__main__":
    main()
