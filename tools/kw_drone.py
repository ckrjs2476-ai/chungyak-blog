"""드론 정보노트 키워드 조사 (Actions에서 실행).
1) 네이버 검색광고 키워드 도구: 씨앗 키워드의 연관 키워드 + 월 검색 수(PC+모바일) + 경쟁 정도(compIdx)
2) 구글 자동완성: 씨앗마다 구글이 제안하는 검색어
자격증 취득 관련(필기·실기·비용·국비 등)은 2026-12-31까지 제외 표시.
결과: blogs/drone/data/keywords.json, blogs/drone/data/keywords.md"""
import base64, hashlib, hmac, json, os, re, time
from pathlib import Path
import requests

SEEDS = ["드론", "드론비행금지구역", "드론비행규정", "드론기체신고", "드론야간비행", "드론비행승인", "드론보험",
         "드론직업", "드론방제", "드론촬영", "드론배송", "드론쇼", "드론택시", "드론뉴스", "드론종류", "미니드론",
         "농업용드론", "드론배터리", "드론항공촬영", "드론규제", "드론원스톱", "드론조종", "드론교관", "드론측량",
         "드론연봉", "드론산업", "드론축구", "UAM", "드론기술", "드론법"]
EXCLUDE = re.compile(r"(자격증|필기|실기|국비|국가지원|내일배움|교육비|응시료|합격|학원|교육원|시험|과정)")
API = "https://api.searchad.naver.com"
cid, key, sec = (os.environ.get(k, "") for k in ("NAVER_AD_CUSTOMER_ID", "NAVER_AD_API_KEY", "NAVER_AD_SECRET"))


def naver(hints):
    ts = str(int(time.time() * 1000)); uri = "/keywordstool"
    sig = base64.b64encode(hmac.new(sec.encode(), f"{ts}.GET.{uri}".encode(), hashlib.sha256).digest()).decode()
    r = requests.get(API + uri, params={"hintKeywords": ",".join(hints), "showDetail": "1"},
                     headers={"X-Timestamp": ts, "X-API-KEY": key, "X-Customer": cid, "X-Signature": sig}, timeout=30)
    r.raise_for_status()
    return r.json().get("keywordList", [])


def n(v):
    return 5 if isinstance(v, str) and "<" in v else int(v or 0)


out = {}
for i in range(0, len(SEEDS), 5):
    try:
        for k in naver(SEEDS[i:i + 5]):
            kw = k["relKeyword"]
            if "드론" not in kw and kw not in ("UAM",):
                continue
            vol = n(k.get("monthlyPcQcCnt")) + n(k.get("monthlyMobileQcCnt"))
            out[kw] = {"kw": kw, "naver_month": vol, "comp": k.get("compIdx"), "excluded": bool(EXCLUDE.search(kw)), "google_suggest": []}
    except Exception as e:  # noqa: BLE001
        print(f"::warning::naver {SEEDS[i:i+5]} {e}")
    time.sleep(1)
for s in SEEDS:
    q = s if s == "UAM" else re.sub(r"^드론", "드론 ", s)
    try:
        r = requests.get("https://suggestqueries.google.com/complete/search", params={"client": "firefox", "hl": "ko", "q": q}, timeout=15)
        for sug in r.json()[1]:
            key2 = sug.replace(" ", "")
            row = out.setdefault(key2, {"kw": sug, "naver_month": None, "comp": None, "excluded": bool(EXCLUDE.search(sug)), "google_suggest": []})
            row["google_suggest"].append(q)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::google {q} {e}")
    time.sleep(0.5)
rows = sorted(out.values(), key=lambda r: (r["excluded"], -(r["naver_month"] or 0)))
Path("blogs/drone/data/keywords.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), "utf-8")
lines = ["# 드론 키워드 조사", "", f"연관 키워드 {len(rows)}개 (자격증 관련 제외 표시 {sum(r['excluded'] for r in rows)}개)", "",
         "| 키워드 | 네이버 월 검색 | 경쟁 | 구글 자동완성 | 제외 |", "| --- | --- | --- | --- | --- |"]
for r in rows:
    lines.append(f"| {r['kw']} | {r['naver_month'] if r['naver_month'] is not None else '-'} | {r['comp'] or '-'} | {'O' if r['google_suggest'] else ''} | {'제외' if r['excluded'] else ''} |")
Path("blogs/drone/data/keywords.md").write_text("\n".join(lines) + "\n", "utf-8")
print(f"::notice::키워드 {len(rows)}개")
