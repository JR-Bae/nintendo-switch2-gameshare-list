#!/usr/bin/env python3
"""
닌텐도 코리아 스토어 나눔통신 지원 게임 목록 추출기
대상: https://store.nintendo.co.kr/all-product?label_platform=4679 (Switch 2 전용)
"""
import requests
from bs4 import BeautifulSoup
import csv
import time
import re
import os
import json
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}
BASE_URL = "https://store.nintendo.co.kr"
LIST_URL = f"{BASE_URL}/all-product?label_platform=4679"  # Switch 2 전용
DELAY = 2.0
_DATE = datetime.now().strftime("%Y%m%d_%H%M%S")
PROGRESS_FILE = "progress.json"
OUTPUT_FILE = f"gameshare_games_{_DATE}.csv"


def get_all_product_urls():
    """전체 상품 URL 수집 (페이지네이션)"""
    urls = {}
    page = 1
    while True:
        print(f"\r[목록] 페이지 {page} 수집 중...", end="", flush=True)
        resp = requests.get(LIST_URL, headers=HEADERS, params={"p": page}, timeout=15)
        soup = BeautifulSoup(resp.text, "lxml")

        links = soup.find_all("a", href=re.compile(r"store\.nintendo\.co\.kr/\d+|store\.nintendo\.co\.kr/[a-z0-9]+$"))
        found = 0
        for a in links:
            href = a.get("href", "")
            txt = a.get_text(strip=True)
            if href and txt and href not in urls:
                if re.search(r"/\d{10,}$|/\w{10,}$", href):
                    urls[href] = txt
                    found += 1

        next_link = soup.find("a", {"title": "다음 페이지"}) or soup.find("a", class_="next")
        if not next_link and found == 0:
            break

        pager = soup.find("ul", class_="pages-items")
        if pager:
            page_nums = [int(a.get_text(strip=True)) for a in pager.find_all("a") if a.get_text(strip=True).isdigit()]
            if page_nums and page >= max(page_nums):
                break

        if not next_link:
            break

        page += 1
        time.sleep(DELAY)

    print(f"\n[목록] 총 {len(urls)}개 상품 URL 수집 완료")
    return urls


