"""
정적 HTML 사이트 생성기.
CSV 데이터 → docs/index.html (GitHub Pages 배포용)

실행: python build_site.py
"""

import json
import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.io as pio

# ── 데이터 로드 ───────────────────────────────────────────

data_dir = Path("data")
bat_files = sorted(data_dir.glob("*전체*batting.csv"))
pit_files = sorted(data_dir.glob("*전체*pitching.csv"))

if not bat_files or not pit_files:
    raise FileNotFoundError("data/ 아래 전체 CSV 없음. python main.py 먼저 실행하세요.")

bat = pd.read_csv(bat_files[-1])
pit = pd.read_csv(pit_files[-1])

updated = datetime.datetime.fromtimestamp(bat_files[-1].stat().st_mtime).strftime("%Y-%m-%d")

TEAMS = sorted(bat["팀"].dropna().unique().tolist())

# ── 팀 색상 ───────────────────────────────────────────────

TEAM_COLORS = {
    "LG":  "#C30452", "두산": "#131230", "KT":  "#000000",
    "SSG": "#CE0E2D", "NC":  "#071D4F", "KIA": "#EA0029",
    "롯데": "#002960", "삼성": "#074CA1", "한화": "#FF6600",
    "키움": "#820024",
}

# ── 차트 생성 헬퍼 ────────────────────────────────────────

def fig_to_html(fig, first=False):
    return pio.to_html(
        fig,
        full_html=False,
        include_plotlyjs="cdn" if first else False,
        config={"displayModeBar": False, "responsive": True},
    )


# ── 차트 ─────────────────────────────────────────────────

# 타자
bat_top20 = bat.nlargest(20, "wRC+")
fig_wrc = px.bar(
    bat_top20, x="선수명", y="wRC+", color="팀",
    color_discrete_map=TEAM_COLORS,
    title="wRC+ Top 20",
)
fig_wrc.add_hline(y=100, line_dash="dash", line_color="#888", annotation_text="리그평균(100)")
fig_wrc.update_layout(xaxis_tickangle=-45, plot_bgcolor="#fff", paper_bgcolor="#fff", legend_title="팀")

fig_obp_iso = px.scatter(
    bat, x="OBP", y="ISO", size="PA", color="팀",
    color_discrete_map=TEAM_COLORS,
    hover_name="선수명", hover_data={"PA": True, "wRC+": True},
    title="출루율(OBP) vs 순수장타력(ISO)",
)
fig_obp_iso.update_layout(plot_bgcolor="#fff", paper_bgcolor="#fff")

bat_war = bat.nlargest(15, "bWAR")
fig_bwar = px.bar(
    bat_war, x="bWAR", y="선수명", orientation="h", color="팀",
    color_discrete_map=TEAM_COLORS,
    title="bWAR Top 15",
)
fig_bwar.update_layout(plot_bgcolor="#fff", paper_bgcolor="#fff", height=500)

# 투수
fig_kbb = px.scatter(
    pit, x="BB/9", y="K/9", size="IP_float", color="팀",
    color_discrete_map=TEAM_COLORS,
    hover_name="선수명", hover_data={"IP": True, "FIP": True},
    title="K/9 vs BB/9 (버블 크기 = 이닝)",
)
fig_kbb.update_layout(plot_bgcolor="#fff", paper_bgcolor="#fff")

max_v = max(pit["ERA"].max(), pit["FIP"].max()) + 0.5
fig_era_fip = px.scatter(
    pit, x="ERA", y="FIP", color="팀",
    color_discrete_map=TEAM_COLORS,
    hover_name="선수명", hover_data={"IP": True, "ERA+": True},
    title="ERA vs FIP (대각선 아래 = FIP이 낮아 운 좋은 투수)",
)
fig_era_fip.add_shape(
    type="line", x0=0, y0=0, x1=max_v, y1=max_v,
    line=dict(color="red", dash="dash"),
)
fig_era_fip.update_layout(plot_bgcolor="#fff", paper_bgcolor="#fff")

pit_war = pit.nlargest(15, "pWAR")
fig_pwar = px.bar(
    pit_war, x="pWAR", y="선수명", orientation="h", color="팀",
    color_discrete_map=TEAM_COLORS,
    title="pWAR Top 15",
)
fig_pwar.update_layout(plot_bgcolor="#fff", paper_bgcolor="#fff", height=500)

