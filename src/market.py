"""국토교통부 아파트 매매 실거래가로 '청약 단지 주변 시세'와 '지역 실거래 동향'을 만든다.

1) 청약 단지 주소 → 시군구 코드(LAWD_CD 5자리): 행정안전부_법정동코드 API (data/market/codes.json에 저장)
2) 시군구별 최근 12개월 아파트 매매 실거래: 국토교통부_아파트 매매 실거래가 상세 자료 API
   (data/market/trades/<LAWD_CD>/<YYYYMM>.json, 지난달·이번 달은 신고가 늦게 들어오므로 매번 다시 받는다)
3) 시군구별 요약: data/market/regions/<LAWD_CD>.json (84㎡ 중앙값, 신축 중앙값, 읍면동별, 월별, 거래 많은 단지)
4) 단지별 지역 연결: data/market/unit_regions.json  → analysis.py가 단지 분석에 '주변 시세 비교'를 붙인다.

환경변수: DATA_GO_KR_KEY (청약홈과 같은 공공데이터포털 키, 두 API 활용신청 필요)
API 키가 없거나 신청 전이면 경고만 남기고 끝난다(전체 작업을 멈추지 않음).
"""
from __future__ import annotations

import json
import os
import re
import statistics
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
UNITS = ROOT / "data" / "units"
MARKET = ROOT / "data" / "market"
KST = timezone(timedelta(hours=9))
CODE_API = "https://apis.data.go.kr/1741000/StanReginCd/getStanReginCdList"
TRADE_API = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
MONTHS = 12
UNIT_DAYS = 150          # 공고 150일 안의 청약 단지 지역만 받는다
MAX_REGIONS_PER_RUN = 25  # 처음에는 여러 번에 나눠 채운다
AREA_84 = (80.0, 86.0)    # 전용 84㎡형으로 묶는 범위
NEW_BUILD_YEARS = 5       # 신축 기준: 준공 5년 이내
_seen_fields = False


def _key() -> str:
    key = os.environ.get("DATA_GO_KR_KEY", "")
    return key if "%" in key else urllib.parse.quote(key, safe="")


def _get(url: str, params: dict) -> requests.Response:
    """공공데이터포털은 가끔 응답이 늦다. 3번까지 다시 시도한다."""
    q = "&".join([f"serviceKey={_key()}"] + [f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()])
    last: Exception | None = None
    for attempt in range(3):
        try:
            return requests.get(f"{url}?{q}", timeout=60)
        except (requests.Timeout, requests.ConnectionError) as e:
            last = e
            time.sleep(3 * (attempt + 1))
    raise last  # type: ignore[misc]


_debug_left = 5


def _num(v) -> float | None:
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


# ---------- 1) 주소 → 시군구 코드 ----------
def _code_rows(prefix: str) -> list[dict]:
    res = _get(CODE_API, {"pageNo": 1, "numOfRows": 1000, "type": "json", "locatadd_nm": prefix})
    if res.status_code != 200:
        print(f"::warning::법정동코드 API HTTP {res.status_code}: {res.text[:200]}")
        return []
    try:
        body = res.json()
    except ValueError:
        print(f"::warning::법정동코드 API 응답이 JSON이 아님: {res.text[:200]}")
        return []
    rows: list[dict] = []

    def walk(x):
        if isinstance(x, dict):
            if isinstance(x.get("row"), list):
                rows.extend(r for r in x["row"] if isinstance(r, dict))
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(body)
    return rows


def lawd_for_address(addr: str, cache: dict) -> dict | None:
    """'경기도 화성특례시 만세구 향남읍 …' → {'lawd': '41xxx', 'name': '경기도 화성특례시 만세구', 'umd': '향남읍'}"""
    tokens = str(addr).split()
    for n in (3, 2, 1):
        if len(tokens) < n:
            continue
        prefix = " ".join(tokens[:n])
        if prefix in cache:
            hit = cache[prefix]
        else:
            hit = None
            for r in _code_rows(prefix):
                nm = str(r.get("locatadd_nm", "")).strip()
                code = str(r.get("region_cd", ""))
                if nm == prefix and len(code) == 10 and code[5:] == "00000" and code[2:5] != "000":
                    hit = {"lawd": code[:5], "name": nm}
                    break
            if hit is None and n >= 2:
                global _debug_left
                if _debug_left > 0:
                    _debug_left -= 1
                    rows = _code_rows(prefix)
                    print(f"::notice::법정동코드 못 찾음 '{prefix}': 응답 {len(rows)}행, 예시 "
                          f"{[(r.get('locatadd_nm'), r.get('region_cd')) for r in rows[:3]]}")
            cache[prefix] = hit
            time.sleep(0.2)
        if hit:
            umd = tokens[n] if len(tokens) > n and re.search(r"(읍|면|동|가|리)$", tokens[n]) else ""
            return {**hit, "umd": umd}
    return None


