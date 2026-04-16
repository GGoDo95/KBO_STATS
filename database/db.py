"""
SQLite 데이터베이스 저장/조회 모듈.
"""

import sqlite3
import pandas as pd
from pathlib import Path
from config import DB_PATH


def _get_conn() -> sqlite3.Connection:
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def save_batting(df: pd.DataFrame) -> None:
    """타자 스탯 + 세이버 지표를 DB에 저장 (기존 데이터 교체)."""
    with _get_conn() as conn:
        df.to_sql("batting", conn, if_exists="replace", index=False)
    print(f"[DB] 타자 {len(df)}명 저장 완료 → {DB_PATH}")


def save_pitching(df: pd.DataFrame) -> None:
    """투수 스탯 + 세이버 지표를 DB에 저장 (기존 데이터 교체)."""
    with _get_conn() as conn:
        df.to_sql("pitching", conn, if_exists="replace", index=False)
    print(f"[DB] 투수 {len(df)}명 저장 완료 → {DB_PATH}")


def load_batting() -> pd.DataFrame:
    with _get_conn() as conn:
        return pd.read_sql("SELECT * FROM batting", conn)


def load_pitching() -> pd.DataFrame:
    with _get_conn() as conn:
        return pd.read_sql("SELECT * FROM pitching", conn)


def table_exists(table: str) -> bool:
    with _get_conn() as conn:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        )
        return cur.fetchone() is not None
