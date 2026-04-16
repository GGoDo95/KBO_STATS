"""
KBO 공식 홈페이지(koreabaseball.com) 크롤러.
ASP.NET WebForms 구조: GET → 시즌 POST → 팀 POST → 페이지 수집

타자: Basic1(기본) + Basic2(볼넷/삼진/출루율) 병합
투수: Basic1(기본) + Basic2(추가) 병합
"""

import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from config import HEADERS, CRAWL_DELAY, SEASON

BASE = "https://www.koreabaseball.com"

KBO_TEAM_CODES = {
    "LG": "LG", "KT": "KT", "SSG": "SK", "NC": "NC",
    "두산": "OB", "KIA": "HT", "롯데": "LT", "삼성": "SS",
    "한화": "HH", "키움": "WO",
}


# ── 내부 유틸 ────────────────────────────────────────────

def _get_soup(session, url):
    r = session.get(url, headers=HEADERS, timeout=10)
    r.encoding = "utf-8"
    time.sleep(CRAWL_DELAY)
    return BeautifulSoup(r.text, "html.parser")


def _viewstate(soup):
    result = {}
    for name in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"):
        tag = soup.find("input", {"name": name})
        if tag:
            result[name] = tag.get("value", "")
    return result


def _hidden_fields(soup):
    return {
        inp["name"]: inp.get("value", "")
        for inp in soup.find_all("input", type="hidden")
        if inp.get("name") and not inp["name"].startswith("__")
    }


def _sel_names(soup):
    return {sel["name"]: sel for sel in soup.find_all("select") if sel.get("name")}


def _post(session, url, soup, eventtarget, extra_fields):
    form = {
        **_viewstate(soup),
        **_hidden_fields(soup),
        "__EVENTTARGET": eventtarget,
        "__EVENTARGUMENT": "",
        **extra_fields,
    }
    r = session.post(url, data=form, headers={**HEADERS, "Referer": url}, timeout=10)
    time.sleep(CRAWL_DELAY)
    return BeautifulSoup(r.text, "html.parser")


def _parse_table(soup):
    table = soup.find("table", {"class": "tData01"})
    if not table:
        return pd.DataFrame()
    rows = table.find_all("tr")
    if len(rows) < 2:
        return pd.DataFrame()
    headers = [th.get_text(strip=True) for th in rows[0].find_all("th")]
    data = []
    for tr in rows[1:]:
        cells = [td.get_text(strip=True) for td in tr.find_all("td")]
        if cells:
            data.append(cells)
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data, columns=headers[:len(data[0])])


def _parse_table_with_ids(soup):
    """테이블 파싱 + 선수명 링크에서 playerId 추출. (df, {이름: id}) 반환."""
    import re
    table = soup.find("table", {"class": "tData01"})
    if not table:
        return pd.DataFrame(), {}
    rows = table.find_all("tr")
    if len(rows) < 2:
        return pd.DataFrame(), {}
    headers = [th.get_text(strip=True) for th in rows[0].find_all("th")]
    data, player_ids = [], {}
    for tr in rows[1:]:
        tds = tr.find_all("td")
        cells = [td.get_text(strip=True) for td in tds]
        if not cells:
            continue
        data.append(cells)
        for td in tds:
            a = td.find("a", href=True)
            if a and "playerId=" in (a.get("href") or ""):
                m = re.search(r"playerId=(\d+)", a["href"])
                name = td.get_text(strip=True)
                if m and name:
                    player_ids[name] = int(m.group(1))
                break
    if not data:
        return pd.DataFrame(), player_ids
    return pd.DataFrame(data, columns=headers[:len(data[0])]), player_ids


def _init_filters(session, url, team_code, season):
    """GET → 시즌 POST → (팀 POST) 초기화. 마지막 soup 반환."""
    soup = _get_soup(session, url)
    sels = _sel_names(soup)
    SN  = next(k for k in sels if "Season" in k)
    SerN = next(k for k in sels if "Series" in k)
    TN  = next(k for k in sels if "Team" in k)
    PN  = next((k for k in sels if "Pos" in k), "")

    # 시즌 설정
    soup2 = _post(session, url, soup, SN, {SN: str(season), SerN: "0", TN: "", PN: ""})
    # 팀 필터 (빈 문자열이면 전체 팀)
    soup3 = _post(session, url, soup2, TN, {SN: str(season), SerN: "0", TN: team_code, PN: ""})
    return soup3, SN, SerN, TN, PN


def _next_page_target(soup, page):
    """페이징 div에서 다음 페이지 __EVENTTARGET 추출."""
    import re
    paging = soup.find("div", {"class": "paging"})
    if not paging:
        return None
    for a in paging.find_all("a"):
        href = a.get("href", "")
        # btnNo{page} 링크 찾기
        m = re.search(r"__doPostBack\('([^']+)','([^']*)'\)", href)
        if m and f"btnNo{page}" in m.group(1):
            return m.group(1)
    return None


