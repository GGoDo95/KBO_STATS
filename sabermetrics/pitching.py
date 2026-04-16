"""
투수 세이버매트릭스 지표 계산 모듈.

계산 지표:
- FIP    : 수비 독립 평균자책점 (투수 본인 책임 실점)
- xFIP   : 기대 FIP (리그 평균 홈런/플라이볼 비율 사용)
- ERA+   : 리그/파크 보정 ERA
- K/9    : 9이닝당 탈삼진
- BB/9   : 9이닝당 볼넷
- K/BB   : 탈삼진/볼넷 비율
- WHIP   : 이닝당 출루 허용
- pWAR   : 투수 WAR (FIP 기반)
"""

import pandas as pd
from config import FIP_CONSTANT, LEAGUE_ERA, PARK_FACTORS, DEFAULT_PARK_FACTOR

# 리그 평균 홈런/플라이볼 비율 (KBO 추정)
LEAGUE_HR_FB_RATE = 0.115

# 플라이볼 비율 추정 (FO 데이터 없을 때 AB 기반 근사)
# 실제로는 Statcast/트래킹 데이터가 필요하지만, KBO는 제한적이라 추정 사용
ESTIMATED_FB_RATE = 0.33  # 타수의 약 33%가 플라이볼로 추정

# 대체 수준 투수 ERA 기준 (5.00 ERA 수준)
REPLACEMENT_ERA = 5.00
RUNS_PER_WIN = 10.0


def _ip_to_float(ip_series: pd.Series) -> pd.Series:
    """
    이닝 표기를 소수로 변환.
    '5.2'  → 5 + 2/3 = 5.667  (statiz 방식)
    '5 2/3'→ 5 + 2/3 = 5.667  (KBO 공식 방식)
    """
    def convert(val):
        val = str(val).strip()
        try:
            # '180 2/3' 또는 '5 1/3' 형식
            if " " in val and "/" in val:
                parts = val.split()
                full = int(parts[0])
                num, den = parts[1].split("/")
                return full + int(num) / int(den)
            # '5.2' 형식
            f = float(val)
            full = int(f)
            outs = round((f - full) * 10)
            return full + outs / 3
        except (ValueError, TypeError, IndexError):
            return float("nan")

    return ip_series.apply(convert)


def calc_fip(df: pd.DataFrame, ip_float: pd.Series) -> pd.Series:
    """
    FIP = (13*HR + 3*(BB+HBP) - 2*K) / IP + FIP_constant

    수비와 무관하게 투수 본인의 책임인 이벤트만으로 계산.
    홈런 > 볼넷/사구 > 탈삼진 순으로 가중.
    """
    hbp = df.get("HBP", pd.Series(0, index=df.index))
    numerator = 13 * df["HR"] + 3 * (df["BB"] + hbp) - 2 * df["SO"]
    fip = numerator / ip_float.replace(0, float("nan")) + FIP_CONSTANT
    return fip.round(2)


def calc_xfip(df: pd.DataFrame, ip_float: pd.Series) -> pd.Series:
    """
    xFIP = (13*(FB*리그HR/FB율) + 3*(BB+HBP) - 2*K) / IP + FIP_constant

    FIP에서 홈런 대신 플라이볼에 리그 평균 HR/FB 비율을 적용.
    홈런 운을 제거해 투수의 진짜 실력에 더 가까운 지표.
    플라이볼 데이터가 없어 AB * 추정비율로 근사.
    """
    hbp = df.get("HBP", pd.Series(0, index=df.index))
    # 플라이볼 수 추정 (트래킹 데이터 없음)
    estimated_fb = df["AB"] * ESTIMATED_FB_RATE if "AB" in df.columns else df["HR"] / LEAGUE_HR_FB_RATE
    expected_hr = estimated_fb * LEAGUE_HR_FB_RATE

    numerator = 13 * expected_hr + 3 * (df["BB"] + hbp) - 2 * df["SO"]
    xfip = numerator / ip_float.replace(0, float("nan")) + FIP_CONSTANT
    return xfip.round(2)


