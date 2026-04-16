SEASON = 2025
TEAM = ""  # 빈 문자열 = 전체 팀
SEASONS = [2023, 2024, 2025, 2026]  # 수집 대상 시즌

# 요청 헤더
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.koreabaseball.com/",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

CRAWL_DELAY = 1.5

# 시즌별 리그 상수 (시즌 종료 후 실제 값으로 보정 권장)
SEASON_CONFIGS = {
    2023: {
        "LINEAR_WEIGHTS": {"BB": 0.680, "HBP": 0.710, "1B": 0.870, "2B": 1.230, "3B": 1.560, "HR": 2.000},
        "WOBA_SCALE": 1.150,
        "LEAGUE_WOBA": 0.315,
        "LEAGUE_RUNS_PER_PA": 0.115,
        "FIP_CONSTANT": 3.15,
        "LEAGUE_ERA": 4.28,
        "LEAGUE_OBP": 0.325,
        "LEAGUE_SLG": 0.405,
    },
    2024: {
        "LINEAR_WEIGHTS": {"BB": 0.685, "HBP": 0.715, "1B": 0.875, "2B": 1.240, "3B": 1.570, "HR": 2.015},
        "WOBA_SCALE": 1.154,
        "LEAGUE_WOBA": 0.318,
        "LEAGUE_RUNS_PER_PA": 0.116,
        "FIP_CONSTANT": 3.12,
        "LEAGUE_ERA": 4.25,
        "LEAGUE_OBP": 0.328,
        "LEAGUE_SLG": 0.408,
    },
    2025: {
        "LINEAR_WEIGHTS": {"BB": 0.690, "HBP": 0.720, "1B": 0.880, "2B": 1.247, "3B": 1.578, "HR": 2.031},
        "WOBA_SCALE": 1.157,
        "LEAGUE_WOBA": 0.320,
        "LEAGUE_RUNS_PER_PA": 0.118,
        "FIP_CONSTANT": 3.10,
        "LEAGUE_ERA": 4.20,
        "LEAGUE_OBP": 0.330,
        "LEAGUE_SLG": 0.410,
    },
    2026: {  # 시즌 진행 중 — 종료 후 실제 리그 평균으로 보정 필요
        "LINEAR_WEIGHTS": {"BB": 0.690, "HBP": 0.720, "1B": 0.880, "2B": 1.247, "3B": 1.578, "HR": 2.031},
        "WOBA_SCALE": 1.157,
        "LEAGUE_WOBA": 0.320,
        "LEAGUE_RUNS_PER_PA": 0.118,
        "FIP_CONSTANT": 3.10,
        "LEAGUE_ERA": 4.20,
        "LEAGUE_OBP": 0.330,
        "LEAGUE_SLG": 0.410,
    },
}

def get_season_config(season: int) -> dict:
    return SEASON_CONFIGS.get(season, SEASON_CONFIGS[2025])

# 기본값 (하위 호환)
_default = SEASON_CONFIGS[2025]
LINEAR_WEIGHTS     = _default["LINEAR_WEIGHTS"]
WOBA_SCALE         = _default["WOBA_SCALE"]
LEAGUE_WOBA        = _default["LEAGUE_WOBA"]
LEAGUE_RUNS_PER_PA = _default["LEAGUE_RUNS_PER_PA"]
FIP_CONSTANT       = _default["FIP_CONSTANT"]
LEAGUE_ERA         = _default["LEAGUE_ERA"]

# KBO 구장별 파크팩터 (1.00 = 중립, >1.00 = 타자 친화)
# 출처: 과거 시즌 기반 추정치 (매년 보정 필요)
PARK_FACTORS = {
    "LG":  1.05,  # 잠실 (두산 공동)
    "두산": 1.05, # 잠실
    "KT":  0.97,  # 수원
    "SSG": 1.02,  # 인천
    "NC":  0.96,  # 창원
    "KIA": 1.03,  # 광주
    "롯데": 1.04, # 부산
    "삼성": 0.97, # 대구
    "한화": 1.00, # 대전
    "키움": 1.01, # 고척
}
DEFAULT_PARK_FACTOR = 1.00

DB_PATH = "data/kbo_sabermetrics.db"
