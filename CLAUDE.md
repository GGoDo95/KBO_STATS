# KBO Sabermetrics Project

## Architecture
- `crawler/kbo_crawler.py` — KBO 공식 사이트 크롤러 (ASP.NET 3단계 POST: GET→시즌→팀)
- `sabermetrics/batting.py` — 타자 세이버 지표 (BABIP, ISO, wOBA, wRC+, OPS+, bWAR)
- `sabermetrics/pitching.py` — 투수 세이버 지표 (FIP, xFIP, ERA+, K/9, BB/9, pWAR)
- `database/db.py` — SQLite 저장/로드
- `web/app.py` — Streamlit 대시보드
- `config.py` — 리그 평균값, 파크팩터, 선형가중치

## Key commands
```bash
python main.py           # 크롤링 + 계산 + DB 저장
python main.py --force   # 강제 재크롤링
streamlit run web/app.py # 대시보드 실행
```
