"""
나무위키 KBO 선수 등장곡/응원가 크롤러.
의존: playwright (pip install playwright && python -m playwright install chromium)
"""

import re
import time
import urllib.parse
from bs4 import BeautifulSoup

TEAM_WIKI_PAGES = {
    "LG":  "LG 트윈스/응원가/선수",
    "두산": "두산 베어스/응원가/선수",
    "KT":  "KT 위즈/응원가/선수",
    "SSG": "SSG 랜더스/응원가/선수",
    "NC":  "NC 다이노스/응원가/선수",
    "KIA": "KIA 타이거즈/응원가/선수",
    "롯데": "롯데 자이언츠/응원가/선수",
    "삼성": "삼성 라이온즈/응원가/선수",
    "한화": "한화 이글스/응원가/선수",
    "키움": "키움 히어로즈/응원가/선수",
}

_SECTION_KEYS = frozenset(["등장시", "등판시", "타석 등장시", "타격시", "응원가", "응원시", "안타시", "듣기", "등장곡", "응원곡"])


def _fetch_page_html(url: str, timeout: int = 30000) -> str:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        # JS 렌더링 대기
        page.wait_for_timeout(3000)
        html = page.content()
        browser.close()
    return html


def _content_div(h4):
    """h4에서 위로 올라가며 내용 있는 next_sibling 반환."""
    node = h4
    for _ in range(15):
        sib = node.find_next_sibling()
        if sib and sib.get_text(strip=True):
            return sib
        node = node.parent
        if node is None:
            break
    return None


def _clean(t: str) -> str:
    """각주·특수괄호·앞쪽 콜론 제거."""
    t = re.sub(r'\[\d+\]', '', t)
    t = re.sub(r'[〈〉《》<>]', '', t)
    t = re.sub(r'^[:：]\s*', '', t)
    return t.strip()


def _is_section(t: str) -> bool:
    return any(t == k or t.startswith(k + ':') or t.startswith(k + '：')
               or t.startswith(k + ' (')
               for k in _SECTION_KEYS)


def _is_lyric(t: str) -> bool:
    """가사 줄 여부: 한글 단어 3개 이상 + 길이 10자 초과."""
    return len(re.findall(r'[가-힣]{2,}', t)) >= 3 and len(t) > 10


def _extract_music(lines: list, keys: list) -> str:
    """
    줄 목록에서 key에 해당하는 'Artist - Song' 추출.

    나무위키 구조 (4가지):
      A) 등장시 : Artist - Song  (한 줄)
      B) 등장시\n:\nArtist\n - Song  (아티스트·곡명 분리)
      C) 등장시\n:\nArtist\n - \nSong  (아티스트·대시·곡명 각각 분리)
      D) 등장곡 (\nArtist\n - \nSong\n)  (KIA 형식, 괄호)
    """
    n = len(lines)
    for i, line in enumerate(lines):
        s = _clean(line)

        # 현재 줄이 키인지 확인 (e.g. '등장시' 또는 '등장시: Artist - Song')
        matched_key = None
        val_inline = ""
        for key in keys:
            if s == key:
                matched_key = key
                break
            if s.startswith(key + ':') or s.startswith(key + '：'):
                matched_key = key
                val_inline = re.split(r'[:：]', s, 1)[1].strip()
                break
            # KIA 형식: '등장곡 (Artist - Song)' 또는 '등장곡 (\nArtist\n...'
            if s.startswith(key + ' ('):
                matched_key = key
                # 괄호 안 인라인 내용 추출 시도
                inner = s[len(key):].strip()
                if inner.startswith('('):
                    inner = inner[1:]
                if inner.endswith(')'):
                    inner = inner[:-1]
                val_inline = inner.strip()
                break

        if matched_key is None:
            continue

        # 인라인 값이 있으면 바로 처리
        if val_inline:
            return _format_song(val_inline, lines[i+1:])

        # 다음 줄들에서 콜론 건너뛰기
        j = i + 1
        while j < n and _clean(lines[j]) in ('', ':', '：'):
            j += 1
        if j >= n:
            return ""

        return _format_song(_clean(lines[j]), lines[j+1:])

    return ""


def _format_song(first: str, rest: list) -> str:
    """
    first = 아티스트 혹은 'Artist - Song' 또는 '구단 자작곡'.
    rest  = 이후 줄들 (곡명·가사 포함).
    → 'Artist - Song' 형태로 반환.
    """
    if not first:
        return ""

    # 이미 'Artist - Song' 형태
    if ' - ' in first or ' – ' in first:
        return _finalize(first)

    # 다음 줄들에서 ' - Song' 또는 '-\nSong' 찾기
    artist = first
    song = ""
    k = 0
    while k < len(rest) and k < 8:
        line = rest[k]
        c = _clean(line)
        k += 1

        if not c or c in (':', '：', ')', '（', '）'):
            continue
        if _is_section(c):
            break

        # '- Song' 패턴 (대시로 시작)
        if re.match(r'^[-–]', c):
            after_dash = re.sub(r'^[-–]\s*', '', c).strip()
            # KIA 형식: ' - Song)' → 닫는 괄호 제거
            after_dash = after_dash.rstrip(')）').strip()
            if after_dash:
                # 같은 줄에 곡명 있음: '- Mr. Chu' 등
                song = after_dash
            else:
                # 대시만 있음 → 다음 줄이 곡명
                while k < len(rest):
                    nc = _clean(rest[k])
                    k += 1
                    if not nc or nc in (':', '：', ')', '（', '）'):
                        continue
                    if _is_section(nc) or _is_lyric(nc):
                        break
                    song = nc.rstrip(')）').strip()
                    break
            break

        # 가사면 중단
        if _is_lyric(c):
            break

    result = f"{artist} - {song}" if song else artist
    return _finalize(result)


