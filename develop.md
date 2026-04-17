# KBO Sabermetrics — 개발 현황 문서

> 최종 업데이트: 2026-04-17
> 이 문서는 현재 구현된 전체 코드베이스를 기술한다.

---

## 1. 프로젝트 개요

**KBO Sabermetrics**는 한국 프로야구(KBO) 선수들의 데이터를 크롤링하여 세이버메트릭스 지표를 계산하고, 정적 HTML 사이트 및 Streamlit 대시보드로 제공하는 분석 플랫폼이다.

### 주요 기능
- **자동 데이터 수집**: KBO 공식 사이트, statiz.co.kr, 나무위키에서 타자/투수 스탯과 선수 정보 크롤링
- **세이버메트릭스 지표 계산**: BABIP, ISO, wOBA, wRC+, FIP, xFIP, ERA+, bWAR, pWAR 등 22개 지표
- **다중 시즌 지원**: 2023~2026 시즌 자동 수집 및 비교 분석
- **정적 웹사이트**: PWA 기능이 있는 GitHub Pages 배포용 HTML 생성
- **Streamlit 대시보드**: 인터랙티브 필터 및 차트 제공
- **선수 프로필 통합**: 사진, 신상정보, 등장곡/응원가 통합 저장

---

## 2. 디렉토리 구조

```
kbo-sabermetrics/
├── main.py                    # 메인 실행 스크립트 (크롤링 → 계산 → 저장)
├── config.py                  # 설정: 리그 상수, 파크팩터, 선형가중치
├── build_site.py              # 정적 HTML 생성기 (docs/index.html 생성)
├── update_music.py            # 나무위키 등장곡/응원가 전체 수집
├── update_profiles.py         # 선수 프로필 재수집 스크립트
├── requirements.txt           # Python 의존성
│
├── crawler/
│   ├── __init__.py
│   ├── kbo_crawler.py         # KBO 공식 홈페이지 크롤러
│   ├── statiz_crawler.py      # statiz.co.kr 로그인 크롤러
│   └── namu_crawler.py        # 나무위키 Playwright 크롤러
│
├── sabermetrics/
│   ├── __init__.py
│   ├── batting.py             # 타자 세이버 지표 계산
│   └── pitching.py            # 투수 세이버 지표 계산
│
├── database/
│   ├── __init__.py
│   └── db.py                  # SQLite 저장/로드 모듈
│
├── web/
│   └── app.py                 # Streamlit 대시보드
│
├── docs/
│   ├── index.html             # 정적 웹사이트 (build_site.py로 생성)
│   ├── manifest.json          # PWA 매니페스트
│   ├── sw.js                  # 서비스 워커
│   └── icons/                 # PWA 아이콘
│
└── data/                      # 런타임 생성
    ├── kbo_sabermetrics.db    # SQLite DB
    ├── *_batting.csv          # 타자 CSV (시즌별)
    ├── *_pitching.csv         # 투수 CSV (시즌별)
    └── namu_music.json        # 등장곡/응원가 캐시
```

---

## 3. 실행 방법

```bash
# 전체 시즌 크롤링 → 계산 → DB 저장 → CSV 백업
python main.py

# 특정 팀만 (예: LG)
python main.py --team LG

# 특정 시즌만
python main.py --seasons 2025 2026

# 강제 재크롤링 (기존 DB 무시)
python main.py --force

# 정적 HTML 생성 (GitHub Pages 배포용)
python build_site.py

# Streamlit 대시보드
streamlit run web/app.py

# 나무위키 등장곡 수집 + HTML 재빌드
python update_music.py

# 선수 프로필 재수집 + HTML 재빌드
python update_profiles.py
```

### CLI 인자 명세

| 인자 | 유형 | 설명 |
|------|------|------|
| `--team` | str | 팀 코드 (빈값=전체) |
| `--seasons` | list[int] | 수집 시즌 복수 지정 |
| `--force` | flag | 기존 DB 무시 강제 재크롤링 |

---

## 4. 데이터 파이프라인 흐름

