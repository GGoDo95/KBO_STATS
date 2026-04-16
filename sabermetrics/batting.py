"""
타자 세이버매트릭스 지표 계산 모듈.
BABIP, ISO, wOBA, wRC+, OPS+, bWAR
"""

import pandas as pd
from config import get_season_config, PARK_FACTORS, DEFAULT_PARK_FACTOR

POSITION_ADJUSTMENT = {
    "C": 12.5, "SS": 7.5, "2B": 2.5, "3B": 2.5, "CF": 2.5,
    "LF": -7.5, "RF": -7.5, "1B": -12.5, "DH": -17.5,
}
REPLACEMENT_LEVEL_WRCP = 47.0
RUNS_PER_WIN = 10.0


def _park_factor(df: pd.DataFrame) -> pd.Series:
    if "팀" in df.columns:
        return df["팀"].map(PARK_FACTORS).fillna(DEFAULT_PARK_FACTOR)
    return pd.Series(DEFAULT_PARK_FACTOR, index=df.index)


def calc_babip(df):
    num = df["H"] - df["HR"]
    den = df["AB"] - df["SO"] - df["HR"] + df.get("SF", pd.Series(0, index=df.index))
    return (num / den.replace(0, float("nan"))).round(3)


def calc_iso(df):
    return (df["SLG"] - df["AVG"]).round(3)


def calc_woba(df, lw):
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


def calc_wrcp(df, woba, cfg):
    pf = _park_factor(df)
    wrc_per_pa = (woba - cfg["LEAGUE_WOBA"]) / cfg["WOBA_SCALE"] + cfg["LEAGUE_RUNS_PER_PA"]
    return ((wrc_per_pa / pf) / cfg["LEAGUE_RUNS_PER_PA"] * 100).round(1)


def calc_ops_plus(df, cfg):
    pf = _park_factor(df)
    return ((df["OBP"] / cfg["LEAGUE_OBP"] + df["SLG"] / cfg["LEAGUE_SLG"] - 1) / pf * 100).round(1)


def calc_batting_war(df, woba, wrcp, cfg):
    pf = _park_factor(df)
    offensive_runs = (wrcp - REPLACEMENT_LEVEL_WRCP) / 100 * df["PA"] * (cfg["LEAGUE_RUNS_PER_PA"] * pf)
    pos_runs = pd.Series(0.0, index=df.index)
    if "포지션" in df.columns:
        pos_runs = df["포지션"].map(POSITION_ADJUSTMENT).fillna(0.0)
    return ((offensive_runs + pos_runs) / RUNS_PER_WIN).round(2)


MIN_PA_FOR_SABERS = 20

def calculate_all(df: pd.DataFrame, season: int = 2025) -> pd.DataFrame:
    cfg = get_season_config(season)
    result = df.copy()
    result["BABIP"] = calc_babip(result)
    result["ISO"]   = calc_iso(result)
    woba            = calc_woba(result, cfg["LINEAR_WEIGHTS"])
    result["wOBA"]  = woba
    wrcp            = calc_wrcp(result, woba, cfg)
    result["wRC+"]  = wrcp
    result["OPS+"]  = calc_ops_plus(result, cfg)
    result["bWAR"]  = calc_batting_war(result, woba, wrcp, cfg)

    small = result["PA"] < MIN_PA_FOR_SABERS
    for col in ["BABIP", "wOBA", "wRC+", "OPS+", "bWAR", "ISO"]:
        if col in result.columns:
            result.loc[small, col] = float("nan")

    return result
