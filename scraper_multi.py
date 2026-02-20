#!/usr/bin/env python3
"""
닌텐도 스위치 2 나눔통신(GameShare) 지원 게임 목록 - 다지역 스크레이퍼
Nintendo Switch 2 GameShare Supported Games - Multi-Region Scraper

Korea (KR): requests + BeautifulSoup (Magento HTML)
US        : Playwright (Next.js / React)
Japan (JP): Playwright (SFCC / React)

출력: gameshare_multi_YYYYMMDD_HHMMSS.csv
"""

import csv
import json
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ─── 설정 ────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

KR_BASE   = "https://store.nintendo.co.kr"
KR_LIST   = f"{KR_BASE}/all-product?label_platform=4679"
KR_DELAY  = 1.5

US_BASE   = "https://www.nintendo.com"
US_GAMESHARE_LOCAL_URL = (
    f"{US_BASE}/us/search/"
    "#cat=gme"
    "&f=waysToPlayLabels%2CcorePlatforms"
    "&waysToPlayLabels=GameShare%20with%20local%20users"
    "&corePlatforms=Nintendo%20Switch%202"
)
US_GAMESHARE_CHAT_URL = (
    f"{US_BASE}/us/search/"
    "#cat=gme"
    "&f=waysToPlayLabels%2CcorePlatforms"
    "&waysToPlayLabels=GameShare%20over%20GameChat"
    "&corePlatforms=Nintendo%20Switch%202"
)

JP_BASE = "https://store-jp.nintendo.com"
JP_LOCAL_URL = f"{JP_BASE}/list/tag/0078?labelPlatform=BEE"   # GameShare Local
JP_CHAT_URL  = f"{JP_BASE}/list/tag/0079?labelPlatform=BEE"   # GameShare GameChat

_DATE      = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_FILE = f"gameshare_multi_{_DATE}.csv"


# ─── 공통 유틸 ────────────────────────────────────────────────────────

def normalize(name: str) -> str:
    """이름 정규화 (소문자, 공백/특수문자 제거) - 지역 간 매칭용"""
    name = unicodedata.normalize("NFKC", name).lower()
    name = re.sub(r"[™®©℗℠:「」『』【】\-–—_.,!?'\"\s]+", " ", name).strip()
    return name


def scroll_to_bottom(page, pause=2.5, max_rounds=20):
    """무한 스크롤 페이지에서 모든 항목 로드"""
    prev = 0
    for _ in range(max_rounds):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(int(pause * 1000))
        cur = page.evaluate("document.body.scrollHeight")
        if cur == prev:
            break
        prev = cur


# ─── KR 스크레이퍼 ───────────────────────────────────────────────────

def kr_get_all_urls() -> list[str]:
    """한국 스토어 Switch 2 전체 게임 URL 수집"""
    urls: list[str] = []
    page_num = 1
    print("[KR] URL 수집 시작...")
    while True:
        r = requests.get(
            f"{KR_LIST}&p={page_num}",
            headers={**HEADERS, "Accept-Language": "ko-KR,ko;q=0.9"},
            timeout=20,
        )
        if r.status_code != 200:
            break
        soup = BeautifulSoup(r.text, "lxml")
        items = soup.select("li.product-item")
        if not items:
            break
        for item in items:
            a = item.select_one("a.product-item-link")
            if a and a.get("href"):
                urls.append(a["href"].strip())
        total_raw = soup.select_one(".toolbar-amount")
        print(f"  페이지 {page_num} 완료: 누적 {len(urls)}개", end="")
        if total_raw:
            print(f" (총 {total_raw.get_text(strip=True)})", end="")
        print()
        page_num += 1
        time.sleep(KR_DELAY)
    return urls