```
1. CRAWLING
   kbo_crawler.py : Basic1 + Basic2 병합 (ASP.NET 3단계 POST)
   statiz_crawler.py : 로그인 세션 후 추가 스탯 (선택)
   namu_crawler.py : Playwright로 등장곡/응원가
   kbo_crawler.py : player_id 추출 → 프로필 크롤링

2. TRANSFORMATION
   컬럼명 통일 (팀명→팀, 선수→선수명)
   중복 제거 (선수명, 팀 기준)
   숫자 컬럼 float 변환
   IP 변환 ('180 2/3' → 180.667)

3. CALCULATION
   batting.py  : BABIP, ISO, wOBA, wRC+, OPS+, bWAR, BB%, K%, BB/K, wRAA
   pitching.py : FIP, xFIP, ERA+, K/9, BB/9, K/BB, WHIP, pWAR, LOB%, ERA-, FIP-, kwERA
   PA < 20 또는 IP < 5.0 → 세이버 지표 NaN

4. STORAGE
   SQLite 저장 (batting, pitching, profiles 테이블)
   CSV 백업 (data/YEAR_TEAM_batting.csv 등)

5. PUBLICATION
   build_site.py : docs/index.html 단일 파일 생성 (인라인 JSON)
   web/app.py    : Streamlit 대시보드 제공
```

---

## 5. 모듈별 상세 구현

### 5.1 config.py

**역할**: 전역 설정, 시즌별 리그 평균값, 파크팩터, 선형가중치 정의

#### 기본 상수

```python
SEASON = 2025
TEAM = ""
SEASONS = [2023, 2024, 2025, 2026]
CRAWL_DELAY = 1.5
DB_PATH = "data/kbo_sabermetrics.db"

HEADERS = {
    "User-Agent": "Mozilla/5.0 ... Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.koreabaseball.com/",
    "Accept-Language": "ko-KR,ko;q=0.9",
}
```

#### 시즌별 리그 상수 (SEASON_CONFIGS)

| 시즌 | BB | HBP | 1B | 2B | 3B | HR | WOBA_SCALE | LEAGUE_WOBA | R/PA | FIP_C | LEAGUE_ERA | LEAGUE_FIP | LEAGUE_OBP | LEAGUE_SLG |
|------|------|------|------|------|------|------|------|------|------|------|------|------|------|------|
| 2023 | 0.680 | 0.710 | 0.870 | 1.230 | 1.560 | 2.000 | 1.150 | 0.315 | 0.115 | 3.15 | 4.28 | 3.80 | 0.325 | 0.405 |
| 2024 | 0.685 | 0.715 | 0.875 | 1.240 | 1.570 | 2.015 | 1.154 | 0.318 | 0.116 | 3.12 | 4.25 | 3.75 | 0.328 | 0.408 |
| 2025 | 0.690 | 0.720 | 0.880 | 1.247 | 1.578 | 2.031 | 1.157 | 0.320 | 0.118 | 3.10 | 4.20 | 3.70 | 0.330 | 0.410 |
| 2026 | 0.690 | 0.720 | 0.880 | 1.247 | 1.578 | 2.031 | 1.157 | 0.320 | 0.118 | 3.10 | 4.20 | 3.70 | 0.330 | 0.410 |

*2026은 시즌 진행 중 — 종료 후 실제 리그 평균으로 보정 필요*

#### 구장별 파크팩터 (PARK_FACTORS)

| 팀 | 구장 | 파크팩터 |
|------|------|---------|
| LG | 잠실 | 1.05 |
| 두산 | 잠실 | 1.05 |
| KT | 수원 | 0.97 |
| SSG | 인천 | 1.02 |
| NC | 창원 | 0.96 |
| KIA | 광주 | 1.03 |
| 롯데 | 부산 | 1.04 |
| 삼성 | 대구 | 0.97 |
| 한화 | 대전 | 1.00 |
| 키움 | 고척 | 1.01 |

#### 함수

