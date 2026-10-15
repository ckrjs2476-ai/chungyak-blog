"""posts/pending/의 글을 검수하고, 통과하면 Blogger에 올린다.

- config.json의 mode가 "draft"면 임시저장, "live"면 바로 발행
- 실패한 글은 posts/held/로 옮기고 사유 파일을 남긴 뒤, 마지막에 종료 코드 1로 끝내 GitHub 알림 메일을 받는다
환경변수: BLOGGER_CLIENT_ID, BLOGGER_CLIENT_SECRET, BLOGGER_REFRESH_TOKEN, BLOGGER_BLOG_ID
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import markdown
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parent.parent
# 블로그 여러 개: BLOG_KEY가 없으면 청약노트(저장소 루트), 있으면 blogs/<BLOG_KEY>/의 blog.py 설정을 쓴다
BLOG = os.environ.get("BLOG_KEY", "cheongyak")
if BLOG == "cheongyak":
    from card import build_card  # noqa: E402
    from check import check_text, recent_posts, split_post  # noqa: E402
    BASE = ROOT
    UNIT_KEY = "house_manage_no"
    _blog = None
else:
    import importlib  # noqa: E402
    sys.path.insert(0, str(ROOT / "blogs" / BLOG))
    _blog = importlib.import_module("blog")
    build_card, check_text, recent_posts, split_post = (_blog.build_card, _blog.check_text,
                                                        _blog.recent_posts, _blog.split_post)
    BASE = ROOT / "blogs" / BLOG
    UNIT_KEY = _blog.UNIT_KEY

REL_START, REL_END = "<!--related-start-->", "<!--related-end-->"
TYPE_NAME = {"notice": "청약 일정·분양가", "competition": "경쟁률 결과", "score": "당첨 가점",
             "remainder": "무순위·잔여 세대"}

PENDING, DONE, HELD, REVIEW = (BASE / "posts" / d for d in ("pending", "published", "held", "review"))
PUBLISHED = (ROOT / "data" / "published.json") if _blog is None else (BASE / "data" / "published.json")
CONFIG = json.loads((ROOT / "config.json").read_text("utf-8"))
KST = timezone(timedelta(hours=9))
API = "https://www.googleapis.com/blogger/v3"


def _retry(fn, tries: int = 4):
    """Blogger API가 가끔 503(backendError)을 낸다. 잠깐 기다렸다 다시 부른다."""
    import time
    res = fn()
    for wait in (5, 15, 40)[:tries - 1]:
        if res.status_code < 500:
            return res
        time.sleep(wait)
        res = fn()
    return res


def _ok(res: requests.Response, what: str) -> requests.Response:
    """실패하면 원인을 Actions 주석(annotation)으로 남긴다. 로그를 못 열어도 원인이 보이게."""
    if not res.ok:
        print(f"::error::{what} HTTP {res.status_code}: {res.text[:400].replace(chr(10), ' ')}")
        res.raise_for_status()
    return res


def access_token() -> str:
    res = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": os.environ["BLOGGER_CLIENT_ID"],
        "client_secret": os.environ["BLOGGER_CLIENT_SECRET"],
        "refresh_token": os.environ["BLOGGER_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }, timeout=30)
    _ok(res, "토큰 발급")
    return res.json()["access_token"]


# 본문 꾸밈. Blogger 테마의 회색 글자·좁은 문단 간격을 덮어쓰려고 태그마다 style 속성으로 넣는다
# (Blogger는 글 안의 <style> 태그를 지우는 경우가 있다). 바꾸면 publish.py --rerender로 기존 글에도 반영한다.
TEXT = "#111111"
WRAP = (f"color:{TEXT};font-size:16px;line-height:1.85;word-break:keep-all;overflow-wrap:break-word;")
TAG_STYLE = {
    "p": f"margin:0 0 1.5em;color:{TEXT};line-height:1.85;",
    "h2": (f"margin:2.8em 0 1.1em;padding-top:1.3em;border-top:1px solid #e5e7eb;font-size:21px;"
           f"line-height:1.45;font-weight:700;color:{TEXT};"),
    "h3": f"margin:2.2em 0 0.9em;font-size:18px;line-height:1.5;font-weight:700;color:{TEXT};",
    "ul": f"margin:0 0 1.6em;padding-left:1.3em;color:{TEXT};",
    "ol": f"margin:0 0 1.6em;padding-left:1.3em;color:{TEXT};",
    "li": f"margin:0 0 0.7em;line-height:1.8;color:{TEXT};",
    "table": "border-collapse:collapse;width:100%;margin:1.6em 0 2em;font-size:15px;",
    "th": f"padding:10px 8px;border:1px solid #e5e7eb;background:#f3f4f6;color:{TEXT};text-align:left;font-weight:700;",
    "td": f"padding:10px 8px;border:1px solid #e5e7eb;color:{TEXT};",
    "blockquote": ("margin:2.4em 0 0;padding:14px 16px;background:#f7f9fc;border-left:4px solid #cbd2d9;"
                   "color:#333333;font-size:14px;"),
    "a": "color:#1a56db;text-decoration:underline;",
    "strong": f"color:{TEXT};",
}


def style_html(html: str) -> str:
    def add(m: re.Match) -> str:
        tag, attrs = m.group(1), m.group(2) or ""
        if "style=" in attrs:
            return m.group(0)
        return f'<{tag}{attrs} style="{TAG_STYLE[tag]}">'
    html = re.sub(r"<(%s)(\s[^>]*)?>" % "|".join(TAG_STYLE), add, html)
    # 인용문 안의 문단은 아래 여백을 없앤다
    html = re.sub(r'(<blockquote[^>]*>\s*<p style=")margin:0 0 1.5em;', r"\1margin:0;", html)
    return f'<div style="{WRAP}">{html}</div>'


def to_html(body: str) -> str:
    return style_html(markdown.markdown(body, extensions=["tables", "sane_lists"]))


# 공개 시각을 매일 다르게: 블로그별 시간대(시작 시각, 길이 분) 안에서 랜덤으로 Blogger 예약 발행.
# 시작 시각은 예약 글쓰기 작업 시각과 맞춘다(청약노트 오전만 10~11시). 2026-10-14 시험: 예약해도 영문 주소 유지.
PUBLISH_WINDOWS = {
    "cheongyak": [("10:00", 60), ("18:35", 60)],
    "gongmoju": [("07:50", 60), ("17:47", 60)],
    "jeonse": [("12:40", 60), ("19:44", 60)],
    "gwanribi": [("15:52", 60), ("21:13", 60)],
}


def pick_publish_time(now: datetime | None = None) -> datetime | None:
    """지금이 어느 시간대 직전·안이면 그 안의 랜덤 시각, 아니면 None(바로 발행).
    이미 남은 시간이 5분 미만이면 바로 발행한다."""
    import random
    now = now or datetime.now(KST)
    for hm, minutes in PUBLISH_WINDOWS.get(BLOG, []):
        h, m = map(int, hm.split(":"))
        start = now.replace(hour=h, minute=m, second=0, microsecond=0)
        end = start + timedelta(minutes=minutes)
        if start - timedelta(hours=1) <= now < end:
            lo = max(now + timedelta(minutes=3), start)
            if (end - lo).total_seconds() < 300:
                return None
            return lo + timedelta(seconds=random.randint(0, int((end - lo).total_seconds())))
    return None


def post_to_blogger(token: str, meta: dict, html: str, draft: bool) -> dict:
    blog = os.environ["BLOGGER_BLOG_ID"]
    h = {"Authorization": f"Bearer {token}"}
    when = None if draft else pick_publish_time()
    # 1) 영문 slug를 제목으로 먼저 만들어 주소(퍼머링크)를 영문으로 고정
    # 2) 그다음 제목을 한글로 바꾼다. (Blogger 동작에 기대는 방식이라 첫 테스트에서 주소를 꼭 확인)
    body = {"kind": "blogger#post", "title": meta["slug"].replace("-", " "),
            "content": html, "labels": meta.get("labels", [])}
    res = requests.post(f"{API}/blogs/{blog}/posts", params={"isDraft": str(draft or when is not None).lower()},
                        json=body, headers=h, timeout=60)
    _ok(res, "글 만들기")
    post = res.json()
    if when is not None:
        res = _retry(lambda: requests.post(f"{API}/blogs/{blog}/posts/{post['id']}/publish",
                                           params={"publishDate": when.isoformat(timespec="seconds")}, headers=h, timeout=60))
        _ok(res, "예약 발행")
        post = res.json()
        post["_scheduled_at"] = when.isoformat(timespec="seconds")
        print(f"::notice::예약 발행: {when:%H:%M} KST 공개 예정")
    print(f"::notice::만든 직후 주소: {post.get('url', '')} / 상태: {post.get('status', '')}")
    res = requests.patch(f"{API}/blogs/{blog}/posts/{post['id']}", json={"title": meta["title"]},
                         headers=h, timeout=60)
    _ok(res, "제목 바꾸기")
    sched = post.get("_scheduled_at")
    post = res.json()
    if sched:  # 한 시간 안에 공개되므로 기록은 LIVE로 둔다(관련 글·점검 대상에 포함)
        post["status"], post["_scheduled_at"] = "LIVE", sched
    print(f"::notice::제목 바꾼 뒤 주소: {post.get('url', '')} / 상태: {post.get('status', '')}")
    return post


REGION_LABELS = ["서울", "경기", "인천", "지방"] if _blog is None else _blog.REGION_LABELS
TYPE_LABELS = (["청약일정", "경쟁률", "당첨가점", "무순위", "청약통계", "실거래가", "월간정리", "청약가이드"]
               if _blog is None else _blog.TYPE_LABELS)
MAX_LINKS = 6


def _live(posts: list[dict]) -> list[dict]:
    return sorted([p for p in posts if p.get("url") and p.get("status") == "LIVE"],
                  key=lambda p: p.get("published_at", ""), reverse=True)


def related_block(no: str, exclude_id: str | None = None, labels: list | None = None,
                  extra: list[dict] | None = None) -> str:
    """내부 링크 묶음. ① 이 단지 다른 글 ② 같은 지역 최근 글 ③ 같은 종류 최근 글 순서로 최대 6개.
    공개된 글(url 있는 LIVE)만 링크한다."""
    posts = json.loads(PUBLISHED.read_text("utf-8"))["posts"] if PUBLISHED.exists() else []
    posts = _live(posts + (extra or []))
    labels = labels or []
    me = next((p for p in posts if exclude_id and p.get("blogger_id") == exclude_id), None)
    if me and not labels:
        labels = me.get("labels", [])
    used = {exclude_id}
    groups = []

    def pick(title: str, cond, limit: int) -> None:
        room = MAX_LINKS - sum(len(g[1]) for g in groups)
        items = [p for p in posts if p.get("blogger_id") not in used and cond(p)][:min(limit, room)]
        for p in items:
            used.add(p.get("blogger_id"))
        if items:
            groups.append((title, items))

    if no:
        pick("이 단지 다른 글", lambda p: p.get("house_manage_no") == no, 4)
    region = next((l for l in labels if l in REGION_LABELS), None)
    kind = next((l for l in labels if l in TYPE_LABELS), None)
    if region:
        name = "지방" if region == "지방" else region
        pick(f"{name} 다른 청약 글", lambda p: region in p.get("labels", []), 3)
    if kind:
        pick(f"다른 단지 {kind} 글", lambda p: kind in p.get("labels", []), 2)
    if not groups:
        pick("최근 청약 글", lambda p: True, 3)
    if not groups:
        return ""
    html = ""
    for title, items in groups:
        lis = "".join(f'<li style="margin:0 0 4px;"><a href="{p["url"]}">{p["title"]}</a></li>' for p in items)
        html += (f'<p style="font-weight:700;margin:16px 0 6px;">{title}</p>'
                 f'<ul style="margin:0;padding-left:20px;">{lis}</ul>')
    return f'{REL_START}<div style="margin:24px 0 0;">{html}</div>{REL_END}'


def replace_related(html: str, block: str) -> str:
    if REL_START in html and REL_END in html:
        a, rest = html.split(REL_START, 1)
        _, b = rest.split(REL_END, 1)
        return a + block + b
    return html + block


def refresh_related(token: str, limit: int = 20) -> int:
    """새 글이 생긴 뒤, 링크 묶음이 달라지는 이전 공개 글들을 갱신한다 (같은 단지·지역·종류)."""
    if not PUBLISHED.exists():
        return 0
    blog = os.environ["BLOGGER_BLOG_ID"]
    h = {"Authorization": f"Bearer {token}"}
    data = json.loads(PUBLISHED.read_text("utf-8"))
    n = 0
    for p in data["posts"]:
        if n >= limit or p.get("status") != "LIVE" or not p.get("blogger_id"):
            continue
        block = related_block(p.get("house_manage_no", ""), exclude_id=p["blogger_id"], labels=p.get("labels"))
        if block == p.get("related_html"):
            continue
        res = requests.get(f"{API}/blogs/{blog}/posts/{p['blogger_id']}", headers=h, timeout=60)
        if not res.ok:
            continue
        html = res.json().get("content", "")
        new_html = replace_related(html, block)
        if new_html != html:
            _ok(requests.patch(f"{API}/blogs/{blog}/posts/{p['blogger_id']}", json={"content": new_html},
                               headers=h, timeout=60), f"링크 갱신 {p.get('title')}")
            n += 1
        p["related_html"] = block
    PUBLISHED.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
    return n


def record(meta: dict, body: str, post: dict, file_name: str = "") -> None:
    PUBLISHED.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(PUBLISHED.read_text("utf-8")) if PUBLISHED.exists() else {"posts": []}
    heads = [l.strip("# ").strip() for l in body.splitlines() if l.startswith("## ")]
    data["posts"].append({
        "house_manage_no": str(meta.get(UNIT_KEY) or ""),
        "type": meta["type"], "labels": list(meta.get("labels") or []), "title": meta["title"], "keyword": meta["keyword"], "file": file_name,
        "opening": meta["opening"], "angle": meta.get("angle", ""), "url": post.get("url", ""), "blogger_id": post.get("id"),
        "status": post.get("status"), "published_at": post.get("_scheduled_at") or datetime.now(KST).isoformat(),
        "headings_pattern": sorted({re.sub(r"[\d,.]+", "N", x) for x in heads}),
    })
    PUBLISHED.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")


def rerender() -> int:
    """이미 올린 글을 posts/published/의 원고로 다시 만들어 내용만 바꾼다 (꾸밈·카드 수정 반영용).
    제목·주소·날짜는 건드리지 않는다."""
    if not PUBLISHED.exists():
        return 0
    token = access_token()
    blog = os.environ["BLOGGER_BLOG_ID"]
    h = {"Authorization": f"Bearer {token}"}
    n = 0
    data = json.loads(PUBLISHED.read_text("utf-8"))
    for p in data["posts"]:
        src = DONE / p["file"] if p.get("file") else None
        if not src or not src.exists() or not p.get("blogger_id"):
            print(f"::warning::원고를 찾지 못해 건너뜀: {p.get('title')}")
            continue
        meta, body = split_post(src.read_text("utf-8"))
        no = str(meta.get(UNIT_KEY) or "")
        p["labels"] = list(meta.get("labels") or [])
        block = related_block(no, exclude_id=p["blogger_id"], labels=p["labels"])
        p["related_html"] = block
        html = build_card(meta) + to_html(body) + method_link() + block
        _ok(requests.patch(f"{API}/blogs/{blog}/posts/{p['blogger_id']}",
                           json={"content": html, "title": meta["title"]},
                           headers=h, timeout=60), f"다시 만들기 {p.get('title')}")
        p["title"] = meta["title"]
        n += 1
    PUBLISHED.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
    print(f"::notice::{n}편 다시 만듦")
    return 0


PAGES_DIR = BASE / "pages"
PAGES_JSON = (ROOT / "data" / "pages.json") if _blog is None else (BASE / "data" / "pages.json")


def method_link() -> str:
    """모든 글 끝에 '분석 방법' 페이지 링크를 붙인다 (계산 방식을 공개해 신뢰를 높인다)."""
    if not PAGES_JSON.exists():
        return ""
    url = json.loads(PAGES_JSON.read_text("utf-8")).get("method.md", {}).get("url")
    if not url:
        return ""
    return (f'<p style="margin:1.6em 0 0;font-size:14px;color:#333333;">이 글의 숫자를 어떻게 계산했는지는 '
            f'<a href="{url}" style="color:#1a56db;">분석 방법과 데이터 출처</a>에 정리해 두었어요.</p>')


def publish_pages() -> int:
    """pages/*.md 가운데 머리말에 publish: true가 있는 것을 Blogger 고정 페이지로 올리거나 고친다."""
    token = access_token()
    blog = os.environ["BLOGGER_BLOG_ID"]
    h = {"Authorization": f"Bearer {token}"}
    known = json.loads(PAGES_JSON.read_text("utf-8")) if PAGES_JSON.exists() else {}
    # 기록이 없어도 이미 있는 페이지(같은 영문 주소)는 새로 만들지 않고 이어 쓴다
    live = _ok(requests.get(f"{API}/blogs/{blog}/pages", headers=h, timeout=60), "페이지 목록").json().get("items", [])
    for f in sorted(PAGES_DIR.glob("*.md")):
        text = f.read_text("utf-8")
        if not text.startswith("---"):
            continue
        meta, body = split_post(text)
        if meta.get("publish") is not True:
            continue
        payload = {"title": meta["title"], "content": to_html(body)}
        slug = meta.get("slug")
        if f.name not in known and slug:
            hit = next((pg for pg in live if str(pg.get("url", "")).endswith(f"/{slug}.html")), None)
            if hit:
                known[f.name] = {"id": hit["id"], "url": hit["url"], "title": meta["title"]}
        old = known.get(f.name, {})
        if slug and old.get("id") and not str(old.get("url", "")).endswith(f"/{slug}.html"):
            # 주소가 한글 제목으로 만들어진 경우: 지우고 영문 주소로 다시 만든다
            requests.delete(f"{API}/blogs/{blog}/pages/{old['id']}", headers=h, timeout=60)
            known.pop(f.name, None)
        if f.name in known and known[f.name].get("id"):
            res = _ok(_retry(lambda: requests.patch(f"{API}/blogs/{blog}/pages/{known[f.name]['id']}", json=payload,
                                                    headers=h, timeout=60)), f"페이지 고치기 {f.name}")
        else:
            first = {**payload, "title": slug} if slug else payload  # 영문 제목으로 만들어 주소를 고정
            res = _ok(requests.post(f"{API}/blogs/{blog}/pages", params={"isDraft": "false"}, json=first,
                                    headers=h, timeout=60), f"페이지 만들기 {f.name}")
            if slug:
                pid = res.json()["id"]
                res = _ok(_retry(lambda: requests.patch(f"{API}/blogs/{blog}/pages/{pid}",
                                                        json={"title": meta["title"]}, headers=h, timeout=60)), "페이지 제목")
        page = res.json()
        known[f.name] = {"id": page.get("id"), "url": page.get("url"), "title": meta["title"]}
        print(f"::notice::페이지: {meta['title']} → {page.get('url')}")
    PAGES_JSON.parent.mkdir(parents=True, exist_ok=True)
    PAGES_JSON.write_text(json.dumps(known, ensure_ascii=False, indent=1), "utf-8")
    return 0


def publish_drafts() -> int:
    """임시저장으로 올린 글을 공개한다. 주소를 영문으로 만들려고 제목을 slug로 바꿔 공개한 뒤 한글 제목으로 되돌린다."""
    if not PUBLISHED.exists():
        return 0
    token = access_token()
    blog = os.environ["BLOGGER_BLOG_ID"]
    h = {"Authorization": f"Bearer {token}"}
    data = json.loads(PUBLISHED.read_text("utf-8"))
    for p in data["posts"]:
        if p.get("status") != "DRAFT" or not p.get("blogger_id") or not p.get("file"):
            continue
        meta, _ = split_post((DONE / p["file"]).read_text("utf-8"))
        url = f"{API}/blogs/{blog}/posts/{p['blogger_id']}"
        _ok(requests.patch(url, json={"title": meta["slug"].replace("-", " ")}, headers=h, timeout=60), "slug 제목")
        _ok(requests.post(f"{url}/publish", headers=h, timeout=60), "공개")
        post = _ok(requests.patch(url, json={"title": meta["title"]}, headers=h, timeout=60), "한글 제목").json()
        p.update({"status": post.get("status"), "url": post.get("url", ""), "title": meta["title"],
                  "published_at": datetime.now(KST).isoformat()})
        print(f"::notice::공개: {meta['title']} → {post.get('url')}")
    PUBLISHED.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
    return 0


def main() -> int:
    files = sorted(PENDING.glob("*.md"))
    if not files:
        print("올릴 글이 없습니다.")
        return 0
    draft = CONFIG.get("mode", "draft") != "live"
    token = None
    summary, failed = [], 0
    for f in files:
        meta, body = split_post(f.read_text("utf-8"))
        if meta.get("type") == "guide" and meta.get("approved") is not True:
            # 청약 가이드는 사람이 한 번 보고 approved: true를 붙여야 발행한다
            REVIEW.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), REVIEW / f.name)
            summary.append(f"- 검토 대기: {meta.get('title')} (posts/review/)")
            continue
        errs = check_text(meta, body, recent_posts())
        from seo import seo_errors  # 검색 노출(SEO·AEO·GEO) 필수 항목도 통과해야 발행
        errs += seo_errors(meta, body)
        if errs:
            failed += 1
            HELD.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), HELD / f.name)
            (HELD / f"{f.stem}.errors.txt").write_text("\n".join(errs), "utf-8")
            summary.append(f"- 보류: {meta.get('title')} ({len(errs)}건)")
            continue
        token = token or access_token()
        no = str(meta.get(UNIT_KEY) or "")
        html = build_card(meta) + to_html(body) + method_link() + related_block(no, labels=meta.get("labels"))
        post = post_to_blogger(token, meta, html, draft)
        record(meta, body, post, f.name)
        try:  # 발행 시점 숫자 근거를 얼려 둔다(이후 데이터가 다시 계산돼도 이 글은 발행일 기준으로 검사)
            from check import save_snapshot, used_valid_numbers
            mod = _blog if _blog is not None else __import__("check")
            nums = used_valid_numbers(body, mod.allowed_set(dict(meta, _file=f.name), body))
            save_snapshot(BLOG, f.name, nums, datetime.now(KST).date().isoformat())
        except Exception as e:  # noqa: BLE001
            print(f"::warning::스냅샷 저장 실패: {type(e).__name__}: {e}")
        if not draft:
            refreshed = refresh_related(token)
            if refreshed:
                summary.append(f"  · 이전 글 {refreshed}편의 관련 글 링크 갱신")
        DONE.mkdir(parents=True, exist_ok=True)
        shutil.move(str(f), DONE / f.name)
        summary.append(f"- {'임시저장' if draft else ('예약 발행 ' + post['_scheduled_at'][11:16] if post.get('_scheduled_at') else '발행')}: {meta['title']} {post.get('url', '')}")

    queue = len(list(((ROOT / "data" / "queue") if _blog is None else (BASE / "data" / "queue")).glob("*.md")))
    if queue < 10:
        summary.append(f"- 경고: 예비 글이 {queue}편입니다 (10편 미만).")
    text = "\n".join(summary)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        Path(os.environ["GITHUB_STEP_SUMMARY"]).write_text("## 발행 결과\n" + text + "\n", "utf-8")
    return 1 if failed else 0


def list_blogs() -> int:
    """이 계정(토큰)으로 관리하는 블로그 목록과 ID를 출력하고 data/blogs.json에 저장한다."""
    h = {"Authorization": f"Bearer {access_token()}"}
    res = _ok(requests.get(f"{API}/users/self/blogs", headers=h, timeout=60), "블로그 목록")
    items = [{"id": b["id"], "name": b.get("name", ""), "url": b.get("url", ""), "posts": b.get("posts", {}).get("totalItems", 0)}
             for b in res.json().get("items", [])]
    for b in items:
        print(f"::notice::{b['name']} | {b['url']} | id={b['id']} | 글 {b['posts']}편")
    (ROOT / "data" / "blogs.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), "utf-8")
    return 0


if __name__ == "__main__":
    try:
        if "--blogs" in sys.argv:
            sys.exit(list_blogs())
        if "--rerender" in sys.argv:
            sys.exit(rerender())
        if "--publish-drafts" in sys.argv:
            sys.exit(publish_drafts())
        if "--pages" in sys.argv:
            sys.exit(publish_pages())
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        print(f"::error::{type(e).__name__}: {str(e)[:400]}")
        raise