def calc_era_plus(df: pd.DataFrame) -> pd.Series:
    """
    ERA+ = (리그평균ERA / ERA) * 파크팩터 * 100

    100이 리그 평균. 높을수록 좋음.
    잠실 구장의 타자 친화적 환경(파크팩터)을 보정.
    """
    era = df["ERA"].replace(0, float("nan"))
    pf = df["팀"].map(PARK_FACTORS).fillna(DEFAULT_PARK_FACTOR) if "팀" in df.columns else DEFAULT_PARK_FACTOR
    era_plus = (LEAGUE_ERA / era) * (1 / pf) * 100
    return era_plus.round(1)


def calc_k9(df: pd.DataFrame, ip_float: pd.Series) -> pd.Series:
    """K/9 = (탈삼진 / IP) * 9"""
    return (df["SO"] / ip_float.replace(0, float("nan")) * 9).round(2)


def calc_bb9(df: pd.DataFrame, ip_float: pd.Series) -> pd.Series:
    """BB/9 = (볼넷 / IP) * 9"""
    return (df["BB"] / ip_float.replace(0, float("nan")) * 9).round(2)


def calc_k_bb(df: pd.DataFrame) -> pd.Series:
    """K/BB = 탈삼진 / 볼넷. 볼넷이 0이면 NaN 처리."""
    return (df["SO"] / df["BB"].replace(0, float("nan"))).round(2)


def calc_whip(df: pd.DataFrame, ip_float: pd.Series) -> pd.Series:
    """WHIP = (볼넷 + 피안타) / IP"""
    return ((df["BB"] + df["H"]) / ip_float.replace(0, float("nan"))).round(3)


def calc_pitching_war(df: pd.DataFrame, fip: pd.Series, ip_float: pd.Series) -> pd.Series:
    """
    투수 WAR (FIP 기반)

    pWAR = (대체수준ERA - FIP) / 9 * IP / RUNS_PER_WIN * 파크팩터보정

    대체 수준 투수보다 얼마나 많은 실점을 막았는지를 승리로 환산.
    """
    pf = df["팀"].map(PARK_FACTORS).fillna(DEFAULT_PARK_FACTOR) if "팀" in df.columns else DEFAULT_PARK_FACTOR
    runs_saved = (REPLACEMENT_ERA - fip) / 9 * ip_float
    war = runs_saved / RUNS_PER_WIN * (1 / pf)
    return war.round(2)


MIN_IP_FOR_SABERS = 5.0  # 이 미만은 세이버 지표 NaN 처리

def calculate_all(df: pd.DataFrame) -> pd.DataFrame:
    """
    투수 DataFrame에 모든 세이버 지표를 추가해 반환.
    입력 DataFrame은 crawl_pitching()의 출력을 기대.
    """
    result = df.copy()
    ip_float = _ip_to_float(result["IP"])
    result["IP_float"] = ip_float

    fip = calc_fip(result, ip_float)
    result["FIP"]  = fip
    result["xFIP"] = calc_xfip(result, ip_float)
    result["ERA+"] = calc_era_plus(result)
    result["K/9"]  = calc_k9(result, ip_float)
    result["BB/9"] = calc_bb9(result, ip_float)
    result["K/BB"] = calc_k_bb(result)
    result["WHIP"] = calc_whip(result, ip_float)
    result["pWAR"] = calc_pitching_war(result, fip, ip_float)

    # 소표본 투수 세이버 지표 NaN 처리
    small = ip_float < MIN_IP_FOR_SABERS
    for col in ["FIP", "xFIP", "ERA+", "K/9", "BB/9", "K/BB", "WHIP", "pWAR"]:
        if col in result.columns:
            result.loc[small, col] = float("nan")

    return result