```python
def get_season_config(season: int) -> dict:
    # 특정 시즌 리그 상수 반환. 없으면 2025 기본값.
```

---

### 5.2 crawler/kbo_crawler.py

**역할**: KBO 공식 홈페이지 크롤링 (ASP.NET WebForms 3단계 POST)

#### 크롤링 방식

```
GET 초기 페이지
  → __VIEWSTATE, __VIEWSTATEGENERATOR, __EVENTVALIDATION 추출
POST 시즌 선택
  → ctl00$ContentPlaceHolder1$ddlSeason={season}
POST 팀 선택
  → ctl00$ContentPlaceHolder1$ddlTeam={team_code}
반복 POST 페이징
  → __EVENTTARGET = ctl00$ContentPlaceHolder1$grdData$btnNo{n}
```

#### 팀 코드 매핑

```python
KBO_TEAM_CODES = {
    "LG": "LG", "KT": "KT", "SSG": "SK", "NC": "NC",
    "두산": "OB", "KIA": "HT", "롯데": "LT", "삼성": "SS",
    "한화": "HH", "키움": "WO",
}
```

#### 내부 유틸 함수

| 함수 | 역할 |
|------|------|
| `_get_soup(session, url)` | GET + BeautifulSoup 파싱, CRAWL_DELAY 적용 |
| `_viewstate(soup)` | __VIEWSTATE 등 3개 필드 추출 |
| `_hidden_fields(soup)` | 숨겨진 폼 필드 {name: value} |
| `_sel_names(soup)` | select 요소 {name: element} |
| `_post(session, url, soup, eventtarget, extra)` | ASP.NET POST 요청 |
| `_parse_table(soup)` | class="tData01" 테이블 → DataFrame |
| `_parse_table_with_ids(soup)` | 테이블 + playerId 링크에서 ID 추출 |
| `_init_filters(session, url, team, season)` | GET → 시즌 POST → 팀 POST |
| `_next_page_target(soup, page)` | 페이징 div에서 다음 __EVENTTARGET |
| `_fetch_all_pages(session, url, team, season)` | 전 페이지 수집 |
| `_fetch_all_pages_with_ids(...)` | 전 페이지 + player_id 수집 |
| `_to_numeric(df, exclude)` | 문자 컬럼 숫자 변환 (실패율 50% 미만만) |

#### 공개 API

```python
def crawl_batting(team: str, season: int, return_ids: bool = False)
    # URL Basic1: G, PA, AB, R, H, 2B, 3B, HR, TB, RBI, SAC, SF
    # URL Basic2: BB, IBB, HBP, SO, GDP, SLG, OBP, OPS
    # 두 테이블 병합, MH/RISP/PH-BA 제거
    # return_ids=True → (DataFrame, {선수명: player_id})

def crawl_pitching(team: str, season: int, return_ids: bool = False)
    # URL Basic1: ERA, G, W, L, SV, HLD, IP, R, ER, BB, HBP, SO, HR
    # IP >= 0.1 필터

def crawl_player_profile(player_id: int, kind: str = "hitter") -> dict
    # URL: /Record/Player/{HitterDetail|PitcherDetail}/Basic.aspx?playerId={id}
    # .player_basic li 파싱 → {key: value}
    # 사진: img[src*="person"] 또는 img[src*="/photo"]

def crawl_all_profiles(player_id_map: dict, existing_ids: set = None) -> list
    # {선수명: (player_id, kind)} 입력
    # existing_ids 스킵, 신규만 크롤링
```

---

### 5.3 crawler/statiz_crawler.py

**역할**: statiz.co.kr 로그인 후 스탯 크롤링 (선택적)

#### 로그인 방식

```python
def _login(user_id: str, password: str) -> requests.Session:
    # 1. GET /member/?m=login (쿠키 획득)
    # 2. POST /member/handle.php {act: "loginJWT", userID, userPassword}
    # 3. GET / (로그아웃 링크 확인으로 성공 검증)
```

#### 팀 코드 매핑

