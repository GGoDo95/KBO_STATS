"""
statiz.co.kr 로그인 후 KBO 선수 스탯 크롤링.

로그인 → 세션 유지 → 팀별/시즌별 스탯 페이지 파싱
"""

import os
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from config import HEADERS, CRAWL_DELAY, SEASON

LOGIN_URL = "https://www.statiz.co.kr/member/handle.php"
STAT_URL  = "https://www.statiz.co.kr/stats/"

# statiz 팀명 코드 (URL 파라미터 기준)
TEAM_MAP = {
    "LG": "LG",
    "KT": "KT",
    "SSG": "SSG",
    "NC": "NC",
    "두산": "OB",
    "KIA": "KIA",
    "롯데": "LT",
    "삼성": "SS",
    "한화": "HAN",
    "키움": "WO",
}


def _login(user_id: str, password: str) -> requests.Session:
    """statiz.co.kr에 로그인하고 세션 반환."""
    session = requests.Session()

    # 로그인 페이지 GET (쿠키 획득)
    session.get("https://www.statiz.co.kr/member/?m=login", headers=HEADERS, timeout=10)
    time.sleep(0.5)

    payload = {
        "act":          "loginJWT",
        "retPage":      "",
        "location":     "",
        "userID":       user_id,
        "userPassword": password,
    }
    resp = session.post(LOGIN_URL, data=payload, headers={
        **HEADERS,
        "Referer": "https://www.statiz.co.kr/member/?m=login",
        "Content-Type": "application/x-www-form-urlencoded",
    }, timeout=10, allow_redirects=True)

    # 로그인 성공 확인
    check = session.get("https://www.statiz.co.kr/", headers=HEADERS, timeout=10)
    soup = BeautifulSoup(check.text, "html.parser")
    # 로그인 상태면 '로그아웃' 링크가 있음
    logged_in = any(
        "logout" in a.get("href", "").lower() or "로그아웃" in a.get_text()
        for a in soup.find_all("a")
    )
    if not logged_in:
        raise RuntimeError("statiz 로그인 실패. ID/PW를 확인하세요.")

    print("  statiz 로그인 성공")
    return session