def kr_check_game(url: str, session: requests.Session) -> dict | None:
    """개별 게임 페이지에서 GameShare 지원 여부 확인"""
    for attempt in range(3):
        try:
            r = session.get(url, timeout=15)
            if r.status_code == 403:
                time.sleep(5)
                continue
            if r.status_code != 200:
                return None
            soup = BeautifulSoup(r.text, "lxml")

            def has_gameshare(css_class):
                div = soup.select_one(f"div.product-attribute.{css_class}")
                if not div:
                    return False
                val = div.select_one("div.attribute-item-val")
                return bool(val and "대응" in val.get_text())

            local = has_gameshare("supported_game_share_l")
            chat  = has_gameshare("supported_game_share_c")

            if not (local or chat):
                return None

            title = soup.select_one("h1.page-title span")
            name  = title.get_text(strip=True) if title else ""

            return {
                "name": name,
                "kr_url": url,
                "kr_local": local,
                "kr_chat": chat,
            }
        except Exception:
            time.sleep(3)
    return None


def scrape_kr() -> list[dict]:
    print("\n══════════ 🇰🇷 한국 스토어 스크랩 ══════════")
    session = requests.Session()
    session.headers.update({**HEADERS, "Accept-Language": "ko-KR,ko;q=0.9"})

    all_urls = kr_get_all_urls()
    results  = []
    print(f"[KR] 총 {len(all_urls)}개 URL 상세 스캔 시작...\n")

    for i, url in enumerate(all_urls, 1):
        data = kr_check_game(url, session)
        if data:
            results.append(data)
            marker = "★ GameShare"
            print(f"  [{i:3d}] {marker} | {data['name']}")
        else:
            print(f"  [{i:3d}]   -")
        time.sleep(KR_DELAY)

    print(f"\n[KR] 나눔통신 지원 게임: {len(results)}개")
    return results


# ─── US 스크레이퍼 ───────────────────────────────────────────────────

def us_get_gameshare_slugs(page) -> tuple[set[str], set[str]]:
    """US 검색 결과에서 GameShare 게임 slug 수집"""

    def load_slugs(url: str) -> set[str]:
        page.goto(url, wait_until="networkidle", timeout=40000)
        page.wait_for_timeout(3000)
        scroll_to_bottom(page)
        links = page.query_selector_all("a[href*='/us/store/products/']")
        slugs = set()
        for l in links:
            href = l.get_attribute("href") or ""
            m = re.search(r"/us/store/products/([^/?#]+)", href)
            if m:
                slugs.add(m.group(1))
        return slugs

    print("[US] GameShare Local 목록 수집...")
    local_slugs = load_slugs(US_GAMESHARE_LOCAL_URL)
    print(f"  → {len(local_slugs)}개")

    print("[US] GameShare Chat 목록 수집...")
    chat_slugs = load_slugs(US_GAMESHARE_CHAT_URL)
    print(f"  → {len(chat_slugs)}개")

    return local_slugs, chat_slugs


def us_get_game_name(page, slug: str) -> str:
    """개별 US 게임 페이지에서 게임 이름 추출"""
    try:
        page.goto(
            f"{US_BASE}/us/store/products/{slug}/",
            wait_until="domcontentloaded",
            timeout=20000,
        )
        page.wait_for_timeout(1500)
        el = page.query_selector("h1")
        return el.inner_text().strip() if el else slug
    except Exception:
        return slug


def scrape_us(playwright) -> list[dict]:
    print("\n══════════ 🇺🇸 미국 스토어 스크랩 ══════════")
    browser = playwright.chromium.launch(headless=True)
    ctx  = browser.new_context(
        user_agent=HEADERS["User-Agent"], locale="en-US"
    )
    page = ctx.new_page()

    local_slugs, chat_slugs = us_get_gameshare_slugs(page)
    all_slugs = local_slugs | chat_slugs

    results = []
    print(f"[US] 총 {len(all_slugs)}개 GameShare 게임 이름 확인...")
    for slug in sorted(all_slugs):
        name = us_get_game_name(page, slug)
        entry = {
            "name": name,
            "us_url": f"{US_BASE}/us/store/products/{slug}/",
            "us_local": slug in local_slugs,
            "us_chat":  slug in chat_slugs,
        }
        results.append(entry)
        icon = "★"
        print(f"  {icon} {name}")
        time.sleep(0.5)

    browser.close()
    print(f"[US] GameShare 게임: {len(results)}개")
    return results


