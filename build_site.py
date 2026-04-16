"""
정적 HTML 사이트 생성기.
CSV 데이터 → docs/index.html (GitHub Pages 배포용)

실행: python build_site.py
"""

import json
import datetime
from pathlib import Path

import pandas as pd

# ── 데이터 로드 ───────────────────────────────────────────

data_dir = Path("data")
bat_files = sorted(data_dir.glob("*전체*batting.csv"))
pit_files = sorted(data_dir.glob("*전체*pitching.csv"))

if not bat_files or not pit_files:
    raise FileNotFoundError("data/ 아래 전체 CSV 없음. python main.py 먼저 실행하세요.")

bat = pd.concat([pd.read_csv(f) for f in bat_files], ignore_index=True)
pit = pd.concat([pd.read_csv(f) for f in pit_files], ignore_index=True)

updated = datetime.datetime.fromtimestamp(bat_files[-1].stat().st_mtime).strftime("%Y-%m-%d")
AVAILABLE_SEASONS = sorted(bat["시즌"].unique().tolist()) if "시즌" in bat.columns else [2025]
TEAMS = sorted(bat["팀"].dropna().unique().tolist())

TEAM_COLORS = {
    "LG":  "#C30452", "두산": "#131230", "KT":  "#3A3A3A",
    "SSG": "#CE0E2D", "NC":  "#071D4F", "KIA": "#EA0029",
    "롯데": "#002960", "삼성": "#074CA1", "한화": "#FF6600",
    "키움": "#820024",
}

# ── JSON 데이터 ────────────────────────────────────────────

BAT_COLS = ["시즌", "선수명", "팀", "PA", "AVG", "OBP", "SLG", "OPS",
            "wOBA", "wRC+", "ISO", "BABIP", "OPS+", "bWAR"]
PIT_COLS = ["시즌", "선수명", "팀", "IP", "IP_float", "ERA", "FIP", "xFIP",
            "ERA+", "WHIP", "K/9", "BB/9", "K/BB", "pWAR"]

bat_cols = [c for c in BAT_COLS if c in bat.columns]
pit_cols = [c for c in PIT_COLS if c in pit.columns]

bat_json     = bat[bat_cols].round(3).to_json(orient="records", force_ascii=False)
pit_json     = pit[pit_cols].round(3).to_json(orient="records", force_ascii=False)
teams_json   = json.dumps(["전체"] + TEAMS, ensure_ascii=False)
seasons_json = json.dumps(["전체"] + AVAILABLE_SEASONS, ensure_ascii=False)

# ── HTML ─────────────────────────────────────────────────

html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>KBO 세이버매트릭스</title>

<!-- PWA -->
<link rel="manifest" href="manifest.json">
<meta name="theme-color" content="#003580">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="KBO Stats">
<link rel="apple-touch-icon" href="icons/icon-192.png">

