"""Blogger 예약 발행 시 주소(퍼머링크)가 영문 slug로 유지되는지 시험. 끝나면 글을 임시보관으로 되돌린다."""
import os, sys, time
from datetime import datetime, timedelta, timezone
import requests
sys.path.insert(0, "src")
os.environ.setdefault("BLOG_KEY", "gwanribi")
from publish import access_token, API
blog = os.environ["BLOGGER_BLOG_ID"]
h = {"Authorization": f"Bearer {access_token()}"}
old = [p for p in requests.get(f"{API}/blogs/{blog}/posts", params={"status": "draft", "fetchBodies": "false"}, headers=h, timeout=60).json().get("items", [])
       if p.get("title") in ("예약 발행 시험 글", "schedule test check")]
if old:
    r = old[0]; pid = r["id"]
    requests.patch(f"{API}/blogs/{blog}/posts/{pid}", json={"title": "schedule test check"}, headers=h, timeout=60)
else:
    r = requests.post(f"{API}/blogs/{blog}/posts", params={"isDraft": "true"}, headers=h, timeout=60,
                      json={"title": "schedule test check", "content": "<p>예약 발행 시험 글입니다. 곧 임시보관으로 되돌립니다.</p>"}).json()
    pid = r["id"]
print("found_old", len(old)); print("::notice::draft", r.get("status"), r.get("url"))
when = (datetime.now(timezone.utc) + timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
r = requests.post(f"{API}/blogs/{blog}/posts/{pid}/publish", params={"publishDate": when}, headers=h, timeout=60)
print("::notice::publish", r.status_code, r.json().get("status"), r.json().get("url"), r.json().get("published"))
r = requests.patch(f"{API}/blogs/{blog}/posts/{pid}", json={"title": "예약 발행 시험 글"}, headers=h, timeout=60)
print("::notice::title", r.status_code, r.json().get("status"), r.json().get("url"))
time.sleep(200)
r = requests.get(f"{API}/blogs/{blog}/posts/{pid}", headers=h, timeout=60).json()
print("::notice::after", r.get("status"), r.get("url"), r.get("title"))
u = r.get("url")
if u:
    print("::notice::live", requests.get(u, timeout=30).status_code)
r = requests.post(f"{API}/blogs/{blog}/posts/{pid}/revert", headers=h, timeout=60)
print("::notice::revert", r.status_code, r.json().get("status"))
