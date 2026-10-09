"""네이버 검색광고 API(키워드 도구)로 글 후보 단지 이름의 월간 검색 수를 받아 data/search_volume.json에 저장한다.

analysis.py가 이 값을 글감 우선순위에 반영한다. 키가 없으면 아무것도 하지 않고 끝난다(실패로 치지 않음).
환경변수: NAVER_AD_CUSTOMER_ID, NAVER_AD_API_KEY, NAVER_AD_SECRET
API 문서: https://naver.github.io/searchad-apidoc/ (키워드 도구 /keywordstool)
- hintKeywords는 공백 없이, 한 번에 5개까지
- 검색 수가 10 미만이면 "< 10" 문자열로 온다
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
JOBS = ROOT / "data" / "jobs.json"
OUT = ROOT / "data" / "search_volume.json"
KST = timezone(timedelta(hours=9))
API = "https://api.searchad.naver.com"
REFRESH_DAYS = 3   # 같은 이름은 3일에 한 번만 다시 조회
MAX_LOOKUPS = 40   # 한 번 실행에 조회하는 이름 수 상한


def _sign(ts: str, method: str, uri: str, secret: str) -> str:
    msg = f"{ts}.{method}.{uri}".encode()
    return base64.b64encode(hmac.new(secret.encode(), msg, hashlib.sha256).digest()).decode()


def name_variants(name: str) -> list[str]:
    """'힐스테이트 고덕엘리스트 A12BL 공공분양주택' → ['힐스테이트고덕엘리스트A12BL공공분양주택', '힐스테이트고덕엘리스트']"""
    base = re.sub(r"\(.*?\)|\[.*?\]", " ", str(name))
    full = re.sub(r"[^0-9A-Za-z가-힣]", "", base)
    short = re.sub(r"\b[A-Z]?\d+[A-Z]*(BL|블록)\b|공공분양주택|공공분양|신혼희망타운|\d+단지|\d+회차|\d+차",
                   " ", base, flags=re.I)
    short = re.sub(r"[^0-9A-Za-z가-힣]", "", short)
    out = []
    if len(short) < 6 or len(short) < len(full) * 0.5:
        short = ""  # '인천계양'처럼 지역명만 남으면 단지 검색량이 아니므로 버린다
    for v in (full, short):
        if 2 <= len(v) <= 40 and v not in out:
            out.append(v)
    return out[:2]


def _num(v) -> int:
    s = str(v).replace(",", "").strip()
    if s.startswith("<"):
        return 5  # "< 10"
    try:
        return int(float(s))
    except ValueError:
        return 0


def lookup(hints: list[str], cid: str, key: str, secret: str) -> dict[str, int]:
    uri = "/keywordstool"
    ts = str(int(time.time() * 1000))
    headers = {"X-Timestamp": ts, "X-API-KEY": key, "X-Customer": str(cid),
               "X-Signature": _sign(ts, "GET", uri, secret)}
    res = requests.get(API + uri, params={"hintKeywords": ",".join(hints), "showDetail": "1"},
                       headers=headers, timeout=30)
    if res.status_code != 200:
        print(f"::warning::검색광고 API HTTP {res.status_code}: {res.text[:200]}")
        return {}
    found = {}
    wanted = {h.upper(): h for h in hints}
    for k in res.json().get("keywordList", []):
        rel = str(k.get("relKeyword", "")).replace(" ", "").upper()
        if rel in wanted:
            found[wanted[rel]] = _num(k.get("monthlyPcQcCnt")) + _num(k.get("monthlyMobileQcCnt"))
    return found


def main() -> int:
    cid, key, secret = (os.environ.get(k, "") for k in ("NAVER_AD_CUSTOMER_ID", "NAVER_AD_API_KEY", "NAVER_AD_SECRET"))
    if not (cid and key and secret):
        print("::notice::네이버 검색광고 API 키가 없어 검색량 조회를 건너뜁니다.")
        return 0
    if not JOBS.exists():
        return 0
    cache = json.loads(OUT.read_text("utf-8")) if OUT.exists() else {"names": {}}
    today = datetime.now(KST).date()
    names = []
    for j in json.loads(JOBS.read_text("utf-8")).get("jobs", []):
        n = str(j.get("name") or "")
        if n and n not in names:
            names.append(n)
    done = 0
    for n in names:
        old = cache["names"].get(n)
        if old and (today - datetime.fromisoformat(old["date"]).date()).days < REFRESH_DAYS:
            continue
        if done >= MAX_LOOKUPS:
            break
        variants = name_variants(n)
        if not variants:
            continue
        vols = lookup(variants, cid, key, secret)
        done += 1
        cache["names"][n] = {"date": today.isoformat(), "variants": variants,
                             "volume": max(vols.values()) if vols else 0, "by_variant": vols}
        time.sleep(0.3)  # 호출 간격
    cache["updated"] = today.isoformat()
    OUT.write_text(json.dumps(cache, ensure_ascii=False, indent=1), "utf-8")
    top = sorted(((v["volume"], k) for k, v in cache["names"].items()), reverse=True)[:5]
    print(f"::notice::검색량 조회 {done}건. 상위: {[f'{k[:12]} {v}' for v, k in top]}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001  검색량은 보조 정보라 실패해도 전체를 멈추지 않는다
        print(f"::warning::검색량 조회 실패 {type(e).__name__}: {str(e)[:300]}")
        sys.exit(0)
