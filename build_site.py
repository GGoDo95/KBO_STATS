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

BAT_COLS = ["시즌", "선수명", "팀", "G", "PA", "AVG", "HR", "RBI", "R",
            "BB", "SO", "OBP", "SLG", "OPS",
            "BABIP", "ISO", "wOBA", "wRC+", "OPS+", "bWAR",
            "BB%", "K%", "BB/K", "wRAA"]
PIT_COLS = ["시즌", "선수명", "팀", "G", "W", "L", "SV", "HLD",
            "IP", "IP_float", "ERA", "WHIP", "SO", "BB", "HR",
            "FIP", "xFIP", "ERA+", "K/9", "BB/9", "K/BB", "pWAR",
            "LOB%", "ERA-", "FIP-", "kwERA"]

BAT_SABER = ["BABIP", "ISO", "wOBA", "wRC+", "OPS+", "bWAR", "BB%", "K%", "BB/K", "wRAA"]
PIT_SABER = ["FIP", "xFIP", "ERA+", "K/9", "BB/9", "K/BB", "pWAR", "LOB%", "ERA-", "FIP-", "kwERA"]

bat_cols = [c for c in BAT_COLS if c in bat.columns]
pit_cols = [c for c in PIT_COLS if c in pit.columns]

bat_json     = bat[bat_cols].round(3).to_json(orient="records", force_ascii=False)
pit_json     = pit[pit_cols].round(3).to_json(orient="records", force_ascii=False)
teams_json   = json.dumps(["전체"] + TEAMS, ensure_ascii=False)
seasons_json = json.dumps(["전체"] + AVAILABLE_SEASONS, ensure_ascii=False)

# ── 선수 프로필 ────────────────────────────────────────────
try:
    from database import db as _db
    _profiles = _db.load_profiles()  # {선수명: {fields...}}
except Exception:
    _profiles = {}

# 나무위키 등장곡/응원가 병합
_music_path = data_dir / "namu_music.json"
if _music_path.exists():
    import json as _json
    _music = _json.loads(_music_path.read_text(encoding="utf-8"))
    for name, mdata in _music.items():
        if name not in _profiles:
            continue  # 스탯 데이터 없는 선수는 스킵
        for field in ("등장곡", "응원가"):
            if mdata.get(field):
                _profiles[name][field] = mdata[field]

profiles_json = json.dumps(_profiles, ensure_ascii=False)

# ── HTML ─────────────────────────────────────────────────

