"""
선수 프로필 전체 재수집 스크립트.
DB에 있는 모든 player_id를 기준으로 프로필을 다시 크롤링한다.
등장곡 / 응원가 등 최신 필드 반영 목적.

실행: python update_profiles.py
"""

import sqlite3
import json
import time
from pathlib import Path
from config import DB_PATH
from crawler.kbo_crawler import crawl_player_profile

def load_all_player_ids() -> list:
    """DB에서 (player_id, kind) 목록 반환."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT player_id, data FROM profiles").fetchall()
    conn.close()
    result = []
    for pid, data_str in rows:
        try:
            d = json.loads(data_str)
            result.append((pid, d.get("kind", "hitter")))
        except Exception:
            result.append((pid, "hitter"))
    return result

def save_profiles(profiles: list) -> None:
    conn = sqlite3.connect(DB_PATH)
    for p in profiles:
        if not p or "player_id" not in p:
            continue
        conn.execute(
            "INSERT OR REPLACE INTO profiles (player_id, 선수명, data) VALUES (?,?,?)",
            (p["player_id"], p.get("선수명", ""), json.dumps(p, ensure_ascii=False)),
        )
    conn.commit()
    conn.close()

def main():
    entries = load_all_player_ids()
    print(f"총 {len(entries)}명 프로필 재수집 시작...")

    updated = []
    for i, (pid, kind) in enumerate(entries, 1):
        print(f"  [{i}/{len(entries)}] player_id={pid} ({kind})", end="", flush=True)
        p = crawl_player_profile(pid, kind)
        if p:
            updated.append(p)
            music = []
            if p.get("등장곡"): music.append(f"등장곡: {p['등장곡']}")
            if p.get("응원가"): music.append(f"응원가: {p['응원가']}")
            suffix = f"  [{', '.join(music)}]" if music else ""
            print(f" OK  {p.get('선수명', '')}{suffix}")
        else:
            print(" FAIL")

    save_profiles(updated)
    print(f"\n[DB] {len(updated)}명 저장 완료 → {DB_PATH}")

    # HTML 재생성
    print("\n[빌드] build_site.py 실행 중...")
    import subprocess
    subprocess.run(["python", "build_site.py"], check=True)
    print("완료.")

if __name__ == "__main__":
    main()