```python
TEAM_MAP = {
    "LG": "LG", "KT": "KT", "SSG": "SSG", "NC": "NC",
    "두산": "OB", "KIA": "KIA", "롯데": "LT",
    "삼성": "SS", "한화": "HAN", "키움": "WO",
}
```

#### 공개 API

```python
def crawl_batting(team, season, user_id=None, password=None) -> DataFrame
    # 환경변수 STATIZ_ID, STATIZ_PW 사용
    # PA >= 10 필터

def crawl_pitching(team, season, user_id=None, password=None) -> DataFrame
    # IP >= 5 필터 (소수 변환)
```

---

### 5.4 crawler/namu_crawler.py

**역할**: 나무위키에서 등장곡/응원가 크롤링 (Playwright 사용)

#### Playwright 사용 이유

나무위키는 JavaScript 렌더링 + 각주 동적 처리 필요. `wait_for_timeout(3000)`으로 JS 안정화.

#### 음악 추출 알고리즘 (4가지 형식)

```
형식 A: 등장시 : Artist - Song         (한 줄)
형식 B: 등장시\n:\nArtist\n - Song     (아티스트·곡명 분리)
형식 C: 등장시\n:\nArtist\n - \nSong   (각각 분리)
형식 D: 등장곡 (\nArtist\n - \nSong)   (KIA 형식, 괄호)
```

#### 팀별 나무위키 URL

```python
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
```

#### 선수명 추출 패턴 (3가지)

```
형식 A: '문보경(No.2)'  → '문보경'
형식 B: 'No.25 김형준' → '김형준'
형식 C: '박성한 (No.2)' → '박성한'
```

#### 주요 함수

| 함수 | 역할 |
|------|------|
| `_fetch_page_html(url)` | Playwright JS 렌더링 HTML 반환 |
| `_player_name_from_span(span_id)` | span id → 선수명 추출 |
| `_content_div(heading)` | 헤딩 다음 본문 div 탐색 |
| `_clean(t)` | 각주, 특수괄호 제거 |
| `_is_section(t)` | 섹션 헤더 여부 |
| `_is_lyric(t)` | 가사 여부 (한글 어절 3개 이상 + 길이 10자 초과) |
| `_extract_music(lines, keys)` | 줄 목록에서 음악 정보 추출 |
| `_format_song(first, rest)` | 'Artist - Song' 형태로 정규화 |
| `_strip_lyrics(text)` | 가사 부분 제거 |
| `parse_team_music(html)` | HTML → {선수명: {등장곡, 응원가}} |
| `crawl_all_teams_music(delay=2.0)` | 전체 10팀 순회 크롤링 |

---

### 5.5 sabermetrics/batting.py

**역할**: 타자 세이버메트릭스 지표 계산

#### 상수

```python
POSITION_ADJUSTMENT = {
    "C": 12.5, "SS": 7.5, "2B": 2.5, "3B": 2.5, "CF": 2.5,
    "LF": -7.5, "RF": -7.5, "1B": -12.5, "DH": -17.5,
}
REPLACEMENT_LEVEL_WRCP = 47.0
RUNS_PER_WIN = 10.0
MIN_PA_FOR_SABERS = 20
```

#### 파크팩터 적용

```python
def _park_factor(df) -> pd.Series:
    # 팀 컬럼 → PARK_FACTORS 매핑. 없으면 DEFAULT_PARK_FACTOR(1.00)
```

#### 타자 지표 공식

| 지표 | 공식 | 의미 |
|------|------|------|
| **BABIP** | (H - HR) / (AB - SO - HR + SF) | 인플레이 안타율 |
| **ISO** | SLG - AVG | 순수 장타력 |
| **wOBA** | ((BB-IBB)×lw_BB + HBP×lw_HBP + 1B×lw_1B + 2B×lw_2B + 3B×lw_3B + HR×lw_HR) / (AB + BB - IBB + SF + HBP) | 가중 출루율 |
| **wRC+** | ((wOBA - 리그wOBA) / WOBA_SCALE + 리그R/PA) / (리그R/PA × PF) × 100 | 공격생산성 (100=평균) |
| **OPS+** | (OBP / 리그OBP + SLG / 리그SLG - 1) / PF × 100 | 파크보정 OPS |
| **bWAR** | ((wRC+ - 47) / 100 × PA × 리그R/PA × PF + 포지션조정) / 10 | 타자 종합 가치 |
| **BB%** | BB / PA × 100 | 볼넷 비율 |
| **K%** | SO / PA × 100 | 삼진 비율 |
| **BB/K** | BB / SO | 볼넷 대 삼진 |
| **wRAA** | (wOBA - 리그wOBA) / WOBA_SCALE × PA | 대체선수 대비 추가 득점 |

