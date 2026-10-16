"""검색엔진 등록 흔적 점검: 홈 HTML의 소유확인 메타태그, robots.txt, sitemap, RSS."""
import re, time, requests
H = {"User-Agent": "Mozilla/5.0 (regcheck)"}
import sys
for h in (sys.argv[1:] or ["daily-cheongyak", "jeonse-ondogye", "gongmoju-breakdown", "gwanribi-dotbogi"]):
    base = f"https://{h}.blogspot.com"
    def get(u):
        for w in (0, 20, 60, 120):
            time.sleep(w or 2)
            try:
                r = requests.get(u, headers=H, timeout=30)
            except Exception as e:
                last = str(e); continue
            if r.status_code != 429:
                return r
        return None
    home = get(base + "/")
    metas = re.findall(r"<meta[^>]*(?:verification|msvalidate|naver)[^>]*>", home.text if home else "", re.I)
    desc = re.findall(r"<meta[^>]*name=['\"]description['\"][^>]*>", home.text if home else "", re.I)
    robots = get(base + "/robots.txt")
    sm = get(base + "/sitemap.xml")
    rss = get(base + "/feeds/posts/default?alt=rss")
    naver = "naver" if any("naver" in m for m in metas) else "-"
    others = [m for m in metas if "naver" not in m]
    rb = (robots.text if robots else "").strip().replace(chr(10), " | ")[:200]
    print(f"::notice::{h} home={home.status_code if home else None} naver={naver} other={others} sm={sm.status_code if sm else None} rss={rss.status_code if rss else None} robots={robots.status_code if robots else None} [{rb}]")
    time.sleep(40)