def _get_soup(session: requests.Session, url: str, params: dict) -> BeautifulSoup:
    resp = session.get(url, params=params, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    time.sleep(CRAWL_DELAY)
    return BeautifulSoup(resp.text, "html.parser")


def _parse_table(soup: BeautifulSoup) -> pd.DataFrame:
    """statiz 스탯 테이블 파싱."""
    table = soup.find("table", {"id": "mytable"})
    if table is None:
        # 다른 테이블 ID 시도
        table = soup.find("table", {"class": lambda c: c and "table" in " ".join(c)})
    if table is None:
        return pd.DataFrame()

    header_row = table.find("thead")
    if header_row:
        headers = [th.get_text(strip=True) for th in header_row.find_all("th")]
    else:
        headers = [th.get_text(strip=True) for th in table.find_all("th")]

    rows = []
    tbody = table.find("tbody") or table
    for tr in tbody.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if cells:
            rows.append(cells)

    if not rows:
        return pd.DataFrame()

    # 컬럼 수 맞추기
    max_cols = max(len(r) for r in rows)
    if len(headers) < max_cols:
        headers += [f"col_{i}" for i in range(len(headers), max_cols)]

    df = pd.DataFrame(rows, columns=headers[:max_cols])
    return df


def _to_numeric(df: pd.DataFrame, exclude: list) -> pd.DataFrame:
    for col in df.columns:
        if col not in exclude:
            cleaned = df[col].astype(str).str.replace(",", "", regex=False).str.replace("%", "", regex=False)
            df[col] = pd.to_numeric(cleaned, errors="ignore")
    return df


def _fetch_stat(
    session: requests.Session,
    stat_type: str,   # "batting" | "pitching"
    team: str,
    season: int,
) -> pd.DataFrame:
    """
    statiz /stats/ 페이지에서 스탯 수집.
    stat_type: 'batting' → m=total, 'pitching' → m=pitcher
    """
    m_val = "total" if stat_type == "batting" else "pitcher"
    team_code = TEAM_MAP.get(team, team)

    params = {
        "m": m_val,
        "y": season,
        "t": team_code,
        "re": "1",
    }

    all_frames = []
    page = 1

    while True:
        params["pg"] = page
        soup = _get_soup(session, STAT_URL, params)

        df_page = _parse_table(soup)
        if df_page.empty:
            break

        all_frames.append(df_page)

        # 다음 페이지 링크 확인
        paging = soup.find("div", {"class": ["paging", "pagination", "page"]})
        has_next = False
        if paging:
            for a in paging.find_all("a"):
                href = a.get("href", "")
                if f"pg={page + 1}" in href or str(page + 1) in a.get_text():
                    has_next = True
                    break

        # 한 페이지만 있거나 다음 페이지 없으면 종료
        if not has_next or len(df_page) < 20:
            break
        page += 1

    return pd.concat(all_frames, ignore_index=True) if all_frames else pd.DataFrame()


def crawl_batting(
    team: str = "LG",
    season: int = SEASON,
    user_id: str = None,
    password: str = None,
) -> pd.DataFrame:
    """LG 트윈스 타자 기본 스탯 크롤링 (로그인 필요)."""
    if user_id is None:
        user_id = os.environ.get("STATIZ_ID", "")
    if password is None:
        password = os.environ.get("STATIZ_PW", "")
    if not user_id or not password:
        raise ValueError("환경변수 STATIZ_ID, STATIZ_PW를 설정하세요.")
    print(f"[크롤링] {season}시즌 {team} 타자 스탯 수집 중...")
    session = _login(user_id, password)

    df = _fetch_stat(session, "batting", team, season)
    if df.empty:
        raise ValueError(f"{season}시즌 {team} 타자 데이터를 가져오지 못했습니다.")

    # 컬럼 정리
    df = df.rename(columns={
        "선수": "선수명",
        "볼넷": "BB",
        "고의4구": "IBB",
        "사구": "HBP",
        "삼진": "SO",
        "타석": "PA",
        "타수": "AB",
        "안타": "H",
        "2루타": "2B",
        "3루타": "3B",
        "홈런": "HR",
        "타점": "RBI",
        "득점": "R",
        "도루": "SB",
        "희생번트": "SAC",
        "희생플라이": "SF",
        "타율": "AVG",
        "출루율": "OBP",
        "장타율": "SLG",
    })
    df["팀"] = team
    df["시즌"] = season

    exclude = ["선수명", "팀", "포지션", "시즌"]
    df = _to_numeric(df, exclude=exclude)

    if "PA" in df.columns:
        df = df[df["PA"] >= 10].reset_index(drop=True)

    print(f"  → {len(df)}명 타자 데이터 수집 완료")
    return df


def crawl_pitching(
    team: str = "LG",
    season: int = SEASON,
    user_id: str = None,
    password: str = None,
) -> pd.DataFrame:
    """LG 트윈스 투수 기본 스탯 크롤링 (로그인 필요)."""
    if user_id is None:
        user_id = os.environ.get("STATIZ_ID", "")
    if password is None:
        password = os.environ.get("STATIZ_PW", "")
    if not user_id or not password:
        raise ValueError("환경변수 STATIZ_ID, STATIZ_PW를 설정하세요.")
    print(f"[크롤링] {season}시즌 {team} 투수 스탯 수집 중...")
    session = _login(user_id, password)

    df = _fetch_stat(session, "pitching", team, season)
    if df.empty:
        raise ValueError(f"{season}시즌 {team} 투수 데이터를 가져오지 못했습니다.")

    df = df.rename(columns={
        "선수": "선수명",
        "이닝": "IP",
        "피안타": "H",
        "피홈런": "HR",
        "볼넷": "BB",
        "사구": "HBP",
        "탈삼진": "SO",
        "자책점": "ER",
        "평균자책점": "ERA",
        "세이브": "SV",
        "홀드": "HLD",
    })
    df["팀"] = team
    df["시즌"] = season

    exclude = ["선수명", "팀", "시즌"]
    df = _to_numeric(df, exclude=exclude)

    if "IP" in df.columns:
        ip_float = df["IP"].astype(str).apply(
            lambda v: int(str(v).split(".")[0]) + int(str(v).split(".")[1]) / 3
            if "." in str(v) and str(v).replace(".", "").isdigit() else 0
        )
        df = df[ip_float >= 5].reset_index(drop=True)

    print(f"  → {len(df)}명 투수 데이터 수집 완료")
    return df
