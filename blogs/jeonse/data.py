"""전세 온도계 데이터: 시군구별 전세가율(매매 대비 전세가)과 전세 흐름을 계산한다.

- 아파트 전월세 실거래가(RTMSDataSvcAptRent)와 매매 실거래가(RTMSDataSvcAptTradeDev), 최근 12개월
- 결과: blogs/jeonse/data/regions/<LAWD>.json, blogs/jeonse/data/ranking.json
- 한 번에 MAX_PER_RUN개 시군구씩, 오래된 것부터 새로 계산한다(공공데이터 호출량 제한 때문).
환경변수: DATA_GO_KR_KEY
"""
from __future__ import annotations

import json
import statistics
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import market  # noqa: E402
from market import TRADE_API, _num, months_back  # noqa: E402
import requests  # noqa: E402

market._get_orig = market._get


def _get(url: str, params: dict):
    """공공데이터포털이 GitHub에서 가끔 연결을 받지 않는다. 기다리는 시간을 늘려 5번까지 시도한다."""
    last = None
    for wait in (0, 10, 30, 60, 120):
        time.sleep(wait)
        try:
            return market._get_orig(url, params)
        except (requests.Timeout, requests.ConnectionError) as e:
            last = e
            print(f"::warning::연결 재시도 ({type(e).__name__}), {wait}초 대기 후")
    raise last  # type: ignore[misc]


def _code_rows(prefix: str) -> list[dict]:
    market._get = _get  # 시군구 목록도 같은 재시도를 쓴다
    try:
        return market._code_rows(prefix)
    finally:
        market._get = market._get_orig

BASE = Path(__file__).resolve().parent / "data"
REG = BASE / "regions"
RENT_API = "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent"
AREA_84 = (80.0, 86.0)
MAX_PER_RUN = 18
REFRESH_DAYS = 14
SIDO = ["서울특별시", "경기도", "인천광역시", "부산광역시", "대구광역시", "대전광역시", "광주광역시",
        "울산광역시", "세종특별자치시", "충청남도", "충청북도", "경상남도", "경상북도", "전북특별자치도",
        "전라남도", "강원특별자치도", "제주특별자치도"]


def region_list() -> list[dict]:
    f = BASE / "region_list.json"
    if f.exists():
        cached = json.loads(f.read_text("utf-8"))
        if len(cached) >= 220:
            return cached
    out, seen = [], set()
    for i, sido in enumerate(SIDO):
        rows, page = [], 1
        while page <= 15:  # 시도마다 행이 1,000개를 넘으므로 쪽을 넘겨 가며 모두 받는다
            res = _get(market.CODE_API, {"pageNo": page, "numOfRows": 1000, "type": "json", "locatadd_nm": sido})
            try:
                body = res.json()
            except ValueError:
                break
            got: list[dict] = []

            def walk(x):
                if isinstance(x, dict):
                    if isinstance(x.get("row"), list):
                        got.extend(r for r in x["row"] if isinstance(r, dict))
                    for v in x.values():
                        walk(v)
                elif isinstance(x, list):
                    for v in x:
                        walk(v)
            walk(body)
            rows += got
            if len(got) < 1000:
                break
            page += 1
        for r in rows:
            code, nm = str(r.get("region_cd", "")), str(r.get("locatadd_nm", "")).strip()
            if len(code) == 10 and code[5:] == "00000" and code[2:5] != "000" and code[:5] not in seen:
                seen.add(code[:5])
                out.append({"lawd": code[:5], "name": nm, "priority": i})
        time.sleep(0.3)
    old = {r["lawd"]: r for r in (json.loads(f.read_text("utf-8")) if f.exists() else [])}
    for l, r in old.items():  # 이전 목록에만 있던 곳도 유지
        if l not in seen:
            out.append(r)
            seen.add(l)
    # '수원시'(41110)처럼 아래에 구가 있는 시 단위 코드는 실거래가 응답이 없으므로 뺀다
    codes = {r["lawd"] for r in out}
    out = [r for r in out if not (r["lawd"][4] == "0" and any(c != r["lawd"] and c[:4] == r["lawd"][:4] for c in codes))]
    BASE.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(out, ensure_ascii=False, indent=1), "utf-8")
    print(f"::notice::시군구 {len(out)}곳 목록 저장")
    return out


