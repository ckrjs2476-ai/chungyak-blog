"""관리비 돋보기 데이터: 시군구 안의 아파트 단지 관리비를 같은 달 기준으로 모아 비교한다.

- 공동주택 단지 목록(AptListService4), 기본정보(AptBasisInfoServiceV5)
- 공용관리비 17개 항목(AptCmnuseManageCostServiceV3), 개별사용료 10개 항목(AptIndvdlzManageCostServiceV3)
- 장기수선충당금 월부과액·적립요율·잔액·월사용액(AptRepairsCostServiceV3)
- 금액은 단지 전체의 한 달 치(원). 관리비부과면적(kaptMarea)으로 나눠 ㎡당, 세대 수로 나눠 세대 평균을 낸다.
- 결과: blogs/gwanribi/data/regions/<시군구코드>.json, blogs/gwanribi/data/summary.json
- 호출량 때문에 한 번 실행에 시군구 MAX_PER_RUN곳, 세대 수 MIN_HH 이상 단지만.
환경변수: DATA_GO_KR_KEY
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = HERE / "data"
REG = BASE / "regions"
REGION_LIST = ROOT / "blogs" / "jeonse" / "data" / "region_list.json"
API = "https://apis.data.go.kr/1613000/"
KEY = os.environ.get("DATA_GO_KR_KEY", "")
MAX_PER_RUN = int(os.environ.get("GWANRIBI_MAX_PER_RUN", "1"))
MIN_HH = 300
MAX_COMPLEX = 150
REFRESH_DAYS = 60
WORKERS = 6

C, I, R = "AptCmnuseManageCostServiceV3/", "AptIndvdlzManageCostServiceV3/", "AptRepairsCostServiceV3/"
# 공용관리비: (항목 이름, 오퍼레이션, 응답 필드들)
COMMON = [
    ("인건비", "getHsmpLaborCostInfoV3", ["pay", "sundryCost", "bonus", "pension", "accidentPremium", "employPremium",
                                        "nationalPension", "healthPremium", "welfareBenefit"]),
    ("제사무비", "getHsmpOfcrkCostInfoV3", ["officeSupply", "bookSupply", "transportCost"]),
    ("제세공과금", "getHsmpTaxdueInfoV3", ["electCost", "telCost", "postageCost", "taxrestCost"]),
    ("피복비", "getHsmpClothingCostInfoV3", ["clothesCost"]),
    ("교육훈련비", "getHsmpEduTraingCostInfoV3", ["eduCost"]),
    ("차량유지비", "getHsmpVhcleMntncCostInfoV3", ["fuelCost", "refairCost", "carInsurance", "carEtc"]),
    ("기타부대비용", "getHsmpEtcCostInfoV3", ["careItemCost", "accountingCost", "hiddenCost"]),
    ("청소비", "getHsmpCleaningCostInfoV3", ["cleanCost"]),
    ("경비비", "getHsmpGuardCostInfoV3", ["guardCost"]),
    ("소독비", "getHsmpDisinfectionCostInfoV3", ["disinfCost"]),
    ("승강기유지비", "getHsmpElevatorMntncCostInfoV3", ["elevCost"]),
    ("홈네트워크유지비", "getHsmpHomeNetworkMntncCostInfoV3", ["hnetwCost"]),
    ("수선비", "getHsmpRepairsCostInfoV3", ["lrefCost1"]),
    ("시설유지비", "getHsmpFacilityMntncCostInfoV3", ["lrefCost2"]),
    ("안전점검비", "getHsmpSafetyCheckUpCostInfoV3", ["lrefCost3"]),
    ("재해예방비", "getHsmpDisasterPreventionCostInfoV3", ["lrefCost4"]),
    ("위탁관리수수료", "getHsmpConsignManageFeeInfoV3", ["manageCost"]),
]
INDIV = [
    ("난방비", "getHsmpHeatCostInfoV3", ["heatC", "heatP"]),
    ("급탕비", "getHsmpHotWaterCostInfoV3", ["waterHotC", "waterHotP"]),
    ("가스사용료", "getHsmpGasRentalFeeInfoV3", ["gasC", "gasP"]),
    ("전기료", "getHsmpElectricityCostInfoV3", ["electC", "electP"]),
    ("수도료", "getHsmpWaterCostInfoV3", ["waterCoolC", "waterCoolP"]),
    ("정화조오물수수료", "getHsmpWaterPurifierTankFeeInfoV3", ["purifi"]),
    ("생활폐기물수수료", "getHsmpDomesticWasteFeeInfoV3", ["scrap"]),
    ("입주자대표회의운영비", "getHsmpMovingInRepresentationMtgInfoV3", ["preMeet"]),
    ("건물보험료", "getHsmpBuildingInsuranceFeeInfoV3", ["buildInsu"]),
    ("선거관리위원회운영비", "getHsmpElectionOrpnsInfoV3", ["electionMng"]),
]
LTSM = [("월부과액", "getHsmpMonthFeeInfoV3", "sLevy"), ("적립요율", "getHsmpAccumulationTariffInfoV3", "sPer"),
        ("잔액", "getHsmpReserveBalanceInfoV3", "sTot"), ("월사용액", "getHsmpMonthRetalFeeInfoV3", "sUse")]
BAD_OPS: set[str] = set()


def _num(v):
    try:
        return float(str(v).replace(",", "")) if v not in (None, "", " ") else None
    except ValueError:
        return None


def call(path: str, params: dict) -> dict | None:
    """응답 body를 돌려준다. 연결 오류는 기다렸다 다시 시도한다."""
    last = None
    for wait in (0, 5, 20, 60):
        time.sleep(wait)
        try:
            r = requests.get(API + path, params={"serviceKey": KEY, "_type": "json", **params}, timeout=40)
        except (requests.Timeout, requests.ConnectionError) as e:
            last = e
            continue
        if r.status_code != 200:
            if path not in BAD_OPS:
                BAD_OPS.add(path)
                print(f"::warning::{path} HTTP {r.status_code}: {r.text[:120]}")
            return None
        try:
            js = r.json()
        except ValueError:
            last = r.text[:120]
            continue
        return (js.get("response") or {}).get("body") or {}
    print(f"::warning::{path} 실패: {last}")
    return None


def complexes(lawd: str) -> list[dict]:
    out, page = [], 1
    while page <= 10:
        b = call("AptListService4/getSigunguAptList4", {"sigunguCode": lawd, "numOfRows": 500, "pageNo": page})
        if not b:
            break
        items = b.get("items") or []
        if isinstance(items, dict):
            items = items.get("item") or []
        if isinstance(items, dict):
            items = [items]
        out += items
        if len(items) < 500:
            break
        page += 1
    return out


def basis(code: str) -> dict | None:
    b = call("AptBasisInfoServiceV5/getAphusBassInfoV5", {"kaptCode": code})
    return (b or {}).get("item") or None


def _item(path: str, code: str, ym: str) -> dict:
    if path in BAD_OPS:
        return {}
    b = call(path, {"kaptCode": code, "searchDate": ym})
    it = (b or {}).get("item") or {}
    return it if isinstance(it, dict) and it.get("kaptCode") else {}


def fees(code: str, ym: str) -> dict | None:
    common, indiv, lt = {}, {}, {}
    for name, op, fields in COMMON:
        it = _item(C + op, code, ym)
        if it:
            common[name] = int(sum(_num(it.get(f)) or 0 for f in fields))
    if not common.get("인건비") and not common.get("청소비"):
        return None  # 이 달 공개 자료가 없는 단지
    for name, op, fields in INDIV:
        it = _item(I + op, code, ym)
        if it:
            indiv[name] = int(sum(_num(it.get(f)) or 0 for f in fields))
    for name, op, field in LTSM:
        it = _item(R + op, code, ym)
        if it and _num(it.get(field)) is not None:
            lt[name] = _num(it.get(field))
    return {"common": common, "indiv": indiv, "ltsm": lt}


def _med(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs)) if xs else None


def _pct(a, b):
    return round((a - b) * 100 / b, 1) if a is not None and b else None


def _ym_candidates(today: date) -> list[str]:
    out = []
    y, m = today.year, today.month
    for back in (2, 3, 4):
        mm, yy = m - back, y
        while mm <= 0:
            mm += 12
            yy -= 1
        out.append(f"{yy}{mm:02d}")
    return out


def size_group(hh: int) -> str:
    return "300~499세대" if hh < 500 else "500~999세대" if hh < 1000 else "1,000세대 이상"


def build_region(lawd: str, name: str, today: date) -> dict:
    rows = []
    lst = complexes(lawd)
    with ThreadPoolExecutor(WORKERS) as ex:
        infos = list(ex.map(lambda it: (it, basis(it["kaptCode"])), [x for x in lst if x.get("kaptCode")]))
    cands = []
    for it, b in infos:
        if not b:
            continue
        hh, area = int(_num(b.get("kaptdaCnt")) or 0), _num(b.get("kaptMarea"))
        if hh >= MIN_HH and area:
            cands.append((it, b, hh, area))
    cands.sort(key=lambda x: -x[2])
    cands = cands[:MAX_COMPLEX]
    if not cands:
        return {"lawd": lawd, "name": name, "empty": True, "updated": today.isoformat(), "n_list": len(lst)}
    ym = None
    for y in _ym_candidates(today):  # 큰 단지 3곳 중 하나라도 자료가 있는 가장 최근 달
        if any(fees(c[0]["kaptCode"], y) for c in cands[:3]):
            ym = y
            break
    if not ym:
        return {"lawd": lawd, "name": name, "empty": True, "updated": today.isoformat(), "n_list": len(lst)}

    def one(c):
        it, b, hh, area = c
        f = fees(it["kaptCode"], ym)
        return (c, f)
    with ThreadPoolExecutor(WORKERS) as ex:
        got = list(ex.map(one, cands))
    for (it, b, hh, area), f in got:
        if not f:
            continue
        ct, idt = sum(f["common"].values()), sum(f["indiv"].values())
        lv = f["ltsm"].get("월부과액")
        bal = f["ltsm"].get("잔액")
        use_date = str(b.get("kaptUsedate") or "")
        r = {
            "code": it["kaptCode"], "name": str(b.get("kaptName") or it.get("kaptName") or "").strip(),
            "umd": it.get("as3") or "", "households": hh, "fee_area_m2": round(area),
            "dong_count": int(_num(b.get("kaptDongCnt")) or 0),
            "heat": b.get("codeHeatNm") or "", "manage": b.get("codeMgrNm") or "", "sale": b.get("codeSaleNm") or "",
            "built_year": int(use_date[:4]) if use_date[:4].isdigit() else None,
            "size_group": size_group(hh),
            "common_won": ct, "indiv_won": idt, "ltsm_levy_won": int(lv) if lv is not None else None,
            "common_items_won": f["common"], "indiv_items_won": f["indiv"],
            "common_m2": round(ct / area), "indiv_m2": round(idt / area),
            "ltsm_m2": round(lv / area) if lv else None,
            "total_m2": round((ct + idt + (lv or 0)) / area),
            "common_hh": round(ct / hh), "indiv_hh": round(idt / hh),
            "ltsm_hh": round(lv / hh) if lv else None, "total_hh": round((ct + idt + (lv or 0)) / hh),
            "common_items_m2": {k: round(v / area) for k, v in f["common"].items()},
            "indiv_items_m2": {k: round(v / area) for k, v in f["indiv"].items()},
            "ltsm_rate_pct": f["ltsm"].get("적립요율"),
            "ltsm_balance_won": int(bal) if bal is not None else None,
            "ltsm_balance_hh": round(bal / hh) if bal else None,
            "ltsm_use_won": int(f["ltsm"]["월사용액"]) if f["ltsm"].get("월사용액") is not None else None,
        }
        if r["built_year"]:
            r["age_years"] = today.year - r["built_year"]
        rows.append(r)
    if not rows:
        return {"lawd": lawd, "name": name, "empty": True, "updated": today.isoformat(), "ym": ym}

    keys = ["common_m2", "indiv_m2", "ltsm_m2", "total_m2", "common_hh", "total_hh"]
    med = {k: _med([r.get(k) for r in rows]) for k in keys}
    item_names = [n for n, _, _ in COMMON] + [n for n, _, _ in INDIV]
    item_med = {}
    for n in item_names:
        vals = [(r["common_items_m2"].get(n) if n in r["common_items_m2"] else r["indiv_items_m2"].get(n)) for r in rows]
        vals = [v for v in vals if v]
        if len(vals) >= 3:
            item_med[n] = _med(vals)
    by_size = {g: {k: _med([r[k] for r in rows if r["size_group"] == g]) for k in ("common_m2", "total_m2")} | {"count": sum(r["size_group"] == g for r in rows)}
               for g in sorted({r["size_group"] for r in rows})}
    by_heat = {h: {k: _med([r[k] for r in rows if r["heat"] == h]) for k in ("indiv_m2", "total_m2")} | {"count": sum(r["heat"] == h for r in rows)}
               for h in sorted({r["heat"] for r in rows}) if h}
    n = len(rows)
    for k in ("common_m2", "indiv_m2", "ltsm_m2", "total_m2"):
        ordered = sorted([r for r in rows if r.get(k) is not None], key=lambda r: -r[k])
        for i, r in enumerate(ordered, 1):
            r[f"rank_{k}"] = i  # 1위 = 가장 비싼 단지
            r[f"rank_{k}_of"] = len(ordered)
            r[f"{k}_vs_median_pct"] = _pct(r[k], med[k])
    for r in rows:
        r["items_vs_median_pct"] = {}
        for nme, v in {**r["common_items_m2"], **r["indiv_items_m2"]}.items():
            if nme in item_med and item_med[nme]:
                r["items_vs_median_pct"][nme] = _pct(v, item_med[nme])
        g, h = by_size.get(r["size_group"], {}), by_heat.get(r["heat"], {})
        r["common_m2_vs_size_median_pct"] = _pct(r["common_m2"], g.get("common_m2")) if g.get("count", 0) >= 3 else None
        r["indiv_m2_vs_heat_median_pct"] = _pct(r["indiv_m2"], h.get("indiv_m2")) if h.get("count", 0) >= 3 else None
        top = sorted(((k, v) for k, v in r["common_items_m2"].items() if v), key=lambda x: -x[1])[:3]
        r["common_top_items"] = [k for k, _ in top]
        r["common_top_share_pct"] = {k: round(r["common_items_won"][k] * 100 / r["common_won"], 1) for k, _ in top} if r["common_won"] else {}
    rows.sort(key=lambda r: r["rank_total_m2"])
    hi, lo = rows[0], rows[-1]
    return {
        "lawd": lawd, "name": name, "ym": ym, "ym_label": f"{ym[:4]}년 {int(ym[4:])}월",
        "updated": today.isoformat(), "n_list": len(lst), "n_complex": n, "min_households": MIN_HH,
        "median": med, "item_median_m2": item_med, "by_size": by_size, "by_heat": by_heat,
        "total_m2_high": {"name": hi["name"], "total_m2": hi["total_m2"]},
        "total_m2_low": {"name": lo["name"], "total_m2": lo["total_m2"]},
        "total_m2_spread": hi["total_m2"] - lo["total_m2"],
        "total_m2_ratio_high_low": round(hi["total_m2"] / lo["total_m2"], 2) if lo["total_m2"] else None,
        "complexes": rows,
    }


def summary() -> None:
    out = []
    for p in sorted(REG.glob("*.json")):
        d = json.loads(p.read_text("utf-8"))
        if d.get("empty"):
            continue
        out.append({"lawd": d["lawd"], "name": d["name"], "ym": d["ym"], "n_complex": d["n_complex"],
                    "median_total_m2": d["median"]["total_m2"], "median_common_m2": d["median"]["common_m2"]})
    ordered = sorted(out, key=lambda x: -(x["median_total_m2"] or 0))
    for i, x in enumerate(ordered, 1):
        x["rank_median_total_m2"] = i
    (BASE / "summary.json").write_text(json.dumps({"updated": date.today().isoformat(), "regions": ordered},
                                                  ensure_ascii=False, indent=1), "utf-8")


def main() -> int:
    if not KEY:
        print("::error::DATA_GO_KR_KEY가 없습니다")
        return 1
    REG.mkdir(parents=True, exist_ok=True)
    regions = json.loads(REGION_LIST.read_text("utf-8"))
    today = date.today()
    only = os.environ.get("GWANRIBI_LAWD")

    def age(r):
        p = REG / f"{r['lawd']}.json"
        if not p.exists():
            return (0, r.get("priority", 99))
        d = json.loads(p.read_text("utf-8"))
        days = (today - date.fromisoformat(d["updated"])).days
        return (1 if days >= REFRESH_DAYS else 9, r.get("priority", 99))
    todo = [r for r in regions if (r["lawd"] == only if only else age(r)[0] < 9)]
    todo.sort(key=age)
    for r in todo[:MAX_PER_RUN]:
        t0 = time.time()
        d = build_region(r["lawd"], r["name"], today)
        (REG / f"{r['lawd']}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), "utf-8")
        print(f"::notice::{r['name']} {'자료 없음' if d.get('empty') else str(d['n_complex']) + '개 단지 ' + d['ym']} ({int(time.time() - t0)}초)")
    summary()
    return 0


if __name__ == "__main__":
    sys.exit(main())