#### calculate_all(df, season) 반환 컬럼

BABIP, ISO, wOBA, wRC+, OPS+, bWAR, BB%, K%, BB/K, wRAA
PA < 20 → 위 컬럼 모두 NaN

---

### 5.6 sabermetrics/pitching.py

**역할**: 투수 세이버메트릭스 지표 계산

#### 상수

```python
LEAGUE_HR_FB_RATE = 0.115     # 리그 평균 홈런/플라이볼 비율
ESTIMATED_FB_RATE = 0.33      # 추정 플라이볼 비율 (AB의 33%)
REPLACEMENT_ERA = 5.00
RUNS_PER_WIN = 10.0
MIN_IP_FOR_SABERS = 5.0
```

#### IP 변환

```python
def _ip_to_float(ip_series) -> pd.Series:
    # '180 2/3' → 180.667
    # '5 1/3'   → 5.333
    # '5.2' (statiz 형식) → 5.667 (소수 이하는 아웃수)
```

#### 투수 지표 공식

| 지표 | 공식 | 의미 |
|------|------|------|
| **FIP** | (13×HR + 3×(BB+HBP) - 2×SO) / IP + FIP_CONSTANT | 수비무관 자책점 |
| **xFIP** | FIP but expected_HR = AB × 0.33 × 0.115 | 홈런 운 제거 FIP |
| **ERA+** | (리그ERA / ERA) × (1 / PF) × 100 | 파크보정 ERA (100=평균) |
| **K/9** | SO / IP × 9 | 9이닝당 탈삼진 |
| **BB/9** | BB / IP × 9 | 9이닝당 볼넷 |
| **K/BB** | SO / BB | 탈삼진 대 볼넷 |
| **WHIP** | (BB + H) / IP | 이닝당 출루 허용 |
| **pWAR** | (5.00 - FIP) / 9 × IP / 10 / PF | 투수 종합 가치 |
| **LOB%** | (H + BB + HBP - R) / (H + BB + HBP - 1.4×HR) × 100 | 잔루 비율 |
| **ERA-** | ERA / 리그ERA × 100 | 파크보정 ERA 지수 (낮을수록 좋음) |
| **FIP-** | FIP / 리그FIP × 100 | 파크보정 FIP 지수 (낮을수록 좋음) |
| **kwERA** | 3.00 + (BB/9 - K/9) × 0.27 | K·BB 기반 간단 추정 ERA |

#### calculate_all(df, season) 반환 컬럼

FIP, xFIP, ERA+, K/9, BB/9, K/BB, WHIP, pWAR, LOB%, ERA-, FIP-, kwERA
IP < 5.0 → 위 컬럼 모두 NaN

---

### 5.7 database/db.py

**역할**: SQLite 데이터베이스 저장/로드

#### 테이블 스키마 (SQL)

