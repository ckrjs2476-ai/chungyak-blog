"""Blogger 조회수(블로그별 7일·30일·전체) → data/traffic.json, data/traffic.md. Actions에서 실행."""
import json, os, time, requests
from datetime import datetime, timedelta, timezone
from pathlib import Path
KST = timezone(timedelta(hours=9))
tok = requests.post("https://oauth2.googleapis.com/token", data={
    "client_id": os.environ["BLOGGER_CLIENT_ID"], "client_secret": os.environ["BLOGGER_CLIENT_SECRET"],
    "refresh_token": os.environ["BLOGGER_REFRESH_TOKEN"], "grant_type": "refresh_token"}, timeout=30).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}
blogs = {"청약노트": os.environ["BLOGGER_BLOG_ID"], "전세 온도계": "5197834942352686134",
         "공모주 뜯어보기": "899799118910718337", "관리비 돋보기": "1893946611364166783"}
out = {"date": datetime.now(KST).date().isoformat(), "blogs": {}}
for name, bid in blogs.items():
    r = requests.get(f"https://www.googleapis.com/blogger/v3/blogs/{bid}/pageviews",
                     params=[("range", "7DAYS"), ("range", "30DAYS"), ("range", "all")], headers=H, timeout=30)
    counts = {c["timeRange"]: int(c["count"]) for c in r.json().get("counts", [])} if r.ok else {"error": r.status_code}
    out["blogs"][name] = counts
    print(f"::notice::{name} 조회수 {counts}")
    time.sleep(1)
p = Path("data/traffic.json")
hist = json.loads(p.read_text("utf-8")) if p.exists() else []
hist = [h for h in hist if h.get("date") != out["date"]] + [out]
p.write_text(json.dumps(hist[-120:], ensure_ascii=False, indent=1), "utf-8")
lines = ["# 블로그 조회수 (Blogger 통계, 본인 조회 제외 설정에 따름)", "", "| 날짜 | 블로그 | 7일 | 30일 | 전체 |", "| --- | --- | --- | --- | --- |"]
for h in hist[-14:]:
    for n, c in h["blogs"].items():
        lines.append(f"| {h['date']} | {n} | {c.get('SEVEN_DAYS', '-')} | {c.get('THIRTY_DAYS', '-')} | {c.get('ALL_TIME', '-')} |")
Path("data/traffic.md").write_text("\n".join(lines) + "\n", "utf-8")