# ---------- 2) 실거래 받기 ----------
def fetch_trades(lawd: str, ym: str) -> list[dict] | None:
    global _seen_fields
    out: list[dict] = []
    page = 1
    while True:
        res = _get(TRADE_API, {"LAWD_CD": lawd, "DEAL_YMD": ym, "pageNo": page, "numOfRows": 1000})
        if res.status_code != 200:
            print(f"::warning::실거래가 API HTTP {res.status_code} ({lawd} {ym}): {res.text[:200]}")
            return None
        try:
            root = ET.fromstring(res.content)
        except ET.ParseError:
            print(f"::warning::실거래가 API 응답 해석 실패 ({lawd} {ym}): {res.text[:200]}")
            return None
        code = (root.findtext(".//resultCode") or "").strip()
        if code not in ("", "00", "000"):
            print(f"::warning::실거래가 API {code} {root.findtext('.//resultMsg')} ({lawd} {ym})")
            return None
        items = root.findall(".//item")
        if items and not _seen_fields:
            _seen_fields = True
            print(f"::notice::실거래가 필드: {','.join(c.tag for c in items[0])}")
        for it in items:
            g = {c.tag: (c.text or "").strip() for c in it}
            price, area = _num(g.get("dealAmount")), _num(g.get("excluUseAr"))
            if not price or not area:
                continue
            out.append({"apt": g.get("aptNm", ""), "umd": g.get("umdNm", ""), "area": area, "price": int(price),
                        "floor": g.get("floor", ""), "built": int(_num(g.get("buildYear")) or 0),
                        "date": f"{g.get('dealYear')}-{int(_num(g.get('dealMonth')) or 0):02d}-"
                                f"{int(_num(g.get('dealDay')) or 0):02d}",
                        "cancel": bool(g.get("cdealType"))})
        total = int(_num(root.findtext(".//totalCount")) or 0)
        if page * 1000 >= total or not items:
            return out
        page += 1
        time.sleep(0.2)


