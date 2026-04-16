SEASON = 2025
TEAM = ""  # 빈 문자열 = 전체 팀

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

# 2025 KBO 리그 평균 선형 가중치 (시즌 종료 후 보정 권장)
LINEAR_WEIGHTS = {
    "BB":  0.690,
    "HBP": 0.720,
    "1B":  0.880,
    "2B":  1.247,
    "3B":  1.578,
    "HR":  2.031,
}

WOBA_SCALE       = 1.157
LEAGUE_WOBA      = 0.320   # 2025 리그 평균 추정
LEAGUE_RUNS_PER_PA = 0.118 # 리그 PA당 득점 추정
FIP_CONSTANT     = 3.10    # ERA - FIP_raw 리그 평균
LEAGUE_ERA       = 4.20    # 2025 리그 평균 ERA 추정

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
