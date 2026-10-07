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
from card import build_card  # noqa: E402
from check import check_text, recent_posts, split_post  # noqa: E402

REL_START, REL_END = "<!--related-start-->", "<!--related-end-->"
TYPE_NAME = {"notice": "청약 일정·분양가", "competition": "경쟁률 결과", "score": "당첨 가점",
             "remainder": "무순위·잔여 세대"}

ROOT = Path(__file__).resolve().parent.parent
PENDING, DONE, HELD, REVIEW = (ROOT / "posts" / d for d in ("pending", "published", "held", "review"))
PUBLISHED = ROOT / "data" / "published.json"
CONFIG = json.loads((ROOT / "config.json").read_text("utf-8"))
KST = timezone(timedelta(hours=9))
API = "https://www.googleapis.com/blogger/v3"


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


def post_to_blogger(token: str, meta: dict, html: str, draft: bool) -> dict:
    blog = os.environ["BLOGGER_BLOG_ID"]
    h = {"Authorization": f"Bearer {token}"}
    # 1) 영문 slug를 제목으로 먼저 만들어 주소(퍼머링크)를 영문으로 고정
    # 2) 그다음 제목을 한글로 바꾼다. (Blogger 동작에 기대는 방식이라 첫 테스트에서 주소를 꼭 확인)
    body = {"kind": "blogger#post", "title": meta["slug"].replace("-", " "),
            "content": html, "labels": meta.get("labels", [])}
    res = requests.post(f"{API}/blogs/{blog}/posts", params={"isDraft": str(draft).lower()},
                        json=body, headers=h, timeout=60)
    _ok(res, "글 만들기")
    post = res.json()
    print(f"::notice::만든 직후 주소: {post.get('url', '')} / 상태: {post.get('status', '')}")
    res = requests.patch(f"{API}/blogs/{blog}/posts/{post['id']}", json={"title": meta["title"]},
                         headers=h, timeout=60)
    _ok(res, "제목 바꾸기")
    post = res.json()
    print(f"::notice::제목 바꾼 뒤 주소: {post.get('url', '')} / 상태: {post.get('status', '')}")
    return post


def related_block(no: str, exclude_id: str | None = None, extra: list[dict] | None = None) -> str:
    """같은 단지의 다른 글 목록. 공개된 글(url 있는 LIVE)만 링크한다."""
    if not no:
        return ""
    posts = json.loads(PUBLISHED.read_text("utf-8"))["posts"] if PUBLISHED.exists() else []
    posts = posts + (extra or [])
    items = [p for p in posts if p.get("house_manage_no") == no and p.get("url")
             and p.get("status") == "LIVE" and p.get("blogger_id") != exclude_id]
    if not items:
        return ""
    lis = "".join(f'<li><a href="{p["url"]}">{p["title"]}</a></li>' for p in items)
    return (f'{REL_START}<div style="margin:24px 0 0;"><p style="font-weight:700;margin:0 0 6px;">'
            f'이 단지 다른 글</p><ul style="margin:0;padding-left:20px;">{lis}</ul></div>{REL_END}')


def replace_related(html: str, block: str) -> str:
    if REL_START in html and REL_END in html:
        a, rest = html.split(REL_START, 1)
        _, b = rest.split(REL_END, 1)
        return a + block + b
    return html + block


def refresh_siblings(token: str, no: str) -> int:
    """새 글이 생긴 뒤 같은 단지의 이전 공개 글들의 '이 단지 다른 글' 목록을 갱신한다."""
    if not no or not PUBLISHED.exists():
        return 0
    blog = os.environ["BLOGGER_BLOG_ID"]
    h = {"Authorization": f"Bearer {token}"}
    n = 0
    for p in json.loads(PUBLISHED.read_text("utf-8"))["posts"]:
        if p.get("house_manage_no") != no or p.get("status") != "LIVE" or not p.get("blogger_id"):
            continue
        res = requests.get(f"{API}/blogs/{blog}/posts/{p['blogger_id']}", headers=h, timeout=60)
        if not res.ok:
            continue
        html = res.json().get("content", "")
        new_html = replace_related(html, related_block(no, exclude_id=p["blogger_id"]))
        if new_html != html:
            requests.patch(f"{API}/blogs/{blog}/posts/{p['blogger_id']}", json={"content": new_html},
                           headers=h, timeout=60).raise_for_status()
            n += 1
    return n


def record(meta: dict, body: str, post: dict, file_name: str = "") -> None:
    data = json.loads(PUBLISHED.read_text("utf-8")) if PUBLISHED.exists() else {"posts": []}
    heads = [l.strip("# ").strip() for l in body.splitlines() if l.startswith("## ")]
    data["posts"].append({
        "house_manage_no": str(meta.get("house_manage_no") or ""),
        "type": meta["type"], "title": meta["title"], "keyword": meta["keyword"], "file": file_name,
        "opening": meta["opening"], "url": post.get("url", ""), "blogger_id": post.get("id"),
        "status": post.get("status"), "published_at": datetime.now(KST).isoformat(),
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
        no = str(meta.get("house_manage_no") or "")
        html = build_card(meta) + to_html(body) + related_block(no, exclude_id=p["blogger_id"])
        _ok(requests.patch(f"{API}/blogs/{blog}/posts/{p['blogger_id']}",
                           json={"content": html, "title": meta["title"]},
                           headers=h, timeout=60), f"다시 만들기 {p.get('title')}")
        p["title"] = meta["title"]
        n += 1
    PUBLISHED.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
    print(f"::notice::{n}편 다시 만듦")
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
        if errs:
            failed += 1
            HELD.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), HELD / f.name)
            (HELD / f"{f.stem}.errors.txt").write_text("\n".join(errs), "utf-8")
            summary.append(f"- 보류: {meta.get('title')} ({len(errs)}건)")
            continue
        token = token or access_token()
        no = str(meta.get("house_manage_no") or "")
        html = build_card(meta) + to_html(body) + related_block(no)
        post = post_to_blogger(token, meta, html, draft)
        record(meta, body, post, f.name)
        if not draft:
            refreshed = refresh_siblings(token, no)
            if refreshed:
                summary.append(f"  · 같은 단지 이전 글 {refreshed}편에 링크 추가")
        DONE.mkdir(parents=True, exist_ok=True)
        shutil.move(str(f), DONE / f.name)
        summary.append(f"- {'임시저장' if draft else '발행'}: {meta['title']} {post.get('url', '')}")

    queue = len(list((ROOT / "data" / "queue").glob("*.md")))
    if queue < 10:
        summary.append(f"- 경고: 예비 글이 {queue}편입니다 (10편 미만).")
    text = "\n".join(summary)
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        Path(os.environ["GITHUB_STEP_SUMMARY"]).write_text("## 발행 결과\n" + text + "\n", "utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(rerender() if "--rerender" in sys.argv else main())
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        print(f"::error::{type(e).__name__}: {str(e)[:400]}")
        raise