<link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/dataTables.bootstrap5.min.css">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css">
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  body {{ font-family: 'Noto Sans KR', 'Apple SD Gothic Neo', sans-serif;
          background:#f8f9fa; padding-bottom:env(safe-area-inset-bottom); }}
  h1 {{ font-size:1.4rem; font-weight:700; }}
  .nav-tabs .nav-link {{ font-weight:600; color:#495057; padding:10px 16px; }}
  .nav-tabs .nav-link.active {{ color:#003580; border-bottom:3px solid #003580; }}
  .team-badge {{ display:inline-block; padding:1px 7px; border-radius:4px;
                 font-size:0.78rem; font-weight:600; color:#fff; }}
  .chart-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:16px; }}
  .chart-box {{ background:#fff; border-radius:8px; padding:4px;
                box-shadow:0 1px 4px rgba(0,0,0,.08); min-height:380px; }}
  .chart-full {{ background:#fff; border-radius:8px; padding:4px;
                 box-shadow:0 1px 4px rgba(0,0,0,.08); margin-top:16px; min-height:420px; }}
  @media (max-width:768px) {{
    .chart-grid {{ grid-template-columns:1fr; }}
    h1 {{ font-size:1.1rem; }}
    .container-fluid {{ padding:10px 12px; }}
    .nav-tabs .nav-link {{ padding:8px 12px; font-size:0.9rem; }}
    table.dataTable td, table.dataTable th {{ font-size:0.75rem; }}
  }}
  .filter-bar {{ display:flex; gap:12px; align-items:flex-end; flex-wrap:wrap; margin-bottom:12px; }}
  .dataTables_wrapper .dataTables_filter input {{ border:1px solid #ced4da; border-radius:4px; padding:4px 8px; }}
  table.dataTable td, table.dataTable th {{ font-size:0.82rem; white-space:nowrap; }}
</style>
</head>
<body>
<div class="container-fluid py-3 px-4">

  <div class="d-flex justify-content-between align-items-center mb-3">
    <h1>⚾ KBO 세이버매트릭스 분석</h1>
    <small class="text-muted">koreabaseball.com &nbsp;|&nbsp; 업데이트: {updated}</small>
  </div>

  <!-- 공통 필터 -->
  <div class="filter-bar">
    <div>
      <label class="form-label fw-semibold mb-1">시즌</label>
      <select id="seasonFilter" class="form-select form-select-sm" style="width:100px"></select>
    </div>
    <div>
      <label class="form-label fw-semibold mb-1">팀</label>
      <select id="teamFilter" class="form-select form-select-sm" style="width:130px"></select>
    </div>
    <div id="paFilterWrap">
      <label class="form-label fw-semibold mb-1">
        최소 PA: <span id="paVal">450</span>
        <small class="text-muted">(규정 450)</small>
      </label>
      <input type="range" class="form-range" id="paFilter" min="0" max="700" step="10" value="450" style="width:160px">
    </div>
    <div id="ipFilterWrap" style="display:none">
      <label class="form-label fw-semibold mb-1">
        최소 IP: <span id="ipVal">144</span>
        <small class="text-muted">(규정 144)</small>
      </label>
      <input type="range" class="form-range" id="ipFilter" min="0" max="200" step="1" value="144" style="width:160px">
    </div>
  </div>

  <!-- 탭 -->
  <ul class="nav nav-tabs mb-3" id="mainTab">
    <li class="nav-item"><button class="nav-link active" data-tab="bat">타자 분석</button></li>
    <li class="nav-item"><button class="nav-link" data-tab="pit">투수 분석</button></li>
    <li class="nav-item"><button class="nav-link" data-tab="team">리그 종합</button></li>
  </ul>

  <!-- 타자 탭 -->
  <div id="tab-bat">
    <div class="table-responsive mb-2">
      <table id="batTable" class="table table-sm table-hover table-bordered w-100"></table>
    </div>
    <div class="chart-grid">
      <div class="chart-box"><div id="chart-wrc" style="height:380px"></div></div>
      <div class="chart-box"><div id="chart-obpiso" style="height:380px"></div></div>
    </div>
    <div class="chart-full"><div id="chart-bwar" style="height:420px"></div></div>
  </div>

  <!-- 투수 탭 -->
  <div id="tab-pit" style="display:none">
    <div class="table-responsive mb-2">
      <table id="pitTable" class="table table-sm table-hover table-bordered w-100"></table>
    </div>
    <div class="chart-grid">
      <div class="chart-box"><div id="chart-kbb" style="height:380px"></div></div>
      <div class="chart-box"><div id="chart-erafip" style="height:380px"></div></div>
    </div>
    <div class="chart-full"><div id="chart-pwar" style="height:420px"></div></div>
  </div>

  <!-- 리그 종합 탭 -->
  <div id="tab-team" style="display:none">
    <div class="table-responsive mb-2">
      <table id="teamTable" class="table table-sm table-hover table-bordered w-100"></table>
    </div>
    <div class="chart-grid">
      <div class="chart-box"><div id="chart-twar" style="height:380px"></div></div>
      <div class="chart-box"><div id="chart-tsc" style="height:380px"></div></div>
    </div>
  </div>

</div>

<script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
<script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
<script src="https://cdn.datatables.net/1.13.6/js/dataTables.bootstrap5.min.js"></script>
<script>
const BAT_DATA  = {bat_json};
const PIT_DATA  = {pit_json};
const TEAMS     = {teams_json};
const SEASONS   = {seasons_json};
const TC        = {json.dumps(TEAM_COLORS, ensure_ascii=False)};

// ── 공통 ────────────────────────────────────────────────

function teamBadge(t) {{
  return `<span class="team-badge" style="background:${{TC[t]||'#888'}}">${{t}}</span>`;
}}

function teamColor(t) {{ return TC[t] || '#aaa'; }}

function round2(v) {{ return Math.round(v*100)/100; }}

const PLOTLY_CFG = {{displayModeBar:false, responsive:true}};
const BASE_LAY = {{
  paper_bgcolor:'#fff', plot_bgcolor:'#f8f9fa',
  font:{{family:"'Apple SD Gothic Neo','Noto Sans KR',sans-serif", size:12}},
  hoverlabel:{{bgcolor:'#fff', bordercolor:'#ccc', font:{{size:13}}}},
  margin:{{t:44, r:16, b:60, l:64}},
}};

// ── 드롭다운 ────────────────────────────────────────────

const seasonSel = document.getElementById('seasonFilter');
SEASONS.forEach(s=>{{ const o=document.createElement('option'); o.value=s; o.textContent=s; seasonSel.appendChild(o); }});
const teamSel = document.getElementById('teamFilter');
TEAMS.forEach(t=>{{ const o=document.createElement('option'); o.value=t; o.textContent=t; teamSel.appendChild(o); }});

// ── 탭 ─────────────────────────────────────────────────

document.querySelectorAll('[data-tab]').forEach(btn=>{{
  btn.addEventListener('click', ()=>{{
    document.querySelectorAll('[data-tab]').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    const tab = btn.dataset.tab;
    ['bat','pit','team'].forEach(t=>document.getElementById('tab-'+t).style.display = t===tab?'':'none');
    document.getElementById('paFilterWrap').style.display  = tab==='bat'  ? '' : 'none';
    document.getElementById('ipFilterWrap').style.display  = tab==='pit'  ? '' : 'none';
    // 탭 전환 후 차트 리사이즈
    setTimeout(()=>Plotly.Plots.resize(document.querySelector('#tab-'+tab+' [id^=chart]')), 50);
  }});
}});

// ── 필터 ────────────────────────────────────────────────

function filterData(data, season, team, minPA, minIP) {{
  return data.filter(r=>{{
    if (season!=='전체' && String(r['시즌'])!==String(season)) return false;
    if (team!=='전체'   && r['팀']!==team)                     return false;
    if (minPA>0 && (r['PA']??0)      < minPA) return false;
    if (minIP>0 && (r['IP_float']??0) < minIP) return false;
    return true;
  }});
}}

// ── DataTable ────────────────────────────────────────────

function makeCols(data, hide=[]) {{
  if (!data.length) return [];
  return Object.keys(data[0]).map(k=>{{
    const isNum = typeof data[0][k]==='number';
    return {{
      title: k, data: k,
      visible: !hide.includes(k),
      render: (v,type,row)=>{{
        if (k==='팀'  && type==='display') return teamBadge(v);
        if (v===null || v===undefined)     return type==='display' ? '-' : -9999;
        return v;
      }},
      className: isNum ? 'dt-right' : '',
    }};
  }});
}}

let batDT, pitDT, teamDT;

function initBat(data) {{
  if (batDT) {{ batDT.clear().rows.add(data).draw(); return; }}
  batDT = $('#batTable').DataTable({{
    data, columns: makeCols(BAT_DATA),
    pageLength:25,
    order:[[Object.keys(BAT_DATA[0]).indexOf('wRC+'),'desc']],
    language:{{search:'검색:',lengthMenu:'_MENU_개씩',info:'_TOTAL_명',paginate:{{next:'▶',previous:'◀'}}}},
    scrollX:true,
  }});
}}

function initPit(data) {{
  if (pitDT) {{ pitDT.clear().rows.add(data).draw(); return; }}
  pitDT = $('#pitTable').DataTable({{
    data, columns: makeCols(PIT_DATA, ['IP_float']),
    pageLength:25,
    order:[[Object.keys(PIT_DATA[0]).indexOf('pWAR'),'desc']],
    language:{{search:'검색:',lengthMenu:'_MENU_개씩',info:'_TOTAL_명',paginate:{{next:'▶',previous:'◀'}}}},
    scrollX:true,
  }});
}}

function initTeam(data) {{
  if (teamDT) {{ teamDT.clear().rows.add(data).draw(); return; }}
  if (!data.length) return;
  teamDT = $('#teamTable').DataTable({{
    data, columns: makeCols(data),
    paging:false, searching:false,
    order:[[Object.keys(data[0]).indexOf('총WAR'),'desc']],
    language:{{info:'_TOTAL_개 팀'}},
    scrollX:true,
  }});
}}

// ── 차트 ────────────────────────────────────────────────

function renderBatCharts(data) {{
  if (!data.length) {{
    ['chart-wrc','chart-obpiso','chart-bwar'].forEach(id=>
      Plotly.purge(id));
    return;
  }}

  // wRC+ Top 20
  const top = [...data].filter(r=>r['wRC+']!=null)
                .sort((a,b)=>b['wRC+']-a['wRC+']).slice(0,20);
  Plotly.newPlot('chart-wrc', [{{
    type:'bar', x:top.map(r=>r['선수명']), y:top.map(r=>r['wRC+']),
    marker:{{color:top.map(r=>teamColor(r['팀'])), line:{{color:'#fff',width:1}}}},
    customdata:top.map(r=>[r['팀'],r['PA'],r['AVG']]),
    hovertemplate:'<b>%{{x}}</b><br>wRC+: <b>%{{y}}</b><br>팀: %{{customdata[0]}}<br>PA: %{{customdata[1]}}<extra></extra>',
    text:top.map(r=>r['팀']), textposition:'none',
  }}], {{
    ...BASE_LAY,
    title:{{text:'wRC+ Top 20', font:{{size:14,color:'#212529'}}}},
    xaxis:{{tickangle:-45, tickfont:{{size:11}}}},
    yaxis:{{title:'wRC+', gridcolor:'#e9ecef'}},
    shapes:[{{type:'line',x0:-0.5,x1:top.length-0.5,y0:100,y1:100,
              line:{{color:'#6c757d',dash:'dot',width:1.5}}}}],
    annotations:[{{x:top.length-1,y:100,text:'리그평균 100',
                   showarrow:false,font:{{size:11,color:'#6c757d'}},yanchor:'bottom'}}],
  }}, PLOTLY_CFG);

  // OBP vs ISO
  const valid = data.filter(r=>r['OBP']!=null && r['ISO']!=null);
  Plotly.newPlot('chart-obpiso', [{{
    type:'scatter', mode:'markers',
    x:valid.map(r=>r['OBP']), y:valid.map(r=>r['ISO']),
    marker:{{
      color:valid.map(r=>teamColor(r['팀'])),
      size:valid.map(r=>Math.sqrt((r['PA']||1)/Math.PI)*3.2),
      opacity:0.8, line:{{color:'#fff',width:0.8}},
    }},
    customdata:valid.map(r=>[r['선수명'],r['팀'],r['PA'],r['wRC+']]),
    hovertemplate:'<b>%{{customdata[0]}}</b> (%{{customdata[1]}})<br>OBP: %{{x}}<br>ISO: %{{y}}<br>PA: %{{customdata[2]}} &nbsp; wRC+: %{{customdata[3]}}<extra></extra>',
  }}], {{
    ...BASE_LAY,
    title:{{text:'출루율(OBP) vs 순수장타력(ISO)', font:{{size:14,color:'#212529'}}}},
    xaxis:{{title:'출루율 (OBP)', gridcolor:'#e9ecef'}},
    yaxis:{{title:'순수장타력 (ISO)', gridcolor:'#e9ecef'}},
    margin:{{...BASE_LAY.margin, b:50}},
  }}, PLOTLY_CFG);

  // bWAR Top 15
  const bwar = [...data].filter(r=>r['bWAR']!=null)
                 .sort((a,b)=>a['bWAR']-b['bWAR']).slice(-15);
  Plotly.newPlot('chart-bwar', [{{
    type:'bar', orientation:'h',
    x:bwar.map(r=>r['bWAR']), y:bwar.map(r=>r['선수명']),
    marker:{{color:bwar.map(r=>teamColor(r['팀'])), line:{{color:'#fff',width:1}}}},
    customdata:bwar.map(r=>[r['팀'],r['PA'],r['wRC+']]),
    hovertemplate:'<b>%{{y}}</b> (%{{customdata[0]}})<br>bWAR: <b>%{{x}}</b><br>PA: %{{customdata[1]}} &nbsp; wRC+: %{{customdata[2]}}<extra></extra>',
  }}], {{
    ...BASE_LAY,
    title:{{text:'bWAR Top 15', font:{{size:14,color:'#212529'}}}},
    xaxis:{{title:'bWAR', gridcolor:'#e9ecef', zeroline:true, zerolinecolor:'#adb5bd'}},
    yaxis:{{tickfont:{{size:12}}}},
    height:440, margin:{{t:44,r:24,b:50,l:90}},
  }}, PLOTLY_CFG);
}}

function renderPitCharts(data) {{
  if (!data.length) {{
    ['chart-kbb','chart-erafip','chart-pwar'].forEach(id=>Plotly.purge(id));
    return;
  }}

  // K/9 vs BB/9
  const kbb = data.filter(r=>r['K/9']!=null && r['BB/9']!=null);
  Plotly.newPlot('chart-kbb', [{{
    type:'scatter', mode:'markers',
    x:kbb.map(r=>r['BB/9']), y:kbb.map(r=>r['K/9']),
    marker:{{
      color:kbb.map(r=>teamColor(r['팀'])),
      size:kbb.map(r=>Math.sqrt((r['IP_float']||1)/Math.PI)*4),
      opacity:0.8, line:{{color:'#fff',width:0.8}},
    }},
    customdata:kbb.map(r=>[r['선수명'],r['팀'],r['IP'],r['FIP']]),
    hovertemplate:'<b>%{{customdata[0]}}</b> (%{{customdata[1]}})<br>K/9: %{{y}} &nbsp; BB/9: %{{x}}<br>IP: %{{customdata[2]}} &nbsp; FIP: %{{customdata[3]}}<extra></extra>',
  }}], {{
    ...BASE_LAY,
    title:{{text:'K/9 vs BB/9 (버블=이닝)', font:{{size:14,color:'#212529'}}}},
    xaxis:{{title:'BB/9 (낮을수록 좋음)', gridcolor:'#e9ecef', autorange:'reversed'}},
    yaxis:{{title:'K/9 (높을수록 좋음)', gridcolor:'#e9ecef'}},
    margin:{{...BASE_LAY.margin, b:50}},
  }}, PLOTLY_CFG);

  // ERA vs FIP
  const ef = data.filter(r=>r['ERA']!=null && r['FIP']!=null && r['ERA']<15 && r['FIP']<15);
  const maxV = Math.max(...ef.map(r=>r['ERA']), ...ef.map(r=>r['FIP']), 1) + 0.5;
  Plotly.newPlot('chart-erafip', [{{
    type:'scatter', mode:'markers',
    x:ef.map(r=>r['ERA']), y:ef.map(r=>r['FIP']),
    marker:{{
      color:ef.map(r=>teamColor(r['팀'])),
      size:10, opacity:0.8, line:{{color:'#fff',width:0.8}},
    }},
    customdata:ef.map(r=>[r['선수명'],r['팀'],r['IP'],r['ERA+']]),
    hovertemplate:'<b>%{{customdata[0]}}</b> (%{{customdata[1]}})<br>ERA: %{{x}} &nbsp; FIP: %{{y}}<br>IP: %{{customdata[2]}} &nbsp; ERA+: %{{customdata[3]}}<extra></extra>',
  }}], {{
    ...BASE_LAY,
    title:{{text:'ERA vs FIP', font:{{size:14,color:'#212529'}}}},
    xaxis:{{title:'ERA', gridcolor:'#e9ecef', range:[0,maxV]}},
    yaxis:{{title:'FIP (낮을수록 좋음)', gridcolor:'#e9ecef', range:[0,maxV]}},
    shapes:[{{type:'line',x0:0,y0:0,x1:maxV,y1:maxV,
              line:{{color:'#dc3545',dash:'dash',width:1.5}}}}],
    annotations:[{{x:maxV*0.7,y:maxV*0.7,text:'ERA=FIP',showarrow:false,
                   font:{{size:11,color:'#dc3545'}},textangle:-45}}],
    margin:{{...BASE_LAY.margin, b:50}},
  }}, PLOTLY_CFG);

  // pWAR Top 15
  const pwar = [...data].filter(r=>r['pWAR']!=null)
                  .sort((a,b)=>a['pWAR']-b['pWAR']).slice(-15);
  Plotly.newPlot('chart-pwar', [{{
    type:'bar', orientation:'h',
    x:pwar.map(r=>r['pWAR']), y:pwar.map(r=>r['선수명']),
    marker:{{color:pwar.map(r=>teamColor(r['팀'])), line:{{color:'#fff',width:1}}}},
    customdata:pwar.map(r=>[r['팀'],r['IP'],r['FIP']]),
    hovertemplate:'<b>%{{y}}</b> (%{{customdata[0]}})<br>pWAR: <b>%{{x}}</b><br>IP: %{{customdata[1]}} &nbsp; FIP: %{{customdata[2]}}<extra></extra>',
  }}], {{
    ...BASE_LAY,
    title:{{text:'pWAR Top 15', font:{{size:14,color:'#212529'}}}},
    xaxis:{{title:'pWAR', gridcolor:'#e9ecef', zeroline:true, zerolinecolor:'#adb5bd'}},
    yaxis:{{tickfont:{{size:12}}}},
    height:440, margin:{{t:44,r:24,b:50,l:90}},
  }}, PLOTLY_CFG);
}}

function renderTeamCharts(batData, pitData) {{
  // 팀별 집계
  const teams = {{}};
  batData.filter(r=>r['PA']>=100).forEach(r=>{{
    if (!teams[r['팀']]) teams[r['팀']] = {{팀:r['팀'],bWAR:[],wRC:[],pWAR:[],FIP:[]}};
    if (r['bWAR']!=null) teams[r['팀']].bWAR.push(r['bWAR']);
    if (r['wRC+']!=null) teams[r['팀']].wRC.push(r['wRC+']);
  }});
  pitData.filter(r=>(r['IP_float']||0)>=20).forEach(r=>{{
    if (!teams[r['팀']]) teams[r['팀']] = {{팀:r['팀'],bWAR:[],wRC:[],pWAR:[],FIP:[]}};
    if (r['pWAR']!=null) teams[r['팀']].pWAR.push(r['pWAR']);
    if (r['FIP']!=null)  teams[r['팀']].FIP.push(r['FIP']);
  }});
  const avg = arr => arr.length ? round2(arr.reduce((a,b)=>a+b)/arr.length) : null;
  const sum = arr => round2(arr.reduce((a,b)=>a+b, 0));
  const td = Object.values(teams).map(t=>{{
    const bw=sum(t.bWAR), pw=sum(t.pWAR);
    return {{팀:t.팀, 타자WAR:bw, 투수WAR:pw, 총WAR:round2(bw+pw),
             평균wRC:avg(t.wRC), 평균FIP:avg(t.FIP)}};
  }}).sort((a,b)=>b.총WAR-a.총WAR);

  if (!td.length) return;

  initTeam(td);

  const sorted = [...td].sort((a,b)=>a.총WAR-b.총WAR);
  Plotly.newPlot('chart-twar', [{{
    type:'bar', orientation:'h',
    x:sorted.map(r=>r.총WAR), y:sorted.map(r=>r.팀),
    marker:{{color:sorted.map(r=>teamColor(r.팀)), line:{{color:'#fff',width:1}}}},
    customdata:sorted.map(r=>[r.타자WAR,r.투수WAR]),
    hovertemplate:'<b>%{{y}}</b><br>총WAR: <b>%{{x}}</b><br>타자: %{{customdata[0]}} &nbsp; 투수: %{{customdata[1]}}<extra></extra>',
  }}], {{
    ...BASE_LAY,
    title:{{text:'팀별 총 WAR', font:{{size:14,color:'#212529'}}}},
    xaxis:{{title:'총 WAR', gridcolor:'#e9ecef'}},
    yaxis:{{tickfont:{{size:13}}}},
    margin:{{t:44,r:24,b:50,l:72}},
  }}, PLOTLY_CFG);

  Plotly.newPlot('chart-tsc', [{{
    type:'scatter', mode:'markers+text',
    x:td.map(r=>r.평균FIP), y:td.map(r=>r.평균wRC),
    text:td.map(r=>r.팀),
    textposition:'top center',
    textfont:{{size:12, color:td.map(r=>teamColor(r.팀))}},
    marker:{{
      color:td.map(r=>teamColor(r.팀)),
      size:td.map(r=>Math.max(14, Math.sqrt(Math.abs(r.총WAR||1))*8)),
      opacity:0.85, line:{{color:'#fff',width:1.5}},
    }},
    customdata:td.map(r=>[r.총WAR]),
    hovertemplate:'<b>%{{text}}</b><br>평균FIP: %{{x}} &nbsp; 평균wRC+: %{{y}}<br>총WAR: %{{customdata[0]}}<extra></extra>',
  }}], {{
    ...BASE_LAY,
    title:{{text:'팀 평균 FIP vs 평균 wRC+', font:{{size:14,color:'#212529'}}}},
    xaxis:{{title:'평균 FIP (낮을수록 좋음)', gridcolor:'#e9ecef', autorange:'reversed'}},
    yaxis:{{title:'평균 wRC+', gridcolor:'#e9ecef'}},
    margin:{{t:44,r:24,b:50,l:72}},
  }}, PLOTLY_CFG);
}}

// ── applyFilters ─────────────────────────────────────────

function applyFilters() {{
  const season = seasonSel.value;
  const team   = teamSel.value;
  const minPA  = parseInt(document.getElementById('paFilter').value);
  const minIP  = parseInt(document.getElementById('ipFilter').value);

  const bd = filterData(BAT_DATA, season, team, minPA, 0);
  const pd = filterData(PIT_DATA, season, team, 0, minIP);

  initBat(bd);
  initPit(pd);
  renderBatCharts(bd);
  renderPitCharts(pd);
  renderTeamCharts(bd, pd);
}}

// 시즌 변경 시 PA/IP 기본값 조정
seasonSel.addEventListener('change', ()=>{{
  const s = seasonSel.value;
  const pa = document.getElementById('paFilter');
  const ip = document.getElementById('ipFilter');
  if (s==='2026') {{
    pa.value=0; document.getElementById('paVal').textContent=0;
    ip.value=0; document.getElementById('ipVal').textContent=0;
  }} else if (s!=='전체') {{
    pa.value=450; document.getElementById('paVal').textContent=450;
    ip.value=144; document.getElementById('ipVal').textContent=144;
  }}
  applyFilters();
}});
teamSel.addEventListener('change', applyFilters);
document.getElementById('paFilter').addEventListener('input', function(){{
  document.getElementById('paVal').textContent=this.value; applyFilters();
}});
document.getElementById('ipFilter').addEventListener('input', function(){{
  document.getElementById('ipVal').textContent=this.value; applyFilters();
}});

// 최초 렌더
applyFilters();
</script>
<script>
if ('serviceWorker' in navigator) {{
  window.addEventListener('load', ()=>navigator.serviceWorker.register('./sw.js'));
}}
</script>
</body>
</html>
"""

out_dir = Path("docs")
out_dir.mkdir(exist_ok=True)
out_file = out_dir / "index.html"
out_file.write_text(html, encoding="utf-8")
print(f"생성 완료: {out_file}  ({out_file.stat().st_size // 1024} KB)")