def check_game_share(url):
    """게임 상세 페이지에서 나눔통신 지원 여부 확인. status_code 반환 포함."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)

        # 403이면 바로 반환
        if resp.status_code == 403:
            return {"url": url, "status": 403}

        soup = BeautifulSoup(resp.text, "lxml")
        title_el = soup.find("h1")
        title = title_el.get_text(strip=True) if title_el else ""

        result = {
            "url": url,
            "status": 200,
            "title": title,
            "game_share_chat": False,
            "game_share_local": False,
            "platform": "",
            "players": "",
            "genre": "",
            "release_date": "",
            "publisher": "",
        }

        for div in soup.find_all("div", class_="product-attribute"):
            classes = " ".join(div.get("class", []))
            val_el = div.find(class_="product-attribute-val")
            val = val_el.get_text(" ", strip=True) if val_el else ""

            if "supported_game_share_c" in classes:
                item_val = div.find(class_="attribute-item-val")
                result["game_share_chat"] = item_val is not None and "대응" in item_val.get_text(strip=True)
            elif "supported_game_share_l" in classes:
                item_val = div.find(class_="attribute-item-val")
                result["game_share_local"] = item_val is not None and "대응" in item_val.get_text(strip=True)
            elif "label_platform" in classes:
                result["platform"] = val
            elif "no_of_players" in classes and "online" not in classes and "wireless" not in classes:
                result["players"] = val
            elif "game_category" in classes:
                result["genre"] = val
            elif "release_date" in classes:
                result["release_date"] = val
            elif "publisher" in classes:
                result["publisher"] = val

        return result
    except Exception as e:
        return {"url": url, "status": -1, "error": str(e)}


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"done_urls": [], "retry_urls": [], "all_urls": {}}


def save_progress(data):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def main():
    print("=== 닌텐도 코리아 나눔통신 게임 스크레이퍼 (Switch 2) ===")
    print(f"시작 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    progress = load_progress()

    if progress["all_urls"]:
        print(f"이전 진행 상황 발견: {len(progress['all_urls'])}개 URL")
        all_urls = progress["all_urls"]
    else:
        print("[1단계] 전체 상품 URL 수집 중...")
        all_urls = get_all_product_urls()
        progress["all_urls"] = all_urls
        progress["done_urls"] = []
        progress["retry_urls"] = []
        save_progress(progress)

    done_urls = set(progress["done_urls"])
    retry_urls = set(progress.get("retry_urls", []))

    # 미완료 = 전체 - 성공완료 (retry는 다시 시도)
    remaining = [(url, title) for url, title in all_urls.items() if url not in done_urls]
    total = len(all_urls)
    initial_done = len(done_urls)

    print(f"\n[2단계] 상세 페이지 스캔 시작")
    print(f"전체: {total}개 | 완료: {initial_done}개 | 남은 것: {len(remaining)}개 | 이전 403: {len(retry_urls)}개")
    print(f"결과는 '{OUTPUT_FILE}'에 저장됩니다.\n")

    write_header = not os.path.exists(OUTPUT_FILE) or initial_done == 0
    csvfile = open(OUTPUT_FILE, "a", newline="", encoding="utf-8-sig")
    fieldnames = ["title", "url", "game_share_chat", "game_share_local", "platform", "players", "genre", "release_date", "publisher"]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction="ignore")
    if write_header:
        writer.writeheader()

    gameshare_count = 0
    try:
        for i, (url, _) in enumerate(remaining):
            current = initial_done + i + 1  # 카운터 버그 수정
            print(f"\r[{current}/{total}] 스캔: {url[-20:]}", end="", flush=True)

            result = check_game_share(url)
            status = result.get("status", -1)

            if status == 403:
                retry_urls.add(url)
                print(f"\n  ⚠ 403 차단! [{url[-20:]}] → retry 목록에 추가")
            elif status == 200:
                done_urls.add(url)
                retry_urls.discard(url)
                has_share = result.get("game_share_chat") or result.get("game_share_local")
                if has_share:
                    writer.writerow(result)
                    csvfile.flush()
                    gameshare_count += 1
                    print(f"\n  ★ 나눔통신 발견! [{result['title']}]")
            else:
                done_urls.add(url)

            progress["done_urls"] = list(done_urls)
            progress["retry_urls"] = list(retry_urls)

            if (i + 1) % 50 == 0:
                save_progress(progress)

            time.sleep(DELAY)

    except KeyboardInterrupt:
        print("\n\n[중단] 진행 상황 저장 중...")
        save_progress(progress)
    finally:
        csvfile.close()
        save_progress(progress)

    # 403 차단된 URL 자동 재시도
    if retry_urls:
        print(f"\n\n[3단계] 403 차단 URL {len(retry_urls)}개 재시도 중... (3초 대기)")
        time.sleep(3)
        retry_list = list(retry_urls)
        for i, url in enumerate(retry_list):
            print(f"\r  [{i+1}/{len(retry_list)}] 재시도: {url[-20:]}", end="", flush=True)
            result = check_game_share(url)
            status = result.get("status", -1)
            if status == 403:
                print(f"\n  ⚠ 또 403: {url[-20:]}")
            elif status == 200:
                retry_urls.discard(url)
                done_urls.add(url)
                has_share = result.get("game_share_chat") or result.get("game_share_local")
                if has_share:
                    writer.writerow(result)
                    csvfile.flush()
                    gameshare_count += 1
                    print(f"\n  ★ 재시도 나눔통신 발견! [{result['title']}]")
            time.sleep(3)

        progress["done_urls"] = list(done_urls)
        progress["retry_urls"] = list(retry_urls)
        save_progress(progress)

    print(f"\n\n=== 완료 ===")
    print(f"나눔통신 지원 게임: {gameshare_count}개")
    print(f"여전히 403인 URL: {len(retry_urls)}개")
    print(f"결과 파일: {OUTPUT_FILE}")
    print(f"종료 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