def _fetch_all_pages(session, url, team_code, season):
    """모든 페이지 데이터를 수집해 DataFrame 반환."""
    soup, SN, SerN, TN, PN = _init_filters(session, url, team_code, season)

    all_frames = [_parse_table(soup)]
    page = 2

    while True:
        target = _next_page_target(soup, page)
        if not target:
            break

        soup = _post(session, url, soup, target, {
            SN: str(season), SerN: "0", TN: team_code, PN: "",
        })
        df_page = _parse_table(soup)
        if df_page.empty:
            break
        all_frames.append(df_page)
        page += 1

    return pd.concat(all_frames, ignore_index=True) if all_frames else pd.DataFrame()


def _fetch_all_pages_with_ids(session, url, team_code, season):
    """모든 페이지 데이터 + player_id dict 수집."""
    soup, SN, SerN, TN, PN = _init_filters(session, url, team_code, season)

    df0, ids0 = _parse_table_with_ids(soup)
    all_frames = [df0]
    all_ids = dict(ids0)
    page = 2

    while True:
        target = _next_page_target(soup, page)
        if not target:
            break
        soup = _post(session, url, soup, target, {
            SN: str(season), SerN: "0", TN: team_code, PN: "",
        })
        df_page, ids_page = _parse_table_with_ids(soup)
        if df_page.empty:
            break
        all_frames.append(df_page)
        all_ids.update(ids_page)
        page += 1

    combined = pd.concat(all_frames, ignore_index=True) if all_frames else pd.DataFrame()
    return combined, all_ids


def crawl_player_profile(player_id: int, kind: str = "hitter") -> dict:
    """선수 기본 프로필(신상정보) 크롤링."""
    kind_path = "Hitter" if kind == "hitter" else "Pitcher"
    url = f"{BASE}/Record/Player/{kind_path}Detail/Basic.aspx?playerId={player_id}"
    session = requests.Session()
    try:
        soup = _get_soup(session, url)
    except Exception as e:
        print(f"  [프로필 오류] playerId={player_id}: {e}")
        return {}

    basic = soup.find("div", {"class": "player_basic"})
    if not basic:
        return {}

    info: dict = {}
    for li in basic.find_all("li"):
        text = li.get_text(strip=True)
        if ":" in text:
            key, _, val = text.partition(":")
            info[key.strip()] = val.strip()

    # 선수 사진 URL
    player_info_div = soup.find("div", {"class": "player_info"})
    if player_info_div:
        img = player_info_div.find("img", src=lambda s: s and "person" in (s or ""))
        if img and img.get("src"):
            src = img["src"]
            info["사진"] = ("https:" + src) if src.startswith("//") else src

    info["player_id"] = player_id
    info["kind"] = kind
    return info


def crawl_all_profiles(player_id_map: dict, existing_ids: set = None) -> list:
    """
    player_id_map: {선수명: (player_id, kind)} 형태
    existing_ids : 이미 DB에 있는 player_id 집합 (스킵)
    """
    existing_ids = existing_ids or set()
    profiles = []
    new_ids = {name: v for name, v in player_id_map.items() if v[0] not in existing_ids}
    print(f"[프로필] 신규 수집 대상: {len(new_ids)}명 (기존: {len(existing_ids)}명)")
    for i, (name, (pid, kind)) in enumerate(new_ids.items(), 1):
        print(f"  [{i}/{len(new_ids)}] {name} (id={pid})", end="", flush=True)
        p = crawl_player_profile(pid, kind)
        if p:
            profiles.append(p)
            print(" ✓")
        else:
            print(" ✗")
    return profiles


def _to_numeric(df, exclude):
    for col in df.columns:
        if col not in exclude:
            cleaned = df[col].astype(str).str.replace(",", "", regex=False)
            converted = pd.to_numeric(cleaned, errors="coerce")
            # 변환 실패(NaN) 비율이 50% 미만일 때만 숫자형 적용
            if converted.notna().mean() >= 0.5:
                df[col] = converted
    return df


# ── 공개 API ──────────────────────────────────────────────