```sql
CREATE TABLE batting (
    시즌 INTEGER, 선수명 TEXT, 팀 TEXT,
    G INTEGER, PA INTEGER, AB INTEGER, R INTEGER, H INTEGER,
    "2B" INTEGER, "3B" INTEGER, HR INTEGER, TB REAL,
    RBI INTEGER, BB INTEGER, IBB INTEGER, HBP INTEGER, SO INTEGER,
    SAC INTEGER, SF INTEGER, GDP INTEGER,
    AVG REAL, OBP REAL, SLG REAL, OPS REAL,
    BABIP REAL, ISO REAL, wOBA REAL, "wRC+" REAL, "OPS+" REAL, bWAR REAL,
    "BB%" REAL, "K%" REAL, "BB/K" REAL, wRAA REAL
);

CREATE TABLE pitching (
    시즌 INTEGER, 선수명 TEXT, 팀 TEXT,
    G INTEGER, W INTEGER, L INTEGER, SV INTEGER, HLD INTEGER,
    IP TEXT, IP_float REAL,
    ERA REAL, R INTEGER, ER INTEGER,
    BB INTEGER, HBP INTEGER, SO INTEGER, HR INTEGER,
    FIP REAL, xFIP REAL, "ERA+" REAL,
    "K/9" REAL, "BB/9" REAL, "K/BB" REAL, WHIP REAL, pWAR REAL,
    "LOB%" REAL, "ERA-" REAL, "FIP-" REAL, kwERA REAL
);

CREATE TABLE profiles (
    player_id INTEGER PRIMARY KEY,
    선수명 TEXT,
    data TEXT  -- JSON: {player_id, kind, 신장/체중, 생년월일, 사진, 포지션, 입단년도, 연봉, ...}
);
```

#### 공개 API

| 함수 | 반환 | 설명 |
|------|------|------|
| `save_batting(df, season)` | None | 시즌 삭제 후 INSERT |
| `save_pitching(df, season)` | None | 시즌 삭제 후 INSERT |
| `load_batting(season=None)` | DataFrame | None=전체 시즌 |
| `load_pitching(season=None)` | DataFrame | None=전체 시즌 |
| `table_exists(table)` | bool | sqlite_master 확인 |
| `season_exists(table, season)` | bool | 특정 시즌 존재 여부 |
| `save_profiles(profiles)` | None | INSERT OR REPLACE |
| `load_profiles()` | dict | {선수명: {프로필}} |
| `get_existing_profile_ids()` | set | 저장된 player_id 집합 |

---

### 5.8 main.py

**역할**: 크롤링 → 계산 → 저장 메인 파이프라인

#### 함수 구조

```python
def _crawl_all_teams(season: int, kind: str, return_ids: bool = False)
    # 10팀 순회, 개별 팀 실패해도 계속 진행
    # kind = "batting" | "pitching"

def run_season(season: int, team: str = "", force_crawl: bool = False)
    # 1. 타자 크롤링 → 세이버 계산 → DB 저장 → CSV 백업
    # 2. 투수 크롤링 → 세이버 계산 → DB 저장 → CSV 백업
    # 3. 신규 선수 프로필 크롤링 → DB 저장
    # force=False: DB에 해당 시즌 있으면 스킵
    # 반환: (타자 DataFrame, 투수 DataFrame)

def run(seasons: list = None, team: str = "", force_crawl: bool = False)
    # 다중 시즌 순차 처리 + Top 5 출력
    # 반환: (전체 타자 DataFrame, 전체 투수 DataFrame)
```

#### CSV 파일명 규칙

```
data/{season}_{팀 또는 "전체"}_batting.csv
data/{season}_{팀 또는 "전체"}_pitching.csv
```

---

### 5.9 build_site.py

**역할**: CSV + DB → 단일 docs/index.html 생성

#### 데이터 로드 방식

```python
bat_files = sorted(data_dir.glob("*전체*batting.csv"))
pit_files = sorted(data_dir.glob("*전체*pitching.csv"))
bat = pd.concat([pd.read_csv(f) for f in bat_files], ignore_index=True)
pit = pd.concat([pd.read_csv(f) for f in pit_files], ignore_index=True)

# 프로필 + 등장곡 병합
profiles = db.load_profiles()
music = json.loads(Path("data/namu_music.json").read_text(encoding="utf-8"))
for name, mdata in music.items():
    if name in profiles:
        profiles[name].update(mdata)
```

#### 출력 컬럼 목록

