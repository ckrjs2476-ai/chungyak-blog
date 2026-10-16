"""검색엔진 등록 흔적 점검: 홈 HTML의 소유확인 메타태그, robots.txt, sitemap, RSS."""
import re, time, requests
H = {"User-Agent": "Mozilla/5.0 (regcheck)"}
for h in ["daily-cheongyak", "jeonse-ondogye", "gongmoju-breakdown", "gwanribi-dotbogi"]:
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
    print(f"::notice::{h} home={home.status_code if home else None} verify={metas or '없음'} desc={'있음' if desc else '없음'}")
    print(f"::notice::{h} robots={robots.status_code if robots else None} [{(robots.text if robots else '').strip().replace(chr(10),' | ')[:300]}]")
    print(f"::notice::{h} sitemap={sm.status_code if sm else None} rss={rss.status_code if rss else None} rss_items={(rss.text.count('<item>') if rss else 0)}")
    time.sleep(15)
