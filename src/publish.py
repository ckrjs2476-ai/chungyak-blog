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
from check import check_text, recent_posts, split_post  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PENDING, DONE, HELD = (ROOT / "posts" / d for d in ("pending", "published", "held"))
PUBLISHED = ROOT / "data" / "published.json"
CONFIG = json.loads((ROOT / "config.json").read_text("utf-8"))
KST = timezone(timedelta(hours=9))
API = "https://www.googleapis.com/blogger/v3"


def access_token() -> str:
    res = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": os.environ["BLOGGER_CLIENT_ID"],
        "client_secret": os.environ["BLOGGER_CLIENT_SECRET"],
        "refresh_token": os.environ["BLOGGER_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }, timeout=30)
    res.raise_for_status()
    return res.json()["access_token"]


def to_html(body: str) -> str:
    return markdown.markdown(body, extensions=["tables", "sane_lists"])


def post_to_blogger(token: str, meta: dict, html: str, draft: bool) -> dict:
    blog = os.environ["BLOGGER_BLOG_ID"]
    h = {"Authorization": f"Bearer {token}"}
    # 1) 영문 slug를 제목으로 먼저 만들어 주소(퍼머링크)를 영문으로 고정
    # 2) 그다음 제목을 한글로 바꾼다. (Blogger 동작에 기대는 방식이라 첫 테스트에서 주소를 꼭 확인)
    body = {"kind": "blogger#post", "title": meta["slug"].replace("-", " "),
            "content": html, "labels": meta.get("labels", [])}
    res = requests.post(f"{API}/blogs/{blog}/posts", params={"isDraft": str(draft).lower()},
                        json=body, headers=h, timeout=60)
    res.raise_for_status()
    post = res.json()
    res = requests.patch(f"{API}/blogs/{blog}/posts/{post['id']}", json={"title": meta["title"]},
                         headers=h, timeout=60)
    res.raise_for_status()
    return res.json()


def record(meta: dict, body: str, post: dict) -> None:
    data = json.loads(PUBLISHED.read_text("utf-8")) if PUBLISHED.exists() else {"posts": []}
    heads = [l.strip("# ").strip() for l in body.splitlines() if l.startswith("## ")]
    data["posts"].append({
        "house_manage_no": str(meta.get("house_manage_no") or ""),
        "type": meta["type"], "title": meta["title"], "keyword": meta["keyword"],
        "opening": meta["opening"], "url": post.get("url", ""), "blogger_id": post.get("id"),
        "status": post.get("status"), "published_at": datetime.now(KST).isoformat(),
        "headings_pattern": sorted({re.sub(r"[\d,.]+", "N", x) for x in heads}),
    })
    PUBLISHED.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")


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
        errs = check_text(meta, body, recent_posts())
        if errs:
            failed += 1
            HELD.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), HELD / f.name)
            (HELD / f"{f.stem}.errors.txt").write_text("\n".join(errs), "utf-8")
            summary.append(f"- 보류: {meta.get('title')} ({len(errs)}건)")
            continue
        token = token or access_token()
        post = post_to_blogger(token, meta, to_html(body), draft)
        record(meta, body, post)
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
    sys.exit(main())