def _items(api: str, lawd: str, ym: str) -> list[dict] | None:
    out, page = [], 1
    while True:
        res = _get(api, {"LAWD_CD": lawd, "DEAL_YMD": ym, "pageNo": page, "numOfRows": 1000})
        if res.status_code != 200:
            print(f"::warning::{api.split('/')[-1]} HTTP {res.status_code} ({lawd} {ym}): {res.text[:150]}")
            return None
        try:
            root = ET.fromstring(res.content)
        except ET.ParseError:
            print(f"::warning::응답 해석 실패 ({lawd} {ym}): {res.text[:150]}")
            return None
        code = (root.findtext(".//resultCode") or "").strip()
        if code not in ("", "00", "000"):
            print(f"::warning::{code} {root.findtext('.//resultMsg')} ({lawd} {ym})")
            return None
        items = root.findall(".//item")
        out += [{c.tag: (c.text or "").strip() for c in it} for it in items]
        total = int(_num(root.findtext(".//totalCount")) or 0)
        if page * 1000 >= total or not items:
            return out
        page += 1
        time.sleep(0.2)


def _date(g: dict) -> str:
    return f"{g.get('dealYear')}-{int(_num(g.get('dealMonth')) or 0):02d}-{int(_num(g.get('dealDay')) or 0):02d}"


def _med(xs: list[float]) -> int | None:
    return int(statistics.median(xs)) if xs else None


def _ratio(j: int | None, t: int | None) -> float | None:
    return round(j * 100 / t, 1) if j and t else None


def summarize(lawd: str, name: str, rents: list[dict], trades: list[dict], today: date) -> dict:
    jeonse, wolse = [], 0
    for g in rents:
        area, dep, mon = _num(g.get("excluUseAr")), _num(g.get("deposit")), _num(g.get("monthlyRent"))
        if not area or not dep:
            continue
        if mon and mon > 0:
            wolse += 1
            continue
        jeonse.append({"apt": g.get("aptNm", ""), "umd": g.get("umdNm", ""), "area": area, "dep": int(dep),
                       "built": int(_num(g.get("buildYear")) or 0), "date": _date(g),
                       "renew": (g.get("contractType") or "") == "갱신"})
    sales = []
    for g in trades:
        area, price = _num(g.get("excluUseAr")), _num(g.get("dealAmount"))
        if area and price and not (g.get("cdealType") or "").strip():
            sales.append({"apt": g.get("aptNm", ""), "umd": g.get("umdNm", ""), "area": area, "price": int(price),
                          "built": int(_num(g.get("buildYear")) or 0), "date": _date(g)})
    is84 = lambda x: AREA_84[0] <= x["area"] <= AREA_84[1]  # noqa: E731
    j84, s84 = [x for x in jeonse if is84(x)], [x for x in sales if is84(x)]
    jm, sm = _med([x["dep"] for x in j84]), _med([x["price"] for x in s84])
    # 최근 3개월 vs 그 전 3개월 전세 중앙값
    cut3 = (today.replace(day=1) - timedelta(days=80)).isoformat()[:7]
    cut6 = (today.replace(day=1) - timedelta(days=170)).isoformat()[:7]
    recent = [x["dep"] for x in j84 if x["date"][:7] >= cut3]
    before = [x["dep"] for x in j84 if cut6 <= x["date"][:7] < cut3]
    rm, bm = _med(recent), _med(before)
    # 읍면동별
    umd = {}
    for u in sorted({x["umd"] for x in j84 + s84 if x["umd"]}):
        jj = [x["dep"] for x in j84 if x["umd"] == u]
        ss = [x["price"] for x in s84 if x["umd"] == u]
        if len(jj) >= 3 and len(ss) >= 3:
            umd[u] = {"jeonse_n": len(jj), "jeonse_median84": _med(jj), "sale_n": len(ss),
                      "sale_median84": _med(ss), "ratio": _ratio(_med(jj), _med(ss))}
    # 단지별(같은 단지 84㎡대에서 전세·매매가 모두 2건 이상)
    apts = []
    for key in sorted({(x["umd"], x["apt"]) for x in j84}):
        jj = [x["dep"] for x in j84 if (x["umd"], x["apt"]) == key]
        ss = [x["price"] for x in s84 if (x["umd"], x["apt"]) == key]
        if len(jj) >= 2 and len(ss) >= 2:
            built = next((x["built"] for x in j84 if (x["umd"], x["apt"]) == key), 0)
            apts.append({"umd": key[0], "apt": key[1], "built": built, "jeonse_n": len(jj),
                         "jeonse_median84": _med(jj), "sale_n": len(ss), "sale_median84": _med(ss),
                         "ratio": _ratio(_med(jj), _med(ss))})
    apts.sort(key=lambda a: a["ratio"] or 0, reverse=True)
    monthly = []
    for ym in sorted({x["date"][:7] for x in jeonse}):
        mm = [x["dep"] for x in j84 if x["date"][:7] == ym]
        monthly.append({"month": ym, "jeonse_count": sum(1 for x in jeonse if x["date"][:7] == ym),
                        "n84": len(mm), "jeonse_median84": _med(mm)})
    total = len(jeonse) + wolse
    return {
        "lawd": lawd, "name": name, "updated": today.isoformat(), "months": 12,
        "jeonse_count": len(jeonse), "wolse_count": wolse,
        "wolse_share_pct": round(wolse * 100 / total, 1) if total else None,
        "renew_share_pct": round(sum(1 for x in jeonse if x["renew"]) * 100 / len(jeonse), 1) if jeonse else None,
        "jeonse_n84": len(j84), "jeonse_median84": jm, "sale_n84": len(s84), "sale_median84": sm,
        "ratio84": _ratio(jm, sm),
        "jeonse_recent3_median84": rm, "jeonse_prev3_median84": bm,
        "jeonse_change_pct": round((rm - bm) * 100 / bm, 1) if rm and bm else None,
        "apts_with_both": len(apts),
        "apts_ratio_80_plus": sum(1 for a in apts if (a["ratio"] or 0) >= 80),
        "apts_ratio_70_plus": sum(1 for a in apts if (a["ratio"] or 0) >= 70),
        "umd": umd, "top_ratio_apts": apts[:10], "low_ratio_apts": apts[-5:][::-1] if len(apts) > 10 else [],
        "monthly": monthly,
    }