html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>KBO STATS</title>

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
          background:#f8f9fa;
          padding-top:env(safe-area-inset-top,0px);
          padding-bottom:env(safe-area-inset-bottom,0px); }}
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
  .player-link {{ color:#003580; cursor:pointer; font-weight:600; text-decoration:underline dotted; }}
  .player-link:hover {{ color:#0056d6; }}
  /* 선수 상세 페이지 */
  #playerPage {{
    animation:pageIn .2s ease;
  }}
  @keyframes pageIn {{ from{{opacity:0;transform:translateY(12px)}} to{{opacity:1;transform:translateY(0)}} }}
  .page-back-bar {{
    position:sticky; top:0; z-index:100;
    background:#fff; border-bottom:1px solid #e9ecef;
    padding:10px 16px;
    display:flex; align-items:center;
    margin:-12px -16px 16px -16px;  /* container padding 상쇄 */
  }}
  .page-back {{
    display:inline-flex; align-items:center; gap:8px;
    background:none; border:none; color:#003580;
    font-size:1rem; font-weight:600; cursor:pointer; padding:4px 0;
    -webkit-tap-highlight-color:transparent;
  }}
  .page-back:active {{ opacity:.6; }}
  .page-back-title {{
    font-size:1rem; font-weight:700; color:#212529; margin-left:4px;
  }}
  .player-card {{
    background:#fff; border-radius:12px; overflow:hidden;
    box-shadow:0 2px 12px rgba(0,0,0,.08); margin-bottom:20px;
  }}
  .player-card-hero {{
    display:flex; gap:20px; padding:24px;
    background:linear-gradient(135deg, #003580 0%, #0056d6 100%);
    color:#fff; align-items:flex-end;
  }}
  .player-hero-photo {{
    width:100px; height:120px; object-fit:cover; border-radius:8px;
    border:3px solid rgba(255,255,255,.3); flex-shrink:0;
    background:#1a4a9a;
  }}
  .player-hero-info {{ flex:1; }}
  .player-hero-number {{ font-size:0.85rem; opacity:.7; margin-bottom:2px; }}
  .player-hero-name {{ font-size:1.8rem; font-weight:800; line-height:1.1; margin-bottom:6px; }}
  .player-hero-sub {{ font-size:0.9rem; opacity:.85; }}
  .player-card-body {{ padding:20px 24px; }}
  .info-grid {{
    display:grid; grid-template-columns:repeat(3,1fr); gap:16px 24px;
  }}
  .info-item {{ display:flex; flex-direction:column; gap:3px; }}
  .info-label {{ font-size:0.72rem; color:#888; font-weight:700; text-transform:uppercase; letter-spacing:.06em; }}
  .info-value {{ font-size:1rem; font-weight:700; color:#212529; }}
  .info-item.span2 {{ grid-column:span 2; }}
  .info-item.span3 {{ grid-column:span 3; }}
  .stats-section {{ background:#fff; border-radius:12px; padding:20px 24px; box-shadow:0 2px 12px rgba(0,0,0,.08); }}
  .stats-section h6 {{ font-weight:700; color:#003580; margin-bottom:14px; font-size:0.9rem; text-transform:uppercase; letter-spacing:.05em; }}
  .stats-grid {{
    display:grid; grid-template-columns:repeat(auto-fill,minmax(90px,1fr)); gap:12px;
  }}
  .stat-box {{
    text-align:center; background:#f8f9fa; border-radius:8px; padding:10px 6px;
  }}
  .stat-box-val {{ font-size:1.2rem; font-weight:800; color:#003580; }}
  .stat-box-lbl {{ font-size:0.68rem; color:#888; font-weight:600; margin-top:2px; }}
  .music-item {{
    display:flex; flex-direction:column; gap:4px; padding:12px 0;
    border-bottom:1px solid #f0f0f0;
  }}
  .music-item:last-child {{ border-bottom:none; }}
  .music-label {{ font-size:0.72rem; color:#888; font-weight:700; text-transform:uppercase; letter-spacing:.06em; }}
  .music-value {{ font-size:0.95rem; font-weight:600; color:#212529; line-height:1.4; }}
  @media (max-width:600px) {{
    .info-grid {{ grid-template-columns:repeat(2,1fr); }}
    .info-item.span2 {{ grid-column:span 2; }}
    .info-item.span3 {{ grid-column:span 2; }}
    .player-hero-name {{ font-size:1.4rem; }}
    .player-hero-photo {{ width:72px; height:88px; }}
  }}
  /* 퍼센타일 바 */
  .pct-bar-wrap  {{ margin:6px 0; display:flex; align-items:center; gap:8px; }}
  .pct-bar-label {{ font-size:0.72rem; color:#888; font-weight:700; width:52px; flex-shrink:0; text-align:right; }}
  .pct-bar-track {{ flex:1; height:8px; background:#e9ecef; border-radius:4px; position:relative; }}
  .pct-bar-fill  {{ height:100%; border-radius:4px; transition:width .4s; }}
  .pct-bar-val   {{ font-size:0.75rem; color:#555; width:36px; text-align:right; flex-shrink:0; }}
  .pct-bar-mid   {{ position:absolute; top:-3px; left:50%; width:2px; height:14px;
                    background:#adb5bd; border-radius:1px; transform:translateX(-50%); }}
</style>
</head>
<body>
<div class="container-fluid py-3 px-4">

<!-- 선수 상세 페이지 -->
<div id="playerPage" style="display:none">
  <div class="page-back-bar">
    <button class="page-back" onclick="closePage()">&#8592;</button>
    <span class="page-back-title">선수 정보</span>
  </div>
  <div class="player-card">
    <div class="player-card-hero">
      <img id="pagePhoto" class="player-hero-photo" src="" alt="" onerror="this.style.display='none'">
      <div class="player-hero-info">
        <div id="pageNumber" class="player-hero-number"></div>
        <div id="pageName" class="player-hero-name"></div>
        <div id="pagePos" class="player-hero-sub"></div>
      </div>
    </div>
    <div class="player-card-body">
      <div id="pageInfoGrid" class="info-grid"></div>
    </div>
  </div>
  <div id="pageMusicSection" class="stats-section">
    <div id="pageMusic"></div>
  </div>
  <div class="stats-section">
    <h6>시즌 기록</h6>
    <div id="pageStats" class="stats-grid"></div>
  </div>
  <div id="pagePctSection" class="stats-section" style="margin-top:16px">
    <h6>퍼센타일 (리그 내 순위)</h6>
    <div id="pagePctBars"></div>
  </div>
</div>

<!-- 메인 콘텐츠 -->
<div id="mainContent">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <h1>⚾ KBO STATS</h1>
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
    <div class="d-flex align-items-center gap-2 mb-2">
      <button id="batSaberBtn" class="btn btn-sm btn-outline-primary" onclick="toggleBatSaber()">
        세이버 지표 보기 ▼
      </button>
      <small class="text-muted">기본: 클래식 스탯 | 버튼 클릭 시 BABIP·wOBA·wRC+·bWAR 등 추가</small>
    </div>
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
    <div class="d-flex align-items-center gap-2 mb-2">
      <button id="pitSaberBtn" class="btn btn-sm btn-outline-primary" onclick="togglePitSaber()">
        세이버 지표 보기 ▼
      </button>
      <small class="text-muted">기본: 클래식 스탯 | 버튼 클릭 시 FIP·xFIP·ERA+·K/9 등 추가</small>
    </div>
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

</div><!-- /mainContent -->
</div><!-- /container-fluid -->

<script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
<script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
<script src="https://cdn.datatables.net/1.13.6/js/dataTables.bootstrap5.min.js"></script>
<script>
const BAT_DATA  = {bat_json};
const PIT_DATA  = {pit_json};
const TEAMS     = {teams_json};
const SEASONS   = {seasons_json};
const TC        = {json.dumps(TEAM_COLORS, ensure_ascii=False)};
const BAT_SABER = {json.dumps(BAT_SABER, ensure_ascii=False)};
const PIT_SABER = {json.dumps(PIT_SABER, ensure_ascii=False)};
const PROFILES  = {profiles_json};

// ── 퍼센타일 유틸 ────────────────────────────────────────

function calcPct(val, allVals, higherIsBetter) {{
  if (val == null) return 50;
  const sorted = allVals.filter(v => v != null && isFinite(v)).sort((a,b)=>a-b);
  if (!sorted.length) return 50;
  const rank = sorted.filter(v => v <= val).length;
  const pct = Math.round(rank / sorted.length * 100);
  return higherIsBetter ? pct : 100 - pct;
}}

function pctColor(p) {{
  if (p >= 80) return '#1a6bc4';
  if (p >= 60) return '#5baee8';
  if (p >= 40) return '#adb5bd';
  if (p >= 20) return '#f9a8a8';
  return '#dc3545';
}}

// ── 공통 ────────────────────────────────────────────────

function teamBadge(t) {{
  return `<span class="team-badge" style="background:${{TC[t]||'#888'}}">${{t}}</span>`;
}}

function teamColor(t) {{ return TC[t] || '#aaa'; }}

function round2(v) {{ return Math.round(v*100)/100; }}

// ── 선수 상세 페이지 ────────────────────────────────────

function playerLink(name) {{
  // data-name 속성 사용 → 따옴표 충돌 방지
  return `<span class="player-link" data-name="${{name.replace(/"/g,'&quot;')}}" onclick="openPage(this.dataset.name)">${{name}}</span>`;
}}

// popstate → 물리 뒤로가기 / 스와이프 / 브라우저 뒤로가기 처리
let _playerPageOpen = false;

window.addEventListener('popstate', ()=>{{
  if (_playerPageOpen) _doClosePage();
}});

function openPage(name) {{
  const p = PROFILES[name];

  // 사진
  const photo = document.getElementById('pagePhoto');
  if (p && p['사진']) {{
    photo.src = p['사진'];
    photo.style.display = '';
  }} else {{
    photo.style.display = 'none';
  }}

  document.getElementById('pageName').textContent = name;
  document.getElementById('pageNumber').textContent = p ? (p['등번호'] || '') : '';
  document.getElementById('pagePos').innerHTML = p
    ? [p['포지션']||'', p['신장/체중']||''].filter(Boolean).join(' &nbsp;|&nbsp; ')
    : '';

  // 상세 정보 그리드
  const INFO_FIELDS = [
    {{'key':'생년월일',    'label':'생년월일',   'span':1}},
    {{'key':'연봉',        'label':'연봉',        'span':1}},
    {{'key':'입단 계약금', 'label':'계약금',      'span':1}},
    {{'key':'입단년도',    'label':'입단년도',    'span':1}},
    {{'key':'지명순위',    'label':'지명순위',    'span':2}},
    {{'key':'경력',        'label':'경력',        'span':3}},
  ];
  const grid = document.getElementById('pageInfoGrid');
  if (p) {{
    grid.innerHTML = INFO_FIELDS.map(f => {{
      const val = p[f.key]; if (!val) return '';
      const cls = f.span===3?'span3':f.span===2?'span2':'';
      return `<div class="info-item ${{cls}}">
        <span class="info-label">${{f.label}}</span>
        <span class="info-value">${{val}}</span>
      </div>`;
    }}).join('');
  }} else {{
    grid.innerHTML = '<p class="text-muted small">프로필 정보가 없습니다.</p>';
  }}

  // 등장곡 / 응원가 (항상 표시)
  const musicEl = document.getElementById('pageMusic');
  const musicFields = [['등장곡','등장곡'], ['응원가','응원가']];
  musicEl.innerHTML = musicFields.map(([k,lbl])=>`<div class="music-item">
      <span class="music-label">${{lbl}}</span>
      <span class="music-value">${{(p && p[k]) || '-'}}</span>
    </div>`).join('');

  // 시즌 스탯
  const allStats = [...BAT_DATA, ...PIT_DATA].filter(r=>r['선수명']===name);
  const BAT_SHOW = ['시즌','팀','AVG','HR','RBI','OBP','SLG','OPS','wRC+','bWAR'];
  const PIT_SHOW = ['시즌','팀','ERA','W','L','SV','IP','WHIP','FIP','pWAR'];
  const isBat = allStats.length && allStats[0]['PA'] != null;
  const SHOW  = isBat ? BAT_SHOW : PIT_SHOW;
  const latest = allStats.sort((a,b)=>b['시즌']-a['시즌'])[0];
  const statsEl = document.getElementById('pageStats');
  if (latest) {{
    statsEl.innerHTML = SHOW.filter(k=>latest[k]!=null).map(k=>
      `<div class="stat-box">
        <div class="stat-box-val">${{latest[k]}}</div>
        <div class="stat-box-lbl">${{k}}</div>
      </div>`
    ).join('');
  }} else {{
    statsEl.innerHTML = '<p class="text-muted small">스탯 데이터 없음</p>';
  }}

  // 퍼센타일 바
  const pctEl = document.getElementById('pagePctBars');
  const pctSection = document.getElementById('pagePctSection');
  if (latest) {{
    const latestSeason = latest['시즌'];
    const pool = (isBat ? BAT_DATA : PIT_DATA).filter(r =>
      r['시즌'] === latestSeason &&
      (isBat ? (r['PA'] || 0) >= 20 : (r['IP_float'] || 0) >= 5)
    );
    const BAT_PCT_METRICS = [
      {{'key':'wRC+',  'label':'wRC+',  'hib':true}},
      {{'key':'BABIP', 'label':'BABIP', 'hib':true}},
      {{'key':'ISO',   'label':'ISO',   'hib':true}},
      {{'key':'BB%',   'label':'BB%',   'hib':true}},
      {{'key':'K%',    'label':'K%',    'hib':false}},
      {{'key':'bWAR',  'label':'bWAR',  'hib':true}},
    ];
    const PIT_PCT_METRICS = [
      {{'key':'FIP',   'label':'FIP',   'hib':false}},
      {{'key':'ERA',   'label':'ERA',   'hib':false}},
      {{'key':'K/9',   'label':'K/9',   'hib':true}},
      {{'key':'BB/9',  'label':'BB/9',  'hib':false}},
      {{'key':'pWAR',  'label':'pWAR',  'hib':true}},
    ];
    const metrics = isBat ? BAT_PCT_METRICS : PIT_PCT_METRICS;
    pctEl.innerHTML = metrics.map(m => {{
      const val = latest[m.key];
      if (val == null) return '';
      const allVals = pool.map(r => r[m.key]);
      const pct = calcPct(val, allVals, m.hib);
      const color = pctColor(pct);
      return `<div class="pct-bar-wrap">
        <span class="pct-bar-label">${{m.label}}</span>
        <div class="pct-bar-track">
          <div class="pct-bar-fill" style="width:${{pct}}%;background:${{color}}"></div>
          <div class="pct-bar-mid"></div>
        </div>
        <span class="pct-bar-val">${{pct}}%</span>
      </div>`;
    }}).join('');
    pctSection.style.display = '';
  }} else {{
    pctSection.style.display = 'none';
  }}

  document.getElementById('playerPage').style.display = 'block';
  document.getElementById('mainContent').style.display = 'none';
  localStorage.setItem('kbo_player', name);
  _playerPageOpen = true;
  history.pushState({{player: name}}, '');
  window.scrollTo(0,0);
}}

function _doClosePage() {{
  _playerPageOpen = false;
  document.getElementById('playerPage').style.display = 'none';
  document.getElementById('mainContent').style.display = 'block';
  localStorage.removeItem('kbo_player');
}}

function closePage() {{
  // 버튼에서 호출 → history.back() → popstate → _doClosePage()
  history.back();
}}

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
seasonSel.value = SEASONS[SEASONS.length-1];  // 최신 연도 기본 선택
const teamSel = document.getElementById('teamFilter');
TEAMS.forEach(t=>{{ const o=document.createElement('option'); o.value=t; o.textContent=t; teamSel.appendChild(o); }});

// ── 탭 ─────────────────────────────────────────────────

function showTab(tab) {{
  document.querySelectorAll('[data-tab]').forEach(b=>b.classList.remove('active'));
  const btn = document.querySelector('[data-tab="'+tab+'"]');
  if (btn) btn.classList.add('active');
  ['bat','pit','team'].forEach(t=>document.getElementById('tab-'+t).style.display = t===tab?'':'none');
  document.getElementById('paFilterWrap').style.display = tab==='bat' ? '' : 'none';
  document.getElementById('ipFilterWrap').style.display = tab==='pit' ? '' : 'none';
  localStorage.setItem('kbo_tab', tab);
  setTimeout(()=>{{
    if (tab==='bat'  && batDT)  batDT.columns.adjust().draw(false);
    if (tab==='pit'  && pitDT)  pitDT.columns.adjust().draw(false);
    if (tab==='team') {{
      renderTeamCharts(_lastBat, _lastPit);
      setTimeout(()=>{{
        Plotly.Plots.resize(document.getElementById('chart-twar'));
        Plotly.Plots.resize(document.getElementById('chart-tsc'));
      }}, 150);
      if (teamDT) teamDT.columns.adjust().draw(false);
    }}
    document.querySelectorAll('#tab-'+tab+' [id^=chart]').forEach(el=>Plotly.Plots.resize(el));
  }}, 100);
}}

document.querySelectorAll('[data-tab]').forEach(btn=>{{
  btn.addEventListener('click', ()=>showTab(btn.dataset.tab));
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
        if (type!=='display') {{
          if (v===null || v===undefined) return isNum ? -9999 : '';
          return v;
        }}
        if (k==='선수명') return playerLink(v);
        if (k==='팀')     return teamBadge(v);
        if (v===null || v===undefined) return '-';
        return v;
      }},
      className: isNum ? 'dt-right' : '',
    }};
  }});
}}

let batDT, pitDT, teamDT;

const BAT_KEYS = () => Object.keys(BAT_DATA[0]);
const PIT_KEYS = () => Object.keys(PIT_DATA[0]);

function initBat(data) {{
  if (batDT) {{ batDT.clear().rows.add(data).columns.adjust().draw(false); return; }}
  const hideCols = ['IP_float', ...BAT_SABER];
  batDT = $('#batTable').DataTable({{
    data, columns: makeCols(BAT_DATA, hideCols),
    pageLength:25,
    order:[[BAT_KEYS().indexOf('AVG'),'desc']],
    language:{{search:'검색:',lengthMenu:'_MENU_개씩',info:'_TOTAL_명',paginate:{{next:'▶',previous:'◀'}}}},
    scrollX:true,
  }});
}}

function initPit(data) {{
  if (pitDT) {{ pitDT.clear().rows.add(data).columns.adjust().draw(false); return; }}
  const hideCols = ['IP_float', ...PIT_SABER];
  pitDT = $('#pitTable').DataTable({{
    data, columns: makeCols(PIT_DATA, hideCols),
    pageLength:25,
    order:[[PIT_KEYS().indexOf('ERA'),'asc']],
    language:{{search:'검색:',lengthMenu:'_MENU_개씩',info:'_TOTAL_명',paginate:{{next:'▶',previous:'◀'}}}},
    scrollX:true,
  }});
}}

// ── 세이버 토글 ──────────────────────────────────────────

let batSaberOn = false;
let pitSaberOn = false;

function toggleBatSaber() {{
  batSaberOn = !batSaberOn;
  const keys = BAT_KEYS();
  BAT_SABER.forEach(col=>{{
    const idx = keys.indexOf(col);
    if (idx>=0 && batDT) batDT.column(idx).visible(batSaberOn);
  }});
  if (batDT) batDT.columns.adjust().draw(false);
  const btn = document.getElementById('batSaberBtn');
  btn.textContent = batSaberOn ? '세이버 지표 숨기기 ▲' : '세이버 지표 보기 ▼';
  btn.className = batSaberOn ? 'btn btn-sm btn-primary' : 'btn btn-sm btn-outline-primary';
}}

function togglePitSaber() {{
  pitSaberOn = !pitSaberOn;
  const keys = PIT_KEYS();
  PIT_SABER.forEach(col=>{{
    const idx = keys.indexOf(col);
    if (idx>=0 && pitDT) pitDT.column(idx).visible(pitSaberOn);
  }});
  if (pitDT) pitDT.columns.adjust().draw(false);
  const btn = document.getElementById('pitSaberBtn');
  btn.textContent = pitSaberOn ? '세이버 지표 숨기기 ▲' : '세이버 지표 보기 ▼';
  btn.className = pitSaberOn ? 'btn btn-sm btn-primary' : 'btn btn-sm btn-outline-primary';
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

  // wRC+ vs bWAR 버블
  const vld = data.filter(r=>r['wRC+']!=null && r['bWAR']!=null);
  Plotly.newPlot('chart-bwar', [{{
    type:'scatter', mode:'markers',
    x:vld.map(r=>r['bWAR']), y:vld.map(r=>r['wRC+']),
    marker:{{
      color:vld.map(r=>teamColor(r['팀'])),
      size:vld.map(r=>Math.sqrt((r['PA']||1)/Math.PI)*3.2),
      opacity:0.82, line:{{color:'#fff',width:0.8}},
    }},
    customdata:vld.map(r=>[r['선수명'],r['팀'],r['PA'],r['AVG']]),
    hovertemplate:'<b>%{{customdata[0]}}</b> (%{{customdata[1]}})<br>bWAR: %{{x}} &nbsp; wRC+: %{{y}}<br>PA: %{{customdata[2]}} &nbsp; AVG: %{{customdata[3]}}<extra></extra>',
  }}], {{
    ...BASE_LAY,
    title:{{text:'공격 가치(wRC+) vs 종합 가치(bWAR)  —  버블 크기=PA', font:{{size:13,color:'#212529'}}}},
    xaxis:{{title:'bWAR (종합 가치)', gridcolor:'#e9ecef', zeroline:true, zerolinecolor:'#adb5bd'}},
    yaxis:{{title:'wRC+ (공격 가치)', gridcolor:'#e9ecef'}},
    shapes:[{{type:'line',x0:0,y0:100,x1:0,y1:100,line:{{color:'#6c757d',dash:'dot',width:1.5}}}}],
    annotations:[{{x:vld.reduce((m,r)=>Math.max(m,r['bWAR']||0),0)*0.05,y:100,
                   text:'wRC+ 100 (리그평균)',showarrow:false,
                   font:{{size:10,color:'#6c757d'}},xanchor:'left'}}],
    height:440, margin:{{t:52,r:24,b:54,l:72}},
  }}, PLOTLY_CFG);
}}

function renderPitCharts(data) {{
  if (!data.length) {{
    ['chart-kbb','chart-erafip','chart-pwar'].forEach(id=>Plotly.purge(id));
    return;
  }}

  // FIP vs xFIP (홈런 운 분석)
  const fx = data.filter(r=>r['FIP']!=null && r['xFIP']!=null && r['FIP']<12 && r['xFIP']<12);
  const fMax = Math.max(...fx.map(r=>Math.max(r['FIP'],r['xFIP'])), 1) + 0.3;
  const fMin = Math.max(0, Math.min(...fx.map(r=>Math.min(r['FIP'],r['xFIP']))) - 0.3);
  Plotly.newPlot('chart-kbb', [{{
    type:'scatter', mode:'markers',
    x:fx.map(r=>r['FIP']), y:fx.map(r=>r['xFIP']),
    marker:{{
      color:fx.map(r=>teamColor(r['팀'])),
      size:fx.map(r=>Math.sqrt((r['IP_float']||1)/Math.PI)*4),
      opacity:0.82, line:{{color:'#fff',width:0.8}},
    }},
    customdata:fx.map(r=>[r['선수명'],r['팀'],r['IP'],r['ERA']]),
    hovertemplate:'<b>%{{customdata[0]}}</b> (%{{customdata[1]}})<br>FIP: %{{x}} &nbsp; xFIP: %{{y}}<br>IP: %{{customdata[2]}} &nbsp; ERA: %{{customdata[3]}}<extra></extra>',
  }}], {{
    ...BASE_LAY,
    title:{{text:'FIP vs xFIP  —  홈런 운 분석  (버블=이닝)', font:{{size:13,color:'#212529'}}}},
    xaxis:{{title:'FIP', gridcolor:'#e9ecef', range:[fMin,fMax]}},
    yaxis:{{title:'xFIP', gridcolor:'#e9ecef', range:[fMin,fMax]}},
    shapes:[{{type:'line',x0:fMin,y0:fMin,x1:fMax,y1:fMax,
              line:{{color:'#6c757d',dash:'dot',width:1.5}}}}],
    annotations:[
      {{x:fMin+(fMax-fMin)*0.72, y:fMin+(fMax-fMin)*0.58,
        text:'FIP<xFIP: 홈런 운 좋음',showarrow:false,font:{{size:10,color:'#198754'}}}},
      {{x:fMin+(fMax-fMin)*0.28, y:fMin+(fMax-fMin)*0.42,
        text:'FIP>xFIP: 홈런 운 나쁨',showarrow:false,font:{{size:10,color:'#dc3545'}}}},
    ],
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

let _lastBat = [], _lastPit = [];

function applyFilters() {{
  const season = seasonSel.value;
  const team   = teamSel.value;
  const minPA  = parseInt(document.getElementById('paFilter').value);
  const minIP  = parseInt(document.getElementById('ipFilter').value);

  const bd = filterData(BAT_DATA, season, team, minPA, 0);
  const pd = filterData(PIT_DATA, season, team, 0, minIP);
  _lastBat = bd; _lastPit = pd;

  initBat(bd);
  initPit(pd);
  renderBatCharts(bd);
  renderPitCharts(pd);
  renderTeamCharts(bd, pd);
}}

// 시즌 변경 시 PA/IP 기본값 조정 + localStorage 저장
seasonSel.addEventListener('change', ()=>{{
  const s = seasonSel.value;
  localStorage.setItem('kbo_season', s);
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
teamSel.addEventListener('change', ()=>{{
  localStorage.setItem('kbo_team', teamSel.value);
  applyFilters();
}});
document.getElementById('paFilter').addEventListener('input', function(){{
  document.getElementById('paVal').textContent=this.value; applyFilters();
}});
document.getElementById('ipFilter').addEventListener('input', function(){{
  document.getElementById('ipVal').textContent=this.value; applyFilters();
}});

// 최초 렌더 — localStorage 시즌/팀 복원 + PA/IP 초기값 조정
(()=>{{
  const savedSeason = localStorage.getItem('kbo_season');
  const savedTeam   = localStorage.getItem('kbo_team');
  if (savedSeason && SEASONS.includes(savedSeason)) seasonSel.value = savedSeason;
  if (savedTeam   && TEAMS.includes(savedTeam))     teamSel.value   = savedTeam;

  const s = seasonSel.value;
  const pa = document.getElementById('paFilter');
  const ip = document.getElementById('ipFilter');
  if (s==='2026') {{
    pa.value=0; document.getElementById('paVal').textContent=0;
    ip.value=0; document.getElementById('ipVal').textContent=0;
  }}
}})();
applyFilters();

// 마지막 탭 + 선수 페이지 복원
(()=>{{
  const savedPlayer = localStorage.getItem('kbo_player');
  if (savedPlayer && PROFILES[savedPlayer]) {{
    openPage(savedPlayer);
    return;
  }} else {{
    localStorage.removeItem('kbo_player');
  }}
  const savedTab = localStorage.getItem('kbo_tab');
  if (savedTab && ['bat','pit','team'].includes(savedTab)) showTab(savedTab);
}})();
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
