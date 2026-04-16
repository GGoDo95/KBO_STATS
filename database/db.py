"""
SQLite 데이터베이스 저장/조회 모듈. 다중 시즌 지원.
"""

import sqlite3
import pandas as pd
from pathlib import Path
from config import DB_PATH


def _get_conn() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def save_batting(df: pd.DataFrame, season: int) -> None:
    with _get_conn() as conn:
        if table_exists("batting"):
            conn.execute("DELETE FROM batting WHERE 시즌 = ?", (season,))
            df.to_sql("batting", conn, if_exists="append", index=False)
        else:
            df.to_sql("batting", conn, if_exists="replace", index=False)
    print(f"[DB] 타자 {len(df)}명 저장 ({season}시즌) → {DB_PATH}")


def save_pitching(df: pd.DataFrame, season: int) -> None:
    with _get_conn() as conn:
        if table_exists("pitching"):
            conn.execute("DELETE FROM pitching WHERE 시즌 = ?", (season,))
            df.to_sql("pitching", conn, if_exists="append", index=False)
        else:
            df.to_sql("pitching", conn, if_exists="replace", index=False)
    print(f"[DB] 투수 {len(df)}명 저장 ({season}시즌) → {DB_PATH}")


def load_batting(season: int = None) -> pd.DataFrame:
    with _get_conn() as conn:
        if season:
            return pd.read_sql("SELECT * FROM batting WHERE 시즌 = ?", conn, params=(season,))
        return pd.read_sql("SELECT * FROM batting ORDER BY 시즌", conn)


def load_pitching(season: int = None) -> pd.DataFrame:
    with _get_conn() as conn:
        if season:
            return pd.read_sql("SELECT * FROM pitching WHERE 시즌 = ?", conn, params=(season,))
        return pd.read_sql("SELECT * FROM pitching ORDER BY 시즌", conn)


def table_exists(table: str) -> bool:
    with _get_conn() as conn:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        )
        return cur.fetchone() is not None


def season_exists(table: str, season: int) -> bool:
    if not table_exists(table):
        return False
    with _get_conn() as conn:
        cur = conn.execute(f"SELECT 1 FROM {table} WHERE 시즌 = ? LIMIT 1", (season,))
        return cur.fetchone() is not None
