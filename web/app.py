"""
Streamlit 대시보드 - KBO 2025 세이버매트릭스 분석
실행: streamlit run web/app.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px
from database import db
from main import run

st.set_page_config(page_title="KBO 세이버매트릭스", page_icon="⚾", layout="wide")
st.title("⚾ KBO 2025 세이버매트릭스 분석")

# 데이터 최신화 날짜 표시
data_dir = Path(__file__).parent.parent / "data"
bat_files = sorted(data_dir.glob("*_batting.csv"))
if bat_files:
    import datetime
    mtime = bat_files[-1].stat().st_mtime
    updated = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
    st.caption(f"데이터 출처: koreabaseball.com | 세이버 지표 직접 계산 | 최근 업데이트: {updated}")
else:
    st.caption("데이터 출처: koreabaseball.com | 세이버 지표 직접 계산")

TEAMS = ["전체", "LG", "두산", "KT", "SSG", "NC", "KIA", "롯데", "삼성", "한화", "키움"]
from config import SEASONS

# ── 사이드바 ──────────────────────────────────────────────
with st.sidebar:
    st.header("설정")
    seasons_to_collect = st.multiselect("수집 시즌", SEASONS, default=SEASONS)
    if st.button("데이터 수집", type="primary"):
        with st.spinner("KBO에서 데이터 수집 중... (시즌당 2~3분 소요)"):
            try:
                run(seasons=seasons_to_collect, team="", force_crawl=True)
                st.success("완료!")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"오류: {e}")

    st.divider()
    st.markdown("""
