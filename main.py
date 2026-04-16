"""
메인 실행 스크립트.
크롤링 → 세이버 지표 계산 → DB 저장 → CSV 백업
"""

import pandas as pd
from pathlib import Path
from crawler.kbo_crawler import crawl_batting, crawl_pitching, KBO_TEAM_CODES
from sabermetrics import batting as bat_stats
from sabermetrics import pitching as pit_stats
from database import db
from config import SEASON, TEAM

ALL_TEAMS = list(KBO_TEAM_CODES.keys())  # 10개 팀


def _crawl_all_teams(season: int, kind: str) -> pd.DataFrame:
    """10개 팀 순회 크롤링 후 합산. kind='batting'|'pitching'"""
    frames = []
    crawl_fn = crawl_batting if kind == "batting" else crawl_pitching
    for team in ALL_TEAMS:
        try:
            frames.append(crawl_fn(team=team, season=season))
        except Exception as e:
            print(f"  [경고] {team} {kind} 수집 실패: {e}")
    if not frames:
        raise ValueError("전체 팀 크롤링 실패")
    df = pd.concat(frames, ignore_index=True)
    # 같은 팀 내 동명이인 방지용 (선수명+팀) 기준 중복 제거
    df = df.drop_duplicates(subset=["선수명", "팀"]).reset_index(drop=True)
    return df


def run(team: str = TEAM, season: int = SEASON, force_crawl: bool = False):
    label = team if team else "전체"
    print(f"=== KBO 세이버매트릭스 분석 ({season}시즌 {label}) ===\n")

    # ── 타자 ────────────────────────────────────────────
    if force_crawl or not db.table_exists("batting"):
        raw_bat = _crawl_all_teams(season, "batting") if not team else crawl_batting(team=team, season=season)
        bat_df  = bat_stats.calculate_all(raw_bat)
        db.save_batting(bat_df)
        Path("data").mkdir(exist_ok=True)
        bat_df.to_csv(f"data/{season}_{label}_batting.csv", index=False, encoding="utf-8-sig")
        print(f"  CSV: data/{season}_{label}_batting.csv\n")
    else:
        print("[DB] 기존 타자 데이터 로드")
        bat_df = db.load_batting()

    # ── 투수 ────────────────────────────────────────────
    if force_crawl or not db.table_exists("pitching"):
        raw_pit = _crawl_all_teams(season, "pitching") if not team else crawl_pitching(team=team, season=season)
        pit_df  = pit_stats.calculate_all(raw_pit)
        db.save_pitching(pit_df)
        pit_df.to_csv(f"data/{season}_{label}_pitching.csv", index=False, encoding="utf-8-sig")
        print(f"  CSV: data/{season}_{label}_pitching.csv\n")
    else:
        print("[DB] 기존 투수 데이터 로드")
        pit_df = db.load_pitching()

    # ── 요약 출력 ────────────────────────────────────────
    bat_cols = ["선수명", "팀", "PA", "AVG", "OBP", "SLG", "wOBA", "wRC+", "ISO", "BABIP", "bWAR"]
    pit_cols = ["선수명", "팀", "IP", "ERA", "FIP", "xFIP", "ERA+", "K/9", "BB/9", "WHIP", "pWAR"]
    print("\n[타자 Top 5 - wRC+]")
    print(bat_df.nlargest(5, "wRC+")[[c for c in bat_cols if c in bat_df.columns]].to_string(index=False))
    print("\n[투수 Top 5 - FIP]")
    print(pit_df.nsmallest(5, "FIP")[[c for c in pit_cols if c in pit_df.columns]].to_string(index=False))
    print(f"\n타자 {len(bat_df)}명 / 투수 {len(pit_df)}명")
    print("\n=== 완료. 'streamlit run web/app.py' 실행 ===")
    return bat_df, pit_df


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--team",   default=TEAM,   help="팀 코드 (빈값=전체팀순회)")
    parser.add_argument("--season", default=SEASON, type=int)
    parser.add_argument("--force",  action="store_true", help="강제 재크롤링")
    args = parser.parse_args()
    run(team=args.team, season=args.season, force_crawl=args.force)