def ranking() -> None:
    rows = []
    for f in REG.glob("*.json"):
        d = json.loads(f.read_text("utf-8"))
        if d.get("ratio84") and d.get("jeonse_n84", 0) >= 20 and d.get("sale_n84", 0) >= 20:
            rows.append({"lawd": d["lawd"], "name": d["name"], "ratio84": d["ratio84"],
                         "jeonse_median84": d["jeonse_median84"], "sale_median84": d["sale_median84"],
                         "jeonse_change_pct": d.get("jeonse_change_pct")})
    rows.sort(key=lambda r: r["ratio84"], reverse=True)
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    (BASE / "ranking.json").write_text(json.dumps({"updated": date.today().isoformat(), "count": len(rows),
                                                   "regions": rows}, ensure_ascii=False, indent=1), "utf-8")
    for f in REG.glob("*.json"):  # 각 지역 파일에 전국 순위를 붙인다
        d = json.loads(f.read_text("utf-8"))
        hit = next((r for r in rows if r["lawd"] == d["lawd"]), None)
        d["rank"] = hit["rank"] if hit else None
        d["rank_of"] = len(rows)
        f.write_text(json.dumps(d, ensure_ascii=False, indent=1), "utf-8")


def main() -> int:
    REG.mkdir(parents=True, exist_ok=True)
    today = date.today()
    regions = region_list()
    if not regions:
        print("::error::시군구 목록을 받지 못했습니다.")
        return 0

    def age(r):
        f = REG / f"{r['lawd']}.json"
        if not f.exists():
            return (0, r["priority"])
        upd = json.loads(f.read_text("utf-8")).get("updated", "2000-01-01")
        return (1, upd)
    todo = [r for r in sorted(regions, key=age)
            if not (REG / f"{r['lawd']}.json").exists()
            or (today - date.fromisoformat(json.loads((REG / f"{r['lawd']}.json").read_text("utf-8"))["updated"])).days >= REFRESH_DAYS]
    done = 0
    for r in todo[:MAX_PER_RUN]:
        rents, trades, ok = [], [], True
        for ym in months_back(today, 12):
            try:
                a = _items(RENT_API, r["lawd"], ym)
                b = _items(TRADE_API, r["lawd"], ym)
            except (requests.Timeout, requests.ConnectionError):
                a = b = None
            if a is None or b is None:
                ok = False
                break
            rents += a
            trades += b
        if not ok:
            continue
        if not rents and not trades:
            (REG / f"{r['lawd']}.json").write_text(json.dumps({"lawd": r["lawd"], "name": r["name"], "updated": today.isoformat(), "empty": True}, ensure_ascii=False), "utf-8")
            continue
        s = summarize(r["lawd"], r["name"], rents, trades, today)
        (REG / f"{r['lawd']}.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), "utf-8")
        done += 1
        print(f"::notice::{r['name']}: 전세 {s['jeonse_count']}건, 84㎡ 전세가율 {s['ratio84']}%")
    ranking()
    print(f"::notice::이번에 {done}곳 계산, 남은 곳 {max(0, len(todo) - MAX_PER_RUN)}곳")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        import traceback
        tb = traceback.format_exc().splitlines()
        print(f"::error::{type(e).__name__}: {str(e)[:300]} | {' / '.join(l.strip() for l in tb[-6:])[:600]}")
        ranking() if REG.exists() else None
        raise