# 팀 종합
bat_team = (
    bat[bat["PA"] >= 100]
    .groupby("팀")
    .agg(타자WAR=("bWAR", "sum"), 평균wRC=("wRC+", "mean"))
    .round(2).reset_index()
)
pit_team = (
    pit[pit["IP_float"] >= 20]
    .groupby("팀")
    .agg(투수WAR=("pWAR", "sum"), 평균FIP=("FIP", "mean"))
    .round(2).reset_index()
)
team_df = pd.merge(bat_team, pit_team, on="팀", how="outer").fillna(0)
team_df["총WAR"] = (team_df["타자WAR"] + team_df["투수WAR"]).round(2)
team_df = team_df.sort_values("총WAR", ascending=False).reset_index(drop=True)

fig_team_war = px.bar(
    team_df.sort_values("총WAR"), x="총WAR", y="팀",
    orientation="h", color="총WAR", color_continuous_scale="Blues",
    title="팀별 총 WAR",
)
fig_team_war.update_layout(plot_bgcolor="#fff", paper_bgcolor="#fff")

fig_team_scatter = px.scatter(
    team_df, x="평균FIP", y="평균wRC", text="팀", size="총WAR",
    title="팀 평균 FIP vs 평균 wRC+",
    labels={"평균FIP": "평균 FIP (낮을수록 좋음)", "평균wRC": "평균 wRC+"},
    color="팀", color_discrete_map=TEAM_COLORS,
)
fig_team_scatter.update_traces(textposition="top center")
fig_team_scatter.update_layout(plot_bgcolor="#fff", paper_bgcolor="#fff")

# ── 테이블 데이터 JSON ────────────────────────────────────

BAT_COLS = ["선수명", "팀", "PA", "AVG", "OBP", "SLG", "OPS", "wOBA", "wRC+", "ISO", "BABIP", "OPS+", "bWAR"]
PIT_COLS = ["선수명", "팀", "IP", "ERA", "FIP", "xFIP", "ERA+", "WHIP", "K/9", "BB/9", "K/BB", "pWAR"]

bat_cols = [c for c in BAT_COLS if c in bat.columns]
pit_cols = [c for c in PIT_COLS if c in pit.columns]
team_cols = ["팀", "타자WAR", "투수WAR", "총WAR", "평균wRC", "평균FIP"]

bat_json  = bat[bat_cols].round(3).to_json(orient="records", force_ascii=False)
pit_json  = pit[pit_cols].round(3).to_json(orient="records", force_ascii=False)
team_json = team_df[[c for c in team_cols if c in team_df.columns]].to_json(orient="records", force_ascii=False)
teams_json = json.dumps(["전체"] + TEAMS, ensure_ascii=False)

# ── HTML 렌더 ─────────────────────────────────────────────

chart_wrc     = fig_to_html(fig_wrc,       first=True)
chart_obpiso  = fig_to_html(fig_obp_iso)
chart_bwar    = fig_to_html(fig_bwar)
chart_kbb     = fig_to_html(fig_kbb)
chart_erafip  = fig_to_html(fig_era_fip)
chart_pwar    = fig_to_html(fig_pwar)
chart_twar    = fig_to_html(fig_team_war)
chart_tsc     = fig_to_html(fig_team_scatter)