def _finalize(text: str) -> str:
    """최종 정리: 가사 제거, 길이 제한, 공백 정규화."""
    text = _clean(text)
    if not text:
        return ""

    # 무의미한 값 제거
    if text in ('→', '↑', '↓', '-', '–'):
        return ""

    # ' - ' 기준으로 artist/song 분리 후 각각 가사 제거
    if ' - ' in text:
        artist, _, rest = text.partition(' - ')
        song = _strip_lyrics(rest)
        if not song:
            return artist.strip()
        return f"{artist.strip()} - {song}"

    return _strip_lyrics(text)


def _strip_lyrics(text: str) -> str:
    """문자열에서 가사 부분을 제거하고 곡명만 반환."""
    text = text.strip()
    if len(text) <= 20:
        return text

    # 한글 어절 연속 카운트로 가사 시작점 감지
    words = text.split()
    kept = []
    kr_run = 0
    for w in words:
        is_kr = len(re.findall(r'[가-힣]{2,}', w)) > 0
        kr_run = (kr_run + 1) if is_kr else 0
        if kr_run >= 3:
            break
        kept.append(w)

    result = ' '.join(kept).rstrip('([（').strip()

    # 영어 전용 제목이 너무 길면 첫 의미 단위까지
    if len(result) > 50 and not re.search(r'[가-힣]', result):
        # 두 번째 괄호 앞에서 자름
        m = re.search(r'(?<=\))\s+\(', result)
        if m:
            result = result[:m.start()].strip()

    return result


# ──────────────────────────────────────────────────────────

def _player_name_from_span(span_id: str) -> str:
    """
    span id에서 선수명 추출.
    형식 A: '문보경(No.2)' → '문보경'
    형식 B: 'No.25 김형준'  → '김형준'
    형식 C: '박성한 (No.2)' → '박성한'
    """
    if not span_id:
        return ""
    # 형식 B: 'No.N 이름' 또는 'No.N. 이름'
    m = re.match(r'^No\.?\d+\.?\s+(.+)', span_id)
    if m:
        raw = m.group(1).strip()
        # 이름 뒤 괄호 제거
        raw = re.sub(r'\s*[\(（].*', '', raw).strip()
        return raw

    # 형식 A/C: '이름(No.N)' 또는 '이름 (No.N)'
    m = re.match(r'^([^\(（]*?)(?:\s*[\(（]|$)', span_id)
    if m:
        return m.group(1).strip()

    return span_id.strip()


def parse_team_music(html: str) -> dict:
    """
    /응원가/선수 HTML → {선수명: {"등장곡": "...", "응원가": "..."}}
    h4 / h3 / h5 모두 처리.
    """
    soup = BeautifulSoup(html, "html.parser")
    result = {}

    # h3/h4/h5 모두 순회 (팀마다 사용 헤딩 다름)
    for heading in soup.find_all(["h3", "h4", "h5"]):
        span = heading.find("span", id=True)
        if not span:
            continue

        span_id = span.get("id", "")
        name = _player_name_from_span(span_id)

        # 무효 필터
        if not name:
            continue
        if any(c in name for c in ['편집', '#', '.', '응원가', '등장곡', '투수', '타자', '공통', '현역', '은퇴']):
            continue
        # 한글 이름이 아닌 경우 스킵 (숫자나 영문만)
        if not re.search(r'[가-힣]', name):
            continue

        div = _content_div(heading)
        if not div:
            continue
        # 다음 섹션 헤딩 포함하면 content 아님
        if div.find(["h3", "h4", "h5"]):
            continue

        lines = [l for l in div.get_text(separator="\n").split("\n") if l.strip()]

        entrance = _extract_music(lines, ["등장시", "등판시", "타석 등장시", "등장곡"])
        cheer    = _extract_music(lines, ["타격시", "응원가", "응원시", "안타시"])

        entry = {}
        if entrance:
            entry["등장곡"] = entrance
        if cheer:
            entry["응원가"] = cheer
        if entry:
            result[name] = entry

    return result


def crawl_all_teams_music(delay: float = 2.0) -> dict:
    """전체 10팀 크롤링 → {선수명: {"등장곡": "...", "응원가": "..."}}"""
    all_music = {}
    base = "https://namu.wiki/w/"
    for team, title in TEAM_WIKI_PAGES.items():
        url = base + urllib.parse.quote(title)
        print(f"[나무위키] {team} 크롤링...")
        try:
            html = _fetch_page_html(url)
            music = parse_team_music(html)
            print(f"  {len(music)}명")
            all_music.update(music)
            time.sleep(delay)
        except Exception as e:
            print(f"  [오류] {team}: {e}")
    return all_music
