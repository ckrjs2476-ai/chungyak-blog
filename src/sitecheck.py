"""애드센스 거절 사유 상위 항목을 공개 블로그에서 직접 확인한다 (로그인 없이, 공개 피드와 페이지만).
사용: python src/sitecheck.py  → data/sitecheck.md, data/sitecheck.json
거절 사유 순서와 근거는 rules/adsense_rejection_top.md.
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
KST = timezone(timedelta(hours=9))
BLOGS = {"cheongyak": "daily-cheongyak", "jeonse": "jeonse-ondogye", "gongmoju": "gongmoju-breakdown",
         "gwanribi": "gwanribi-dotbogi"}
NAMES = {"cheongyak": "청약노트", "jeonse": "전세 온도계", "gongmoju": "공모주 뜯어보기", "gwanribi": "관리비 돋보기"}
UA = {"User-Agent": "Mozilla/5.0 (sitecheck for own blog)"}
NEED_PAGES = {"소개": r"(소개|about)", "문의": r"(문의|연락|contact)", "개인정보처리방침": r"(개인정보|privacy)",
              "분석 방법": r"(방법|method)"}
PLACEHOLDER = re.compile(r"(lorem ipsum|준비 ?중|공사 ?중|테스트 ?글|test post|샘플 ?글|내용을 입력|coming soon)", re.I)
MIN_PER_LABEL = 8


LAST_ERR: list[str] = []


def get(url: str, **kw):
    """구글이 GitHub 공용 IP를 자주 429로 막는다. 간격을 두고 기다렸다 다시 시도한다."""
    r = None
    for wait in (0, 30, 90, 180):
        time.sleep(wait or 1.5)
        try:
            r = requests.get(url, headers=UA, timeout=30, **kw)
        except requests.RequestException as e:
            LAST_ERR.append(f"{type(e).__name__}: {str(e)[:120]}")
            continue
        if r.status_code != 429:
            return r
    return r


def feed(host: str, kind: str) -> list[dict]:
    out, start = [], 1
    while True:
        r = get(f"https://{host}.blogspot.com/feeds/{kind}/default", params={"alt": "json", "max-results": 150, "start-index": start})
        if r is None or r.status_code != 200:
            return out
        ents = r.json().get("feed", {}).get("entry", []) or []
        out += ents
        if len(ents) < 150:
            return out
        start += 150


def link_of(e: dict) -> str:
    return next((l["href"] for l in e.get("link", []) if l.get("rel") == "alternate"), "")


def check_blog(key: str, host: str) -> dict:
    res = {"key": key, "name": NAMES[key], "host": f"https://{host}.blogspot.com", "problems": [], "notes": []}
    P, N = res["problems"], res["notes"]
    home = get(res["host"] + "/")
    if home is None or home.status_code != 200:
        kind = "확인 못 함(구글이 점검 요청을 잠시 막음)" if home is not None and home.status_code == 429 else "사이트 이용 불가"
        P.append((kind, f"홈 응답 {home.status_code if home is not None else '없음 ' + (LAST_ERR[-1] if LAST_ERR else '')}"))
        return res
    html = home.text
    # 기술: noindex, 모바일, canonical
    if re.search(r'<meta[^>]+name=["\']robots["\'][^>]+noindex', html, re.I):
        P.append(("색인 차단", "홈에 noindex가 있습니다"))
    if 'name="viewport"' not in html and "name='viewport'" not in html:
        P.append(("모바일", "홈에 viewport 메타 태그가 없습니다"))
    posts, pages = feed(host, "posts"), feed(host, "pages")
    res["post_count"], res["page_count"] = len(posts), len(pages)
    # 필수 페이지
    page_titles = [(e.get("title", {}).get("$t", ""), link_of(e)) for e in pages]
    for need, pat in NEED_PAGES.items():
        hit = [t for t, u in page_titles if re.search(pat, t + " " + u, re.I)]
        if not hit:
            P.append(("필수 페이지 없음", f"'{need}' 페이지가 없습니다"))
    if pages and not re.search(r"/p/", html):
        P.append(("탐색", "홈 화면에 정적 페이지(소개·문의 등)로 가는 링크가 보이지 않습니다"))
    # 라벨
    labels = Counter(c["term"] for e in posts for c in e.get("category", []))
    res["labels"] = dict(labels.most_common())
    thin = [f"{l}({c})" for l, c in labels.items() if c < MIN_PER_LABEL]
    if thin:
        N.append(("라벨 편수", f"8편 미만 라벨 {len(thin)}개: " + ", ".join(thin[:12])))
    if "/search/label/" not in html and labels:
        P.append(("탐색", "홈 화면에 라벨(카테고리) 메뉴 링크가 보이지 않습니다"))
    # 글: 미완성·짧은 글·깨진 링크
    own_links: set[str] = set()
    for e in posts:
        title = e.get("title", {}).get("$t", "")
        body = e.get("content", {}).get("$t", "")
        url = link_of(e)
        text = re.sub(r"<[^>]+>", " ", body)
        if PLACEHOLDER.search(title + " " + text[:500]):
            P.append(("미완성·시험 글", f"'{title[:30]}' {url}"))
        n_chars = len(re.sub(r"\s", "", text))
        if n_chars < 800:
            P.append(("내용이 적은 글", f"'{title[:30]}' 본문 {n_chars}자 {url}"))
        for h in re.findall(r'href="([^"#]+)"', body):
            if urlparse(h).netloc == f"{host}.blogspot.com":
                own_links.add(h.split("?")[0])
    for t, u in page_titles:
        if PLACEHOLDER.search(t):
            P.append(("미완성·시험 페이지", f"'{t}' {u}"))
    broken = []
    for u in sorted(own_links)[:200]:
        r = get(u, allow_redirects=True)
        if r is not None and r.status_code == 429:
            continue  # 확인 못 함(깨짐 아님)
        if r is None or r.status_code >= 400:
            broken.append(u)
    if broken:
        P.append(("깨진 내부 링크", f"{len(broken)}개: " + ", ".join(broken[:5])))
    # 최신성: 마지막 글 날짜
    if posts:
        last = max(e.get("published", {}).get("$t", "")[:10] for e in posts)
        res["last_post"] = last
        if (datetime.now(KST).date() - datetime.fromisoformat(last).date()).days >= 3:
            P.append(("발행 멈춤", f"마지막 글이 {last}입니다"))
    else:
        P.append(("글 없음", "공개 글이 없습니다"))
    return res


def main() -> int:
    results = []
    for k, h in BLOGS.items():
        results.append(check_blog(k, h))
        time.sleep(20)
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    lines = [f"# 애드센스 거절 사유 상위 항목 매일 점검 ({now} KST)", "",
             "기준과 순서: rules/adsense_rejection_top.md. '문제'는 고쳐야 할 것, '참고'는 신청 전까지 채울 것.", ""]
    for r in results:
        lines += [f"## {r['name']} ({r['host']})", "",
                  f"- 공개 글 {r.get('post_count', 0)}편, 정적 페이지 {r.get('page_count', 0)}개, 마지막 글 {r.get('last_post', '-')}"]
        lines += [f"- 문제 · {a}: {b}" for a, b in r["problems"]] or ["- 문제 없음"]
        lines += [f"- 참고 · {a}: {b}" for a, b in r["notes"]]
        lines.append("")
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "sitecheck.md").write_text("\n".join(lines), "utf-8")
    (ROOT / "data" / "sitecheck.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), "utf-8")
    print("\n".join(lines))
    for r in results:
        for a, b in r["problems"]:
            print(f"::warning::{r['name']} {a}: {b[:150]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