def months_back(today: date, n: int) -> list[str]:
    y, m, out = today.year, today.month, []
    for _ in range(n):
        out.append(f"{y}{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out


# ---------- 3) 요약 ----------
def _median(xs: list[int]) -> int | None:
    return int(statistics.median(xs)) if xs else None


def summarize(lawd: str, name: str, trades: list[dict], today: date) -> dict:
    t = [x for x in trades if not x["cancel"]]
    is84 = [x for x in t if AREA_84[0] <= x["area"] <= AREA_84[1]]
    new84 = [x for x in is84 if x["built"] and x["built"] >= today.year - NEW_BUILD_YEARS]
    by_umd: dict[str, list[int]] = {}
    for x in is84:
        keys = {x["umd"], x["umd"].split()[0]} if x["umd"] else set()
        for k in keys:  # '오남읍 양지리'는 '오남읍'으로도 묶는다
            by_umd.setdefault(k, []).append(x["price"])
    by_month: dict[str, list[int]] = {}
    count_month: dict[str, int] = {}
    for x in t:
        k = x["date"][:7]
        count_month[k] = count_month.get(k, 0) + 1
        if AREA_84[0] <= x["area"] <= AREA_84[1]:
            by_month.setdefault(k, []).append(x["price"])
    by_apt: dict[str, list[dict]] = {}
    for x in t:
        by_apt.setdefault(f"{x['umd']} {x['apt']}", []).append(x)
    top = sorted(by_apt.items(), key=lambda kv: len(kv[1]), reverse=True)[:10]
    per_pyeong = [round(x["price"] * 3.3058 / x["area"]) for x in is84]
    q = statistics.quantiles([x["price"] for x in is84], n=4) if len(is84) >= 4 else None
    return {
        "lawd": lawd, "name": name, "months": MONTHS, "updated": today.isoformat(),
        "trade_count": len(t), "cancel_count": len(trades) - len(t),
        "n84": len(is84), "median84": _median([x["price"] for x in is84]),
        "p25_84": int(q[0]) if q else None, "p75_84": int(q[2]) if q else None,
        "median84_pyeong_excl": _median(per_pyeong),   # 전용면적 3.3㎡당
        "new_n84": len(new84), "new_median84": _median([x["price"] for x in new84]),
        "new_build_years": NEW_BUILD_YEARS,
        "umd84": {u: {"n": len(v), "median": _median(v)} for u, v in by_umd.items() if len(v) >= 3},
        "monthly": [{"month": k, "count": count_month[k], "n84": len(by_month.get(k, [])),
                     "median84": _median(by_month.get(k, []))} for k in sorted(count_month)],
        "top_apts": [{"name": k, "count": len(v),
                      "median84": _median([x["price"] for x in v if AREA_84[0] <= x["area"] <= AREA_84[1]]),
                      "built": v[0]["built"]} for k, v in top],
    }


def main() -> int:
    if not os.environ.get("DATA_GO_KR_KEY"):
        print("::notice::DATA_GO_KR_KEY가 없어 실거래가를 건너뜁니다.")
        return 0
    today = datetime.now(KST).date()
    MARKET.mkdir(parents=True, exist_ok=True)
    codes_p, unit_p = MARKET / "codes.json", MARKET / "unit_regions.json"
    codes = json.loads(codes_p.read_text("utf-8")) if codes_p.exists() else {}
    unit_regions = json.loads(unit_p.read_text("utf-8")) if unit_p.exists() else {}

    since = (today - timedelta(days=UNIT_DAYS)).isoformat()
    targets: dict[str, str] = {}
    for p in sorted(UNITS.glob("*.json")):
        u = json.loads(p.read_text("utf-8"))
        d = u.get("detail", {})
        nd = str(d.get("RCRIT_PBLANC_DE", ""))
        if nd < since:
            continue
        no = str(d.get("HOUSE_MANAGE_NO"))
        if no not in unit_regions:
            hit = lawd_for_address(d.get("HSSPLY_ADRES", ""), codes)
            if hit:
                unit_regions[no] = hit
        if no in unit_regions:
            targets[unit_regions[no]["lawd"]] = unit_regions[no]["name"]
    codes_p.write_text(json.dumps(codes, ensure_ascii=False, indent=1), "utf-8")
    unit_p.write_text(json.dumps(unit_regions, ensure_ascii=False, indent=1), "utf-8")

    months = months_back(today, MONTHS)
    done = 0
    for lawd, name in targets.items():
        reg_p = MARKET / "regions" / f"{lawd}.json"
        if reg_p.exists() and json.loads(reg_p.read_text("utf-8")).get("updated") == today.isoformat():
            continue
        if done >= MAX_REGIONS_PER_RUN:
            break
        tdir = MARKET / "trades" / lawd
        tdir.mkdir(parents=True, exist_ok=True)
        trades, ok = [], True
        for i, ym in enumerate(months):
            f = tdir / f"{ym}.json"
            if f.exists() and i >= 2:  # 2달 전보다 오래된 달은 바뀌지 않으므로 저장본을 쓴다
                trades += json.loads(f.read_text("utf-8"))
                continue
            try:
                got = fetch_trades(lawd, ym)
            except (requests.Timeout, requests.ConnectionError) as e:
                print(f"::warning::실거래가 응답 지연으로 {name} {ym} 건너뜀: {type(e).__name__}")
                got = None
            if got is None:
                ok = False
                break
            f.write_text(json.dumps(got, ensure_ascii=False), "utf-8")
            trades += got
            time.sleep(0.2)
        if not ok:
            print("::warning::실거래가를 받지 못해 이번 실행은 여기서 멈춥니다 (활용신청·키 반영 여부 확인).")
            break
        reg_p.parent.mkdir(parents=True, exist_ok=True)
        reg_p.write_text(json.dumps(summarize(lawd, name, trades, today), ensure_ascii=False, indent=1), "utf-8")
        done += 1
    # 오래된 달 파일 정리 (12개월 밖)
    keep = set(months)
    for f in (MARKET / "trades").glob("*/*.json") if (MARKET / "trades").exists() else []:
        if f.stem not in keep:
            f.unlink()
    print(f"::notice::실거래가 지역 {done}곳 갱신 (대상 {len(targets)}곳, 단지 연결 {len(unit_regions)}곳)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001  실거래가는 보조 정보라 실패해도 전체를 멈추지 않는다
        print(f"::warning::실거래가 처리 실패 {type(e).__name__}: {str(e)[:300]}")
        sys.exit(0)