def crawl_batting(team: str = "LG", season: int = SEASON, return_ids: bool = False):
    """
    KBO 타자 스탯 수집.
    Basic1: 순위, 선수명, 팀, AVG, G, PA, AB, R, H, 2B, 3B, HR, TB, RBI, SAC, SF
    Basic2: 순위, 선수명, 팀, AVG, BB, IBB, HBP, SO, GDP, SLG, OBP, OPS, MH, RISP, PH-BA
    """
    team_code = KBO_TEAM_CODES.get(team, team)
    print(f"[크롤링] {season}시즌 {team} 타자 스탯 수집 중...")

    session = requests.Session()
    url1 = f"{BASE}/Record/Player/HitterBasic/Basic1.aspx"
    url2 = f"{BASE}/Record/Player/HitterBasic/Basic2.aspx"

    if return_ids:
        df1, ids1 = _fetch_all_pages_with_ids(session, url1, team_code, season)
        df2 = _fetch_all_pages(session, url2, team_code, season)
    else:
        df1 = _fetch_all_pages(session, url1, team_code, season)
        df2 = _fetch_all_pages(session, url2, team_code, season)
        ids1 = {}

    if df1.empty:
        raise ValueError(f"{season}시즌 {team} 타자 데이터 수집 실패")

    # 팀명 → 팀 으로 컬럼명 통일
    df1 = df1.rename(columns={"팀명": "팀"})
    df2 = df2.rename(columns={"팀명": "팀"})

    # Basic2 중복 컬럼 제거 후 병합
    drop2 = [c for c in ["순위", "AVG", "팀"] if c in df2.columns]
    df2_clean = df2.drop(columns=drop2, errors="ignore").drop_duplicates(subset=["선수명"])
    df1_clean = df1.drop_duplicates(subset=["선수명"])
    df = pd.merge(df1_clean, df2_clean, on="선수명", how="left")

    # _x/_y 접미사 제거
    for col in list(df.columns):
        for suffix in ["_x", "_y"]:
            if col.endswith(suffix):
                base = col[:-2]
                if base not in df.columns:
                    df = df.rename(columns={col: base})
                else:
                    df = df.drop(columns=[col])

    # 팀 필터 지정 시 덮어씀, 없으면 테이블 팀명 유지
    if team:
        df["팀"] = team
    elif "팀" not in df.columns:
        df["팀"] = ""
    df["시즌"] = season

    df = _to_numeric(df, exclude=["선수명", "팀", "시즌", "순위"])

    if "PA" in df.columns:
        df = df[df["PA"] >= 1].reset_index(drop=True)

    df = df.drop(columns=["순위", "MH", "RISP", "PH-BA"], errors="ignore")
    print(f"  → {len(df)}명 타자 수집 완료")
    if return_ids:
        return df, ids1
    return df


def crawl_pitching(team: str = "LG", season: int = SEASON, return_ids: bool = False):
    """
    KBO 투수 스탯 수집.
    Basic1: 순위, 선수명, 팀, ERA, G, W, L, SV, HLD, IP, R, ER, BB, HBP, SO, HR
    Basic2: 추가 투구 지표
    """
    team_code = KBO_TEAM_CODES.get(team, team)
    print(f"[크롤링] {season}시즌 {team} 투수 스탯 수집 중...")

    session = requests.Session()
    url1 = f"{BASE}/Record/Player/PitcherBasic/Basic1.aspx"
    url2 = f"{BASE}/Record/Player/PitcherBasic/Basic2.aspx"

    if return_ids:
        df1, ids1 = _fetch_all_pages_with_ids(session, url1, team_code, season)
        df2 = _fetch_all_pages(session, url2, team_code, season)
    else:
        df1 = _fetch_all_pages(session, url1, team_code, season)
        df2 = _fetch_all_pages(session, url2, team_code, season)
        ids1 = {}

    if df1.empty:
        raise ValueError(f"{season}시즌 {team} 투수 데이터 수집 실패")

    df1 = df1.rename(columns={"팀명": "팀"})
    df2 = df2.rename(columns={"팀명": "팀"})

    drop2 = [c for c in ["순위", "ERA", "팀"] if c in df2.columns]
    df2_clean = df2.drop(columns=drop2, errors="ignore").drop_duplicates(subset=["선수명"])
    df1_clean = df1.drop_duplicates(subset=["선수명"])
    df = pd.merge(df1_clean, df2_clean, on="선수명", how="left")

    for col in list(df.columns):
        for suffix in ["_x", "_y"]:
            if col.endswith(suffix):
                base = col[:-2]
                if base not in df.columns:
                    df = df.rename(columns={col: base})
                else:
                    df = df.drop(columns=[col])

    if team:
        df["팀"] = team
    elif "팀" not in df.columns:
        df["팀"] = ""
    df["시즌"] = season
    df = _to_numeric(df, exclude=["선수명", "팀", "시즌", "순위"])
    df = df.drop(columns=["순위"], errors="ignore")

    # 최소 이닝 필터 ('180 2/3' 또는 '5.2' 형식 모두 처리)
    if "IP" in df.columns:
        def ip_to_f(v):
            v = str(v).strip()
            try:
                if " " in v and "/" in v:
                    parts = v.split(); num, den = parts[1].split("/")
                    return int(parts[0]) + int(num) / int(den)
                f = float(v); return int(f) + round((f - int(f)) * 10) / 3
            except Exception:
                return 0
        ip_float = df["IP"].apply(ip_to_f)
        df = df[ip_float >= 0.1].reset_index(drop=True)

    print(f"  → {len(df)}명 투수 수집 완료")
    if return_ids:
        return df, ids1
    return df
