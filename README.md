# Nintendo Switch 2 GameShare List / 닌텐도 스위치 2 나눔통신 지원 게임 목록

## 한국어

닌텐도 코리아 스토어에서 **나눔통신(GameShare)** 을 지원하는 Nintendo Switch 2 게임 목록을 자동으로 수집하는 스크레이퍼입니다.

### 나눔통신이란?
Nintendo Switch 2의 새로운 기능으로, 한 명이 게임을 보유하면 주변 사람들과 함께 플레이할 수 있습니다.
- **가까이 있는 사람** : 근거리 무선 통신으로 나눔
- **게임챗 중** : 게임챗 연결된 사람과 나눔

### 사용 방법

```bash
# 가상환경 생성
python3 -m venv .venv
source .venv/bin/activate

# 패키지 설치
pip install requests beautifulsoup4 lxml

# 실행
python scraper.py
```

### 결과
- `gameshare_games_날짜.csv` 파일로 저장
- 중단 후 재실행 시 `progress.json` 기반으로 이어서 실행
- 403 차단 발생 시 자동 재시도

---

## English

A scraper that automatically collects Nintendo Switch 2 games supporting **GameShare** from the Nintendo Korea store.

### What is GameShare?
A new Nintendo Switch 2 feature that allows one person who owns a game to share it with nearby players.
- **Local users** : Share via local wireless
- **Game Chat users** : Share with people connected via Game Chat

### How to use

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install packages
pip install requests beautifulsoup4 lxml

# Run
python scraper.py
```

### Output
- Results saved to `gameshare_games_<datetime>.csv`
- Resumes from `progress.json` if interrupted
- Automatically retries URLs that returned 403

---

**Data source**: [Nintendo Korea Store](https://store.nintendo.co.kr)