# ─── JP 스크레이퍼 ───────────────────────────────────────────────────

def jp_get_gameshare_ids(page, url: str, label: str) -> set[str]:
    """JP 스토어 태그 페이지에서 게임 ID 수집 (페이지 스크롤)"""
    print(f"[JP] {label} 목록 수집...")
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(4000)
    scroll_to_bottom(page, pause=2.0)

    links = page.query_selector_all("a[href*='/item/software/D']")
    ids = set()
    for l in links:
        href = l.get_attribute("href") or ""
        m = re.search(r"/item/software/(D\w+)", href)
        if m:
            ids.add(m.group(1))
    print(f"  → {len(ids)}개")
    return ids


def jp_get_game_name(page, product_id: str) -> str:
    """JP 게임 페이지에서 이름 추출"""
    try:
        page.goto(
            f"{JP_BASE}/item/software/{product_id}",
            wait_until="domcontentloaded",
            timeout=30000,
        )
        page.wait_for_timeout(3000)

        state_raw = page.evaluate("""() => {
            if (window.__PRELOADED_STATE__) return JSON.stringify(window.__PRELOADED_STATE__);
            return null;
        }""")
        if state_raw:
            state = json.loads(state_raw)
            queries = state.get("__reactQuery", {}).get("queries", [])
            for q in queries:
                d = q.get("state", {}).get("data", {})
                if isinstance(d, dict) and d.get("title"):
                    return d["title"]
                if isinstance(d, dict) and d.get("name"):
                    return d["name"]

        el = page.query_selector("h1")
        return el.inner_text().strip() if el else product_id
    except Exception:
        return product_id


def scrape_jp(playwright) -> list[dict]:
    print("\n══════════ 🇯🇵 일본 스토어 스크랩 ══════════")
    browser = playwright.chromium.launch(headless=True)
    ctx  = browser.new_context(
        user_agent=HEADERS["User-Agent"], locale="ja-JP"
    )
    page = ctx.new_page()

    local_ids = jp_get_gameshare_ids(page, JP_LOCAL_URL, "GameShare Local")
    chat_ids  = jp_get_gameshare_ids(page, JP_CHAT_URL,  "GameShare Chat")
    all_ids   = local_ids | chat_ids

    results = []
    print(f"[JP] 총 {len(all_ids)}개 GameShare 게임 이름 확인...")
    for pid in sorted(all_ids):
        name = jp_get_game_name(page, pid)
        entry = {
            "name": name,
            "jp_url": f"{JP_BASE}/item/software/{pid}",
            "jp_local": pid in local_ids,
            "jp_chat":  pid in chat_ids,
        }
        results.append(entry)
        print(f"  ★ {name}")
        time.sleep(0.5)

    browser.close()
    print(f"[JP] GameShare 게임: {len(results)}개")
    return results


# ─── 지역 간 매칭 & CSV 출력 ─────────────────────────────────────────