```python
BAT_COLS = [
    "시즌", "선수명", "팀", "G", "PA", "AVG", "HR", "RBI", "R",
    "BB", "SO", "OBP", "SLG", "OPS",
    "BABIP", "ISO", "wOBA", "wRC+", "OPS+", "bWAR",
    "BB%", "K%", "BB/K", "wRAA"
]

PIT_COLS = [
    "시즌", "선수명", "팀", "G", "W", "L", "SV", "HLD",
    "IP", "IP_float", "ERA", "WHIP", "SO", "BB", "HR",
    "FIP", "xFIP", "ERA+", "K/9", "BB/9", "K/BB", "pWAR",
    "LOB%", "ERA-", "FIP-", "kwERA"
]

BAT_SABER = ["BABIP", "ISO", "wOBA", "wRC+", "OPS+", "bWAR", "BB%", "K%", "BB/K", "wRAA"]
PIT_SABER = ["FIP", "xFIP", "ERA+", "K/9", "BB/9", "K/BB", "pWAR", "LOB%", "ERA-", "FIP-", "kwERA"]
```

#### JavaScript 전역 변수 (인라인 JSON)

| 변수 | 내용 |
|------|------|
| `BAT_DATA` | 타자 JSON 배열 |
| `PIT_DATA` | 투수 JSON 배열 |
| `TEAMS` | 팀 목록 |
| `SEASONS` | 시즌 목록 |
| `TC` | 팀 색상 {팀: 색코드} |
| `BAT_SABER` | 타자 세이버 컬럼명 배열 |
| `PIT_SABER` | 투수 세이버 컬럼명 배열 |
| `PROFILES` | 선수 프로필 dict |

#### JavaScript 함수 목록

