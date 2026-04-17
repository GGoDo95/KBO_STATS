"""
나무위키에서 KBO 선수 등장곡/응원가 전체 수집 → data/namu_music.json 저장 → 사이트 재빌드.

실행: python update_music.py
"""

import json
import subprocess
from pathlib import Path
from crawler.namu_crawler import crawl_all_teams_music

OUT = Path("data/namu_music.json")

def main():
    music = crawl_all_teams_music(delay=2.0)

    print(f"\n[결과] 총 {len(music)}명 수집")
    has_entrance = sum(1 for v in music.values() if v.get("등장곡"))
    has_cheer    = sum(1 for v in music.values() if v.get("응원가"))
    print(f"  등장곡: {has_entrance}명 / 응원가: {has_cheer}명")

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(music, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[저장] {OUT}  ({OUT.stat().st_size // 1024} KB)")

    print("\n[빌드] build_site.py 실행 중...")
    subprocess.run(["python", "build_site.py"], check=True)
    print("완료.")

if __name__ == "__main__":
    main()