def merge_results(kr_list, us_list, jp_list) -> list[dict]:
    """게임 이름 기반으로 지역별 결과 병합"""

    def make_lookup(lst, name_key="name"):
        return {normalize(g[name_key]): g for g in lst}

    kr_map = make_lookup(kr_list)
    us_map = make_lookup(us_list)
    jp_map = make_lookup(jp_list)

    all_names: dict[str, dict] = {}  # norm_name -> merged row

    for norm, g in kr_map.items():
        all_names[norm] = {
            "name_kr": g["name"],
            "name_us": "",
            "name_jp": "",
            "kr_local": g.get("kr_local", False),
            "kr_chat":  g.get("kr_chat",  False),
            "us_local": False,
            "us_chat":  False,
            "jp_local": False,
            "jp_chat":  False,
            "kr_url": g.get("kr_url", ""),
            "us_url": "",
            "jp_url": "",
        }

    for norm, g in us_map.items():
        best = _fuzzy_match(norm, all_names)
        if best:
            all_names[best]["name_us"] = g["name"]
            all_names[best]["us_local"] = g.get("us_local", False)
            all_names[best]["us_chat"]  = g.get("us_chat",  False)
            all_names[best]["us_url"]   = g.get("us_url", "")
        else:
            all_names[norm] = {
                "name_kr": "",
                "name_us": g["name"],
                "name_jp": "",
                "kr_local": False, "kr_chat": False,
                "us_local": g.get("us_local", False),
                "us_chat":  g.get("us_chat",  False),
                "jp_local": False, "jp_chat": False,
                "kr_url": "",
                "us_url": g.get("us_url", ""),
                "jp_url": "",
            }

    for norm, g in jp_map.items():
        best = _fuzzy_match(norm, all_names)
        if best:
            all_names[best]["name_jp"] = g["name"]
            all_names[best]["jp_local"] = g.get("jp_local", False)
            all_names[best]["jp_chat"]  = g.get("jp_chat",  False)
            all_names[best]["jp_url"]   = g.get("jp_url", "")
        else:
            all_names[norm] = {
                "name_kr": "",
                "name_us": "",
                "name_jp": g["name"],
                "kr_local": False, "kr_chat": False,
                "us_local": False, "us_chat": False,
                "jp_local": g.get("jp_local", False),
                "jp_chat":  g.get("jp_chat",  False),
                "kr_url": "",
                "us_url": "",
                "jp_url": g.get("jp_url", ""),
            }

    rows = list(all_names.values())
    # 이름 정렬 (KR → US → JP 순)
    rows.sort(key=lambda r: (r["name_kr"] or r["name_us"] or r["name_jp"]).lower())
    return rows


def _fuzzy_match(norm: str, pool: dict, threshold=0.6) -> str | None:
    """정규화된 이름으로 가장 유사한 키 찾기"""
    if norm in pool:
        return norm
    # 부분 일치: norm이 키에 포함되거나 키가 norm에 포함
    candidates = []
    for key in pool:
        if norm in key or key in norm:
            overlap = len(set(norm.split()) & set(key.split()))
            total   = max(len(norm.split()), len(key.split()))
            score   = overlap / total if total else 0
            if score >= threshold:
                candidates.append((score, key))
    if candidates:
        return max(candidates)[1]
    return None


def write_csv(rows: list[dict]):
    fieldnames = [
        "name_kr", "name_us", "name_jp",
        "kr_local", "kr_chat",
        "us_local", "us_chat",
        "jp_local", "jp_chat",
        "kr_url", "us_url", "jp_url",
    ]
    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})
    print(f"\n✅ 저장 완료: {OUTPUT_FILE}  (총 {len(rows)}개 게임)")


# ─── 메인 ────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  닌텐도 스위치 2 GameShare 다지역 스크레이퍼")
    print("  Nintendo Switch 2 GameShare Multi-Region Scraper")
    print("=" * 55)

    kr_results = scrape_kr()

    with sync_playwright() as pw:
        us_results = scrape_us(pw)
        jp_results = scrape_jp(pw)

    print("\n══════════ 결과 병합 & CSV 저장 ══════════")
    merged = merge_results(kr_results, us_results, jp_results)
    write_csv(merged)

    # 요약 출력
    print("\n┌─────────────────────────────────────────┐")
    print("│ 지역별 GameShare 게임 수                │")
    print(f"│  🇰🇷 한국: {len(kr_results):3d}개                        │")
    print(f"│  🇺🇸 미국: {len(us_results):3d}개                        │")
    print(f"│  🇯🇵 일본: {len(jp_results):3d}개                        │")
    print(f"│  전체(병합): {len(merged):3d}개                     │")
    print("└─────────────────────────────────────────┘")


if __name__ == "__main__":
    main()