| 함수 | 역할 |
|------|------|
| `calcPct(val, allVals, higherIsBetter)` | 퍼센타일 계산 |
| `pctColor(p)` | 퍼센타일 → 색상 (#1a6bc4 / #adb5bd / #dc3545) |
| `teamBadge(t)` | 팀 배지 HTML |
| `playerLink(name)` | 선수 클릭 링크 HTML |
| `openPage(name)` | 선수 상세 페이지 열기 (history.pushState) |
| `closePage()` | 뒤로가기 (history.back) |
| `_doClosePage()` | 실제 페이지 닫기 (popstate 이벤트 처리) |
| `filterData(data, season, team, minPA, minIP)` | 필터 적용 |
| `initBat(data)` | 타자 DataTable 초기화 |
| `initPit(data)` | 투수 DataTable 초기화 |
| `initTeam(batData, pitData)` | 리그 종합 DataTable |
| `toggleBatSaber()` | 타자 세이버 지표 컬럼 토글 |
| `togglePitSaber()` | 투수 세이버 지표 컬럼 토글 |
| `renderBatCharts(data)` | 타자 차트 (wRC+ Top20, OBP vs ISO, bWAR Top15) |
| `renderPitCharts(data)` | 투수 차트 (FIP vs xFIP, ERA vs FIP, pWAR Top15) |
| `renderTeamCharts(bat, pit)` | 팀 차트 (팀별 WAR, FIP vs wRC+) |
| `applyFilters()` | 전체 필터 재적용 + 차트 갱신 |
| `showTab(tab)` | 탭 전환 (bat/pit/team) |

#### localStorage 키

| 키 | 역할 |
|------|------|
| `kbo_season` | 선택된 시즌 |
| `kbo_team` | 선택된 팀 |
| `kbo_tab` | 활성 탭 |
| `kbo_player` | 마지막 열린 선수 이름 |

#### 외부 라이브러리 (CDN)

- Bootstrap 5.3.2
- DataTables 1.13.6
- Plotly.js (최신)
- jQuery 3.7.1 (DataTables 의존)

#### PWA 지원

- `docs/manifest.json`: 앱 이름, 아이콘, theme_color 정의
- `docs/sw.js`: 서비스 워커 (오프라인 캐시)
- `docs/icons/`: PWA 아이콘 이미지

---

### 5.10 update_music.py

```python
def main():
    music = crawl_all_teams_music(delay=2.0)    # 10팀 나무위키 크롤링
    OUT.write_text(json.dumps(music, ensure_ascii=False, indent=2))
    subprocess.run(["python", "build_site.py"], check=True)
```

---

### 5.11 update_profiles.py

```python
def main():
    entries = load_all_player_ids()  # DB에서 (player_id, kind) 목록
    updated = []
    for pid, kind in entries:
        p = crawl_player_profile(pid, kind)
        if p:
            updated.append(p)
    save_profiles(updated)
    subprocess.run(["python", "build_site.py"], check=True)
```

---

### 5.12 web/app.py

**역할**: Streamlit 인터랙티브 대시보드

```
사이드바:
  - 시즌 다중선택 + "데이터 수집" 버튼
  - 지표 설명 마크다운

탭 1 [타자 분석]:
  - 최소 PA 슬라이더
  - 정렬 기준 선택 (wRC+, bWAR, wOBA, OPS+, ISO, BABIP)
  - 세이버 지표 토글
  - DataFrame + 차트 3개 (wRC+ Top20, OBP vs ISO, bWAR Top15)

탭 2 [투수 분석]:
  - 최소 IP 슬라이더
  - 정렬 기준 선택 (pWAR, FIP, ERA+, K/9, WHIP)
  - 세이버 지표 토글
  - DataFrame + 차트 3개 (K/9 vs BB/9, ERA vs FIP, pWAR Top15)

탭 3 [리그 종합]:
  - 팀별 집계 (타자WAR, 투수WAR, 총WAR, 평균wRC+, 평균FIP)
  - 차트 2개 (팀별 총WAR, FIP vs wRC+ 산점도)
```

```python
@st.cache_data(ttl=300)
def load_data() -> (pd.DataFrame, pd.DataFrame):
    # DB 없으면 CSV fallback (*_전체_batting.csv)
```

---

## 6. 크롤링 대상 및 수집 데이터 요약

| 사이트 | 인증 | 방식 | 수집 데이터 |
|------|------|------|------|
| koreabaseball.com | 없음 | ASP.NET POST 3단계 | 타자/투수 기본 스탯, 선수 프로필 |
| statiz.co.kr | 로그인 필요 (STATIZ_ID, STATIZ_PW) | 세션 GET | 타자/투수 기본 스탯 (보완용) |
| namu.wiki | 없음 | Playwright (JS 렌더링) | 등장곡, 응원가 (10팀) |

---

## 7. 외부 의존성

```
requests>=2.31.0
beautifulsoup4>=4.12.3
pandas>=2.2.2
streamlit>=1.35.0
plotly>=5.22.0
lxml

# 별도 설치
pip install playwright
python -m playwright install chromium
```

---

## 8. 알려진 제약사항

### 데이터 정확도
1. **파크팩터**: 과거 시즌 기반 추정치. 매년 보정 필요.
2. **리그 상수**: 시즌 종료 전에는 전년도 값 사용. 시즌 종료 후 수동 업데이트 필요.
3. **선형가중치**: KBO 근사값 (실제 회귀 계산 아님).

### 크롤링 제약
1. **CRAWL_DELAY 1.5초**: 서버 부하 방지. 임의 제거 금지.
2. **나무위키 Playwright**: chromium 초기 설치 필요 (~150MB).
3. **KBO ViewState**: 세션 만료 시 재시도 필요.

### 계산 주의사항
1. **최소 규정**: PA < 20(타자), IP < 5.0(투수) → 세이버 지표 NaN.
2. **0 제수**: `.replace(0, float("nan"))` 사용.
3. **포지션 정보**: 프로필 미수집 선수 → 포지션 조정값 0 적용.

### 배포 유의사항
1. **단일 HTML 크기**: 4시즌 누적 시 20MB+ 가능. 향후 외부 JSON 분리 권장.
2. **GitHub Pages 100MB 제한**: CSV, DB 파일 대용량 주의.
3. **namu_music.json**: 로컬 캐시 파일 참조. 정기 업데이트 필요.