html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>⚾ KBO 2025 세이버매트릭스</title>

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
<style>
  body {{ font-family: 'Noto Sans KR', 'Apple SD Gothic Neo', sans-serif; background: #f8f9fa;
          padding-bottom: env(safe-area-inset-bottom); }}
  h1 {{ font-size: 1.4rem; font-weight: 700; }}
  .nav-tabs .nav-link {{ font-weight: 600; color: #495057; padding: 10px 16px; }}
  .nav-tabs .nav-link.active {{ color: #003580; border-bottom: 3px solid #003580; }}
  .team-badge {{ display: inline-block; padding: 1px 7px; border-radius: 4px; font-size: 0.78rem; font-weight: 600; color: #fff; }}
  .chart-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
  @media (max-width: 768px) {{
    .chart-grid {{ grid-template-columns: 1fr; }}
    h1 {{ font-size: 1.1rem; }}
    .container-fluid {{ padding: 10px 12px; }}
    .nav-tabs .nav-link {{ padding: 8px 12px; font-size: 0.9rem; }}
    table.dataTable td, table.dataTable th {{ font-size: 0.75rem; }}
  }}
  .filter-bar {{ display: flex; gap: 12px; align-items: flex-end; flex-wrap: wrap; margin-bottom: 12px; }}
  .dataTables_wrapper .dataTables_filter input {{ border: 1px solid #ced4da; border-radius: 4px; padding: 4px 8px; }}
  table.dataTable td, table.dataTable th {{ font-size: 0.82rem; white-space: nowrap; }}
  .section-title {{ font-size: 1.1rem; font-weight: 700; margin: 18px 0 10px; color: #212529; }}
</style>
</head>
<body>
<div class="container-fluid py-3 px-4">

  <div class="d-flex justify-content-between align-items-center mb-3">
    <h1>⚾ KBO 2025 세이버매트릭스 분석</h1>
    <small class="text-muted">데이터: koreabaseball.com &nbsp;|&nbsp; 최근 업데이트: {updated}</small>
  </div>

  <!-- 팀 필터 -->
  <div class="filter-bar">
    <div>
      <label class="form-label fw-semibold mb-1">팀 필터</label>
      <select id="teamFilter" class="form-select form-select-sm" style="width:130px">
      </select>
    </div>
    <div id="paFilterWrap">
      <label class="form-label fw-semibold mb-1">최소 PA: <span id="paVal">0</span></label>
      <input type="range" class="form-range" id="paFilter" min="0" max="700" step="10" value="0" style="width:160px">
    </div>
    <div id="ipFilterWrap" style="display:none">
      <label class="form-label fw-semibold mb-1">최소 IP: <span id="ipVal">0</span></label>
      <input type="range" class="form-range" id="ipFilter" min="0" max="200" step="5" value="0" style="width:160px">
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
    <div class="filter-bar" style="margin-bottom:8px">
      <div>
        <label class="form-label fw-semibold mb-1">정렬</label>
        <select id="batSort" class="form-select form-select-sm" style="width:120px">
          <option value="wRC+">wRC+</option>
          <option value="bWAR">bWAR</option>
          <option value="wOBA">wOBA</option>
          <option value="OPS+">OPS+</option>
          <option value="ISO">ISO</option>
          <option value="BABIP">BABIP</option>
        </select>
      </div>
    </div>
    <div class="table-responsive mb-4">
      <table id="batTable" class="table table-sm table-hover table-bordered w-100"></table>
    </div>
    <div class="chart-grid">
      <div>{chart_wrc}</div>
      <div>{chart_obpiso}</div>
    </div>
    <div class="mt-3">{chart_bwar}</div>
  </div>

  <!-- 투수 탭 -->
  <div id="tab-pit" style="display:none">
    <div class="filter-bar" style="margin-bottom:8px">
      <div>
        <label class="form-label fw-semibold mb-1">정렬</label>
        <select id="pitSort" class="form-select form-select-sm" style="width:120px">
          <option value="pWAR">pWAR</option>
          <option value="FIP">FIP</option>
          <option value="ERA+">ERA+</option>
          <option value="K/9">K/9</option>
          <option value="WHIP">WHIP</option>
        </select>
      </div>
    </div>
    <div class="table-responsive mb-4">
      <table id="pitTable" class="table table-sm table-hover table-bordered w-100"></table>
    </div>
    <div class="chart-grid">
      <div>{chart_kbb}</div>
      <div>{chart_erafip}</div>
    </div>
    <div class="mt-3">{chart_pwar}</div>
  </div>

  <!-- 리그 탭 -->
  <div id="tab-team" style="display:none">
    <div class="table-responsive mb-4">
      <table id="teamTable" class="table table-sm table-hover table-bordered w-100"></table>
    </div>
    <div class="chart-grid">
      <div>{chart_twar}</div>
      <div>{chart_tsc}</div>
    </div>
  </div>

</div><!-- /container -->

<script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
<script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
<script src="https://cdn.datatables.net/1.13.6/js/dataTables.bootstrap5.min.js"></script>
<script>
const BAT_DATA  = {bat_json};
const PIT_DATA  = {pit_json};
const TEAM_DATA = {team_json};
const TEAMS     = {teams_json};

const TEAM_COLORS = {json.dumps(TEAM_COLORS, ensure_ascii=False)};

function teamBadge(team) {{
  const c = TEAM_COLORS[team] || '#888';
  return `<span class="team-badge" style="background:${{c}}">${{team}}</span>`;
}}

// 팀 필터 드롭다운 채우기
const sel = document.getElementById('teamFilter');
TEAMS.forEach(t => {{ const o = document.createElement('option'); o.value = t; o.textContent = t; sel.appendChild(o); }});

// 탭 전환
document.querySelectorAll('[data-tab]').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('[data-tab]').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const tab = btn.dataset.tab;
    ['bat','pit','team'].forEach(t => document.getElementById('tab-'+t).style.display = t===tab ? '' : 'none');
    document.getElementById('paFilterWrap').style.display  = tab==='bat'  ? '' : 'none';
    document.getElementById('ipFilterWrap').style.display  = tab==='pit'  ? '' : 'none';
  }});
}});

// ── DataTable 초기화 헬퍼 ─────────────────────────────

function makeColumns(data) {{
  if (!data.length) return [];
  return Object.keys(data[0]).map(k => ({{
    title: k,
    data: k,
    render: (v, type, row) => {{
      if (k === '팀' && type === 'display') return teamBadge(v);
      if (typeof v === 'number') return type === 'display' ? v : v;
      return v ?? '-';
    }}
  }}));
}}

function filterData(data, team, minPA, minIP) {{
  return data.filter(r => {{
    if (team !== '전체' && r['팀'] !== team) return false;
    if (minPA > 0 && r['PA'] !== undefined && r['PA'] < minPA) return false;
    if (minIP > 0 && r['IP_float'] !== undefined && r['IP_float'] < minIP) return false;
    return true;
  }});
}}

let batDT, pitDT, teamDT;

function initBat(data) {{
  const cols = makeColumns(data);
  if (batDT) {{ batDT.destroy(); $('#batTable').empty(); }}
  batDT = $('#batTable').DataTable({{
    data, columns: cols,
    pageLength: 25, order: [[cols.findIndex(c=>c.data==='wRC+'), 'desc']],
    language: {{ search: '검색:', lengthMenu: '_MENU_개씩', info: '_TOTAL_명', paginate: {{next:'▶', previous:'◀'}} }},
    scrollX: true,
  }});
}}

function initPit(data) {{
  const cols = makeColumns(data);
  if (pitDT) {{ pitDT.destroy(); $('#pitTable').empty(); }}
  pitDT = $('#pitTable').DataTable({{
    data, columns: cols,
    pageLength: 25, order: [[cols.findIndex(c=>c.data==='pWAR'), 'desc']],
    language: {{ search: '검색:', lengthMenu: '_MENU_개씩', info: '_TOTAL_명', paginate: {{next:'▶', previous:'◀'}} }},
    scrollX: true,
  }});
}}

function initTeam(data) {{
  const cols = makeColumns(data);
  if (teamDT) {{ teamDT.destroy(); $('#teamTable').empty(); }}
  teamDT = $('#teamTable').DataTable({{
    data, columns: cols,
    pageLength: 15, order: [[cols.findIndex(c=>c.data==='총WAR'), 'desc']],
    paging: false, searching: false,
    language: {{ info: '_TOTAL_개 팀' }},
    scrollX: true,
  }});
}}

// 최초 렌더
initBat(BAT_DATA);
initPit(PIT_DATA);
initTeam(TEAM_DATA);

// 필터 이벤트
function applyFilters() {{
  const team  = sel.value;
  const minPA = parseInt(document.getElementById('paFilter').value);
  const minIP = parseInt(document.getElementById('ipFilter').value);
  initBat(filterData(BAT_DATA, team, minPA, 0));
  initPit(filterData(PIT_DATA, team, 0, minIP));
}}

sel.addEventListener('change', applyFilters);
document.getElementById('paFilter').addEventListener('input', function() {{
  document.getElementById('paVal').textContent = this.value; applyFilters();
}});
document.getElementById('ipFilter').addEventListener('input', function() {{
  document.getElementById('ipVal').textContent = this.value; applyFilters();
}});
</script>
<script>
if ('serviceWorker' in navigator) {{
  window.addEventListener('load', () => {{
    navigator.serviceWorker.register('./sw.js');
  }});
}}
</script>
</body>
</html>
"""

# ── 파일 저장 ─────────────────────────────────────────────

out_dir = Path("docs")
out_dir.mkdir(exist_ok=True)
out_file = out_dir / "index.html"
out_file.write_text(html, encoding="utf-8")
print(f"생성 완료: {out_file}  ({out_file.stat().st_size // 1024} KB)")
