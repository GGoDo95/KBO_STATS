"""
타자 세이버매트릭스 지표 계산 모듈.
BABIP, ISO, wOBA, wRC+, OPS+, bWAR
"""

import pandas as pd
from config import (
    LINEAR_WEIGHTS, WOBA_SCALE, LEAGUE_WOBA,
    LEAGUE_RUNS_PER_PA, PARK_FACTORS, DEFAULT_PARK_FACTOR,
)

POSITION_ADJUSTMENT = {
    "C": 12.5, "SS": 7.5, "2B": 2.5, "3B": 2.5, "CF": 2.5,
    "LF": -7.5, "RF": -7.5, "1B": -12.5, "DH": -17.5,
}
REPLACEMENT_LEVEL_WRCP = 47.0
RUNS_PER_WIN = 10.0

LEAGUE_OBP = 0.330
LEAGUE_SLG = 0.410


def _park_factor(df: pd.DataFrame) -> pd.Series:
    """팀 컬럼이 있으면 팀별 파크팩터, 없으면 기본값 반환."""
    if "팀" in df.columns:
        return df["팀"].map(PARK_FACTORS).fillna(DEFAULT_PARK_FACTOR)
    return pd.Series(DEFAULT_PARK_FACTOR, index=df.index)


def calc_babip(df):
    num = df["H"] - df["HR"]
    den = df["AB"] - df["SO"] - df["HR"] + df.get("SF", pd.Series(0, index=df.index))
    return (num / den.replace(0, float("nan"))).round(3)


def calc_iso(df):
    return (df["SLG"] - df["AVG"]).round(3)


def calc_woba(df):
    lw = LINEAR_WEIGHTS
    singles = df["H"] - df["2B"] - df["3B"] - df["HR"]
    ibbs = df.get("IBB", pd.Series(0, index=df.index))
    sf   = df.get("SF",  pd.Series(0, index=df.index))
    num = (
        (df["BB"] - ibbs) * lw["BB"]
        + df["HBP"] * lw["HBP"]
        + singles   * lw["1B"]
        + df["2B"]  * lw["2B"]
        + df["3B"]  * lw["3B"]
        + df["HR"]  * lw["HR"]
    )
    den = df["AB"] + df["BB"] - ibbs + sf + df["HBP"]
    return (num / den.replace(0, float("nan"))).round(3)


def calc_wrcp(df, woba):
    """팀별 파크팩터를 반영한 wRC+."""
    pf = _park_factor(df)
    wrc_per_pa = (woba - LEAGUE_WOBA) / WOBA_SCALE + LEAGUE_RUNS_PER_PA
    return ((wrc_per_pa / pf) / LEAGUE_RUNS_PER_PA * 100).round(1)


def calc_ops_plus(df):
    """팀별 파크팩터를 반영한 OPS+."""
    pf = _park_factor(df)
    return ((df["OBP"] / LEAGUE_OBP + df["SLG"] / LEAGUE_SLG - 1) / pf * 100).round(1)


def calc_batting_war(df, woba, wrcp):
    pf = _park_factor(df)
    offensive_runs = (wrcp - REPLACEMENT_LEVEL_WRCP) / 100 * df["PA"] * (LEAGUE_RUNS_PER_PA * pf)
    pos_runs = pd.Series(0.0, index=df.index)
    if "포지션" in df.columns:
        pos_runs = df["포지션"].map(POSITION_ADJUSTMENT).fillna(0.0)
    return ((offensive_runs + pos_runs) / RUNS_PER_WIN).round(2)


MIN_PA_FOR_SABERS = 20  # 이 미만은 세이버 지표 NaN 처리

def calculate_all(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    result["BABIP"] = calc_babip(result)
    result["ISO"]   = calc_iso(result)
    woba            = calc_woba(result)
    result["wOBA"]  = woba
    wrcp            = calc_wrcp(result, woba)
    result["wRC+"]  = wrcp
    result["OPS+"]  = calc_ops_plus(result)
    result["bWAR"]  = calc_batting_war(result, woba, wrcp)

    # 소표본 선수 세이버 지표 NaN 처리
    small = result["PA"] < MIN_PA_FOR_SABERS
    for col in ["BABIP", "wOBA", "wRC+", "OPS+", "bWAR", "ISO"]:
        if col in result.columns:
            result.loc[small, col] = float("nan")

    return result
