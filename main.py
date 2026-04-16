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
from config import SEASONS

ALL_TEAMS = list(KBO_TEAM_CODES.keys())


def _crawl_all_teams(season: int, kind: str) -> pd.DataFrame:
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
    df = df.drop_duplicates(subset=["선수명", "팀"]).reset_index(drop=True)
    return df


def run_season(season: int, team: str = "", force_crawl: bool = False):
    label = team if team else "전체"
    print(f"\n=== {season}시즌 {label} ===")
    Path("data").mkdir(exist_ok=True)

    # ── 타자 ──────────────────────────────────────────────
    if force_crawl or not db.season_exists("batting", season):
        raw_bat = _crawl_all_teams(season, "batting") if not team else crawl_batting(team=team, season=season)
        bat_df  = bat_stats.calculate_all(raw_bat, season=season)
        db.save_batting(bat_df, season)
        bat_df.to_csv(f"data/{season}_{label}_batting.csv", index=False, encoding="utf-8-sig")
        print(f"  CSV: data/{season}_{label}_batting.csv")
    else:
        print(f"  [DB] {season} 타자 데이터 이미 있음 (--force 로 재수집)")
        bat_df = db.load_batting(season)

    # ── 투수 ──────────────────────────────────────────────
    if force_crawl or not db.season_exists("pitching", season):
        raw_pit = _crawl_all_teams(season, "pitching") if not team else crawl_pitching(team=team, season=season)
        pit_df  = pit_stats.calculate_all(raw_pit, season=season)
        db.save_pitching(pit_df, season)
        pit_df.to_csv(f"data/{season}_{label}_pitching.csv", index=False, encoding="utf-8-sig")
        print(f"  CSV: data/{season}_{label}_pitching.csv")
    else:
        print(f"  [DB] {season} 투수 데이터 이미 있음 (--force 로 재수집)")
        pit_df = db.load_pitching(season)

    return bat_df, pit_df


def run(seasons: list = None, team: str = "", force_crawl: bool = False):
    if seasons is None:
        seasons = SEASONS
    print(f"=== KBO 세이버매트릭스 분석 | 시즌: {seasons} ===")

    all_bat, all_pit = [], []
    for season in seasons:
        bat_df, pit_df = run_season(season, team=team, force_crawl=force_crawl)
        all_bat.append(bat_df)
        all_pit.append(pit_df)

    bat_all = pd.concat(all_bat, ignore_index=True)
    pit_all = pd.concat(all_pit, ignore_index=True)

    bat_cols = ["선수명", "팀", "시즌", "PA", "AVG", "wOBA", "wRC+", "ISO", "BABIP", "bWAR"]
    pit_cols = ["선수명", "팀", "시즌", "IP", "ERA", "FIP", "xFIP", "ERA+", "K/9", "pWAR"]

    for season in seasons:
        b = bat_all[bat_all["시즌"] == season]
        p = pit_all[pit_all["시즌"] == season]
        print(f"\n[{season} 타자 Top 5 - wRC+]")
        print(b.nlargest(5, "wRC+")[[c for c in bat_cols if c in b.columns]].to_string(index=False))
        print(f"\n[{season} 투수 Top 5 - FIP]")
        print(p.nsmallest(5, "FIP")[[c for c in pit_cols if c in p.columns]].to_string(index=False))

    print(f"\n총 타자 {len(bat_all)}명 / 투수 {len(pit_all)}명")
    print("\n=== 완료. 'streamlit run web/app.py' 또는 'python build_site.py' ===")
    return bat_all, pit_all


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--team",    default="",     help="팀 코드 (빈값=전체)")
    parser.add_argument("--seasons", default=None,   type=int, nargs="+",
                        help="수집 시즌 (예: --seasons 2023 2024 2025)")
    parser.add_argument("--force",   action="store_true", help="강제 재크롤링")
    args = parser.parse_args()
    run(seasons=args.seasons, team=args.team, force_crawl=args.force)