**지표 설명**
- **wOBA** : 가중 출루율 (0.320 = 리그평균)
- **wRC+** : 파크팩터 보정 생산성 (100 = 평균)
- **ISO**  : 순수 장타력
- **BABIP**: 인플레이 타율
- **FIP**  : 수비무관 자책점
- **xFIP** : 기대 FIP (홈런 운 제거)
- **ERA+** : 보정 평균자책점
- **WAR**  : 대체선수 대비 승리 기여
""")


# ── 데이터 로드 ───────────────────────────────────────────
@st.cache_data(ttl=300)
def load_data():
    if db.table_exists("batting") and db.table_exists("pitching"):
        return db.load_batting(), db.load_pitching()
    # CSV fallback — 클라우드 배포 등 DB 없는 환경
    data_dir = Path(__file__).parent.parent / "data"
    bat_files = sorted(data_dir.glob("*_전체_batting.csv"))
    pit_files = sorted(data_dir.glob("*_전체_pitching.csv"))
    if bat_files and pit_files:
        return (
            pd.concat([pd.read_csv(f) for f in bat_files], ignore_index=True),
            pd.concat([pd.read_csv(f) for f in pit_files], ignore_index=True),
        )
    return None, None


bat_all, pit_all = load_data()

if bat_all is None:
    st.warning("데이터 없음. 사이드바에서 '데이터 수집'을 클릭하세요.")
    st.stop()

available_seasons = sorted(bat_all["시즌"].unique().tolist(), reverse=True) if "시즌" in bat_all.columns else [2025]

# ── 시즌 + 팀 필터 (공통) ─────────────────────────────────
col_s, col_tf, _ = st.columns([2, 2, 4])
with col_s:
    season_filter = st.selectbox("시즌", ["전체"] + available_seasons, index=0)
with col_tf:
    team_filter = st.selectbox("팀 필터", TEAMS, index=0)

def filter_df(df):
    result = df.copy()
    if season_filter != "전체" and "시즌" in result.columns:
        result = result[result["시즌"] == int(season_filter)]
    if team_filter != "전체" and "팀" in result.columns:
        result = result[result["팀"] == team_filter]
    return result.reset_index(drop=True)


bat_df = filter_df(bat_all)
pit_df = filter_df(pit_all)


# ── 탭 ───────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["타자 분석", "투수 분석", "리그 종합"])


# ════════════════════════════════════════════════════════
# 탭 1: 타자
# ════════════════════════════════════════════════════════
with tab1:
    st.subheader(f"타자 세이버매트릭스 {'— ' + team_filter if team_filter != '전체' else '(전체 팀)'}")

    c1, c2 = st.columns([2, 1])
    with c1:
        sort_by = st.selectbox("정렬 기준", ["wRC+", "bWAR", "wOBA", "OPS+", "ISO", "BABIP"], key="bat_sort")
    with c2:
        pa_max_val = int(bat_df["PA"].max()) if len(bat_df) else 700
        min_pa = st.slider("최소 PA", 0, pa_max_val, 0, step=10,
                           help=f"현재 데이터 PA 범위: 0~{pa_max_val}")

    bat_show_cols = ["선수명", "팀", "PA", "AVG", "OBP", "SLG", "OPS", "wOBA", "wRC+", "ISO", "BABIP", "OPS+", "bWAR"]
    bat_show = [c for c in bat_show_cols if c in bat_df.columns]
    filtered = bat_df[bat_df["PA"] >= min_pa].sort_values(sort_by, ascending=False).reset_index(drop=True)
    filtered.index += 1

    st.dataframe(
        filtered[bat_show].style
            .background_gradient(subset=["wRC+", "bWAR"], cmap="RdYlGn")
            .highlight_null(color="#e0e0e0"),
        use_container_width=True,
    )

    c_a, c_b = st.columns(2)
    with c_a:
        top_n = filtered.head(20)
        fig = px.bar(top_n, x="선수명", y="wRC+", color="팀" if "팀" in top_n.columns else "wRC+",
                     title="wRC+ Top 20", color_discrete_sequence=px.colors.qualitative.Set2)
        fig.add_hline(y=100, line_dash="dash", line_color="gray", annotation_text="리그평균")
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    with c_b:
        fig2 = px.scatter(filtered, x="OBP", y="ISO", size="PA",
                          color="팀" if "팀" in filtered.columns else "wRC+",
                          hover_name="선수명",
                          title="출루율 vs 장타력")
        st.plotly_chart(fig2, use_container_width=True)

    fig3 = px.bar(
        filtered.sort_values("bWAR").tail(15),
        x="bWAR", y="선수명", orientation="h",
        color="팀" if "팀" in filtered.columns else "bWAR",
        title="bWAR Top 15",
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig3.add_vline(x=0, line_color="gray")
    st.plotly_chart(fig3, use_container_width=True)


# ════════════════════════════════════════════════════════
# 탭 2: 투수
# ════════════════════════════════════════════════════════
with tab2:
    st.subheader(f"투수 세이버매트릭스 {'— ' + team_filter if team_filter != '전체' else '(전체 팀)'}")

    c1, c2 = st.columns([2, 1])
    with c1:
        pit_sort = st.selectbox("정렬 기준",
            ["pWAR", "FIP", "ERA+", "K/9", "WHIP"],
            format_func=lambda x: f"{x} {'↑' if x in ['pWAR','ERA+','K/9'] else '↓'}",
            key="pit_sort")
    with c2:
        ip_max_val = int(pit_df["IP_float"].max()) if len(pit_df) else 200
        min_ip = st.slider("최소 IP", 0, ip_max_val, 0, step=5,
                           help=f"현재 데이터 IP 범위: 0~{ip_max_val}")

    pit_show_cols = ["선수명", "팀", "IP", "ERA", "FIP", "xFIP", "ERA+", "WHIP", "K/9", "BB/9", "K/BB", "pWAR"]
    pit_show = [c for c in pit_show_cols if c in pit_df.columns]

    asc = pit_sort in ["FIP", "xFIP", "WHIP"]
    pit_filtered = pit_df[pit_df["IP_float"] >= min_ip].sort_values(pit_sort, ascending=asc).reset_index(drop=True)
    pit_filtered.index += 1

    st.dataframe(
        pit_filtered[pit_show].style
            .background_gradient(subset=["ERA+", "pWAR"], cmap="RdYlGn")
            .highlight_null(color="#e0e0e0"),
        use_container_width=True,
    )

    c_a, c_b = st.columns(2)
    with c_a:
        fig4 = px.scatter(pit_filtered, x="BB/9", y="K/9", size="IP_float",
                          color="팀" if "팀" in pit_filtered.columns else "FIP",
                          hover_name="선수명",
                          title="K/9 vs BB/9 (버블=이닝)")
        st.plotly_chart(fig4, use_container_width=True)

    with c_b:
        fig5 = px.scatter(pit_filtered, x="ERA", y="FIP",
                          color="팀" if "팀" in pit_filtered.columns else "pWAR",
                          hover_name="선수명",
                          title="ERA vs FIP")
        max_v = max(pit_filtered["ERA"].max(), pit_filtered["FIP"].max()) + 0.5
        fig5.add_shape(type="line", x0=0, y0=0, x1=max_v, y1=max_v,
                       line=dict(color="red", dash="dash"))
        st.plotly_chart(fig5, use_container_width=True)

    fig6 = px.bar(
        pit_filtered.sort_values("pWAR").tail(15),
        x="pWAR", y="선수명", orientation="h",
        color="팀" if "팀" in pit_filtered.columns else "pWAR",
        title="pWAR Top 15",
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig6.add_vline(x=0, line_color="gray")
    st.plotly_chart(fig6, use_container_width=True)


# ════════════════════════════════════════════════════════
# 탭 3: 리그 종합
# ════════════════════════════════════════════════════════
with tab3:
    st.subheader("2025 KBO 리그 종합 지표")

    # 팀별 집계 (전체 데이터 기준)
    if "팀" in bat_all.columns and "팀" in pit_all.columns:
        bat_team = (
            bat_all[bat_all["PA"] >= 100]
            .groupby("팀")
            .agg(팀_bWAR=("bWAR", "sum"), 팀_wRC_avg=("wRC+", "mean"), 선수수=("선수명", "count"))
            .round(2).reset_index()
        )
        pit_team = (
            pit_all[pit_all["IP_float"] >= 20]
            .groupby("팀")
            .agg(팀_pWAR=("pWAR", "sum"), 팀_FIP_avg=("FIP", "mean"))
            .round(2).reset_index()
        )
        team_summary = pd.merge(bat_team, pit_team, on="팀", how="outer").fillna(0)
        team_summary["총WAR"] = (team_summary["팀_bWAR"] + team_summary["팀_pWAR"]).round(2)
        team_summary = team_summary.sort_values("총WAR", ascending=False).reset_index(drop=True)
        team_summary.index += 1

        st.dataframe(
            team_summary.rename(columns={
                "팀_bWAR": "타자WAR", "팀_wRC_avg": "평균wRC+",
                "팀_pWAR": "투수WAR", "팀_FIP_avg": "평균FIP",
            }).style.background_gradient(subset=["총WAR"], cmap="Blues"),
            use_container_width=True,
        )

        c_a, c_b = st.columns(2)
        with c_a:
            fig7 = px.bar(team_summary.sort_values("총WAR"), x="총WAR", y="팀",
                          orientation="h", color="총WAR", color_continuous_scale="Blues",
                          title="팀별 총 WAR (타자 + 투수)")
            st.plotly_chart(fig7, use_container_width=True)
        with c_b:
            fig8 = px.scatter(team_summary, x="팀_FIP_avg", y="팀_wRC_avg",
                              text="팀", size="총WAR",
                              title="팀 평균 FIP vs 평균 wRC+",
                              labels={"팀_FIP_avg": "평균 FIP (낮을수록 좋음)", "팀_wRC_avg": "평균 wRC+"})
            fig8.update_traces(textposition="top center")
            st.plotly_chart(fig8, use_container_width=True)
    else:
        # 전체 데이터 없을 때 간단 지표만
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("평균 wRC+", f"{bat_df[bat_df['PA']>=100]['wRC+'].mean():.1f}" if len(bat_df) else "N/A")
        c2.metric("평균 FIP",  f"{pit_df[pit_df['IP_float']>=20]['FIP'].mean():.2f}" if len(pit_df) else "N/A")
        c3.metric("타자 bWAR 합", f"{bat_df['bWAR'].sum():.1f}")
        c4.metric("투수 pWAR 합", f"{pit_df['pWAR'].sum():.1f}")
