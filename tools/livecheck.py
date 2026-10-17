"""공개 페이지에 특정 문자열이 있는지 확인: python tools/livecheck.py URL '문자열1|문자열2' ..."""
import sys, time, requests
args = sys.argv[1:]
for i in range(0, len(args), 2):
    url, keys = args[i], args[i + 1].split("|")
    r = None
    for w in (0, 30, 90, 150):
        time.sleep(w or 3)
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (livecheck)"}, timeout=30)
        except Exception:
            continue
        if r.status_code != 429:
            break
    body = r.text if r is not None else ""
    res = ", ".join(f"{k}={'O' if k in body else 'X'}" for k in keys)
    print(f"::notice::{url.split('/')[2].split('.')[0]}{url[-30:]} {r.status_code if r is not None else None} {res}")
    time.sleep(20)
