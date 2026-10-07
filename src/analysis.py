"""data/units/의 원본 데이터로 '청약홈에 없는 분석 숫자'를 계산한다.

- data/analysis/<HOUSE_MANAGE_NO>.json : 단지별 분석 (평당가, 지역 비교, 경쟁률 해석, 가점 비교)
- data/stats/latest.json             : 여러 단지를 모은 통계 (주간 경쟁률 순위, 주간 무순위, 월별·지역별 평당가 등)

글에 쓰는 분석 숫자는 반드시 이 파일들에서 가져온다. check.py가 이 값으로 대조한다.
계산 기준을 바꾸면 rules/writing_rules.md의 '분석 숫자' 설명도 같이 고친다.

경쟁률 데이터 읽는 법 (2026-10-07 실제 응답으로 확인):
  한 주택형의 행은 1순위 해당지역 → 1순위 기타지역 → 2순위 해당지역 → 2순위 기타지역 순서로 이어진다.
  CMPET_RATE가 숫자면 그 단계에서 마감(경쟁률), "(△N)"이면 그 단계까지 N세대가 남음, "-"면 앞 단계에서 이미 마감.
  SUPLY_HSHLDCO는 특별공급 미달분이 넘어온 뒤의 일반공급 세대수다.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from card import house_ty  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
UNITS = ROOT / "data" / "units"
OUT = ROOT / "data" / "analysis"
STATS = ROOT / "data" / "stats"
KST = timezone(timedelta(hours=9))
PYEONG = 3.3058
COMPARE_DAYS = 180
MIN_PEER_HOUSEHOLDS = 30  # 조합원 취소분 같은 소규모 재공급은 비교 대상에서 뺀다
SPECIAL_KINDS = {"NWWDS_HSHLDCO": "신혼부부", "LFE_FRST_HSHLDCO": "생애최초", "NWBB_HSHLDCO": "신생아",
                 "MNYCH_HSHLDCO": "다자녀", "OLD_PARNTS_SUPORT_HSHLDCO": "노부모 부양",
                 "INSTT_RECOMEND_HSHLDCO": "기관추천", "YGMN_HSHLDCO": "청년"}


def _num(v) -> float | None:
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _ymd(v) -> str:
    s = str(v or "").strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s


def region_of(d: dict) -> str:
    return str(d.get("SUBSCRPT_AREA_CODE_NM") or "").strip() or str(d.get("HSSPLY_ADRES", ""))[:2]


def label_region(region: str) -> str:
    return region if region in ("서울", "경기", "인천") else "지방"


def type_rows(unit: dict) -> list[dict]:
    rows = []
    for m in unit.get("models", []):
        price, area = _num(m.get("LTTOT_TOP_AMOUNT")), _num(m.get("SUPLY_AR"))
        general, special = int(_num(m.get("SUPLY_HSHLDCO")) or 0), int(_num(m.get("SPSPLY_HSHLDCO")) or 0)
        row = {"ty": house_ty(m.get("HOUSE_TY")), "size": int(_num(str(m.get("HOUSE_TY"))[:3]) or 0),
               "price": int(price) if price else None, "area_m2": area, "general": general, "special": special}
        if price and area:
            row["pyeong_price"] = round(price * PYEONG / area)
        if general + special:
            row["special_share_pct"] = round(special * 100 / (general + special))
        rows.append(row)
    return rows


def competition(unit: dict) -> dict:
    by_ty: dict[str, list[dict]] = defaultdict(list)
    for r in unit.get("competition", []):
        by_ty[house_ty(r.get("HOUSE_TY"))].append(r)
    if not by_ty:
        return {}
    types, best, req_all, rank1_req, supply_all, shortfall = [], None, 0, 0, 0, 0
    for ty, rows in by_ty.items():
        supply = int(_num(rows[0].get("SUPLY_HSHLDCO")) or 0)
        supply_all += supply
        closed_at, rate = None, None
        for r in rows:
            req = int(_num(r.get("REQ_CNT")) or 0)
            req_all += req
            if str(r.get("SUBSCRPT_RANK_CODE")) == "1":
                rank1_req += req
            val = _num(r.get("CMPET_RATE"))
            if val is not None and closed_at is None:
                closed_at = f"{r.get('SUBSCRPT_RANK_CODE')}순위 {r.get('RESIDE_SENM')}"
                rate = val
                if best is None or val > best["rate"]:
                    best = {"ty": ty, "rate": val, "stage": closed_at}
        last = str(rows[-1].get("CMPET_RATE", ""))
        m = re.search(r"△\s*(\d+)", last)
        left = int(m.group(1)) if m else 0
        shortfall += left
        types.append({"ty": ty, "supply": supply, "closed_at": closed_at, "rate": rate, "final_shortfall": left})
    out = {"types": types, "req_total": req_all, "rank1_req": rank1_req, "supply_total": supply_all,
           "final_shortfall_total": shortfall,
           "closed_types": sum(1 for t in types if t["closed_at"]),
           "rank1_closed_types": sum(1 for t in types if (t["closed_at"] or "").startswith("1순위")),
           "type_count": len(types)}
    if supply_all:
        out["rank1_avg_rate"] = round(rank1_req / supply_all, 2)
    if best:
        out["best"] = best
    return out


def score(unit: dict) -> dict:
    lows, tops, by_ty = [], [], {}
    for s in unit.get("score", []):
        lo, hi = _num(s.get("LWET_SCORE")), _num(s.get("TOP_SCORE"))
        ty = house_ty(s.get("HOUSE_TY"))
        if lo is not None:
            lows.append((lo, ty, s.get("RESIDE_SENM")))
            by_ty.setdefault(ty, []).append(int(lo))
        if hi is not None:
            tops.append((hi, ty))
    if not lows:
        return {}
    lo = min(lows)
    hi = max(tops) if tops else None
    out = {"min": {"score": int(lo[0]), "ty": lo[1], "reside": lo[2]},
           "type_min": {ty: min(v) for ty, v in by_ty.items()},
           "avg_min": round(sum(x[0] for x in lows) / len(lows), 1)}
    if hi:
        out["max"] = {"score": int(hi[0]), "ty": hi[1]}
    return out


def weighted_pyeong(types: list[dict]) -> int | None:
    pairs = [(t["pyeong_price"], t["general"] + t["special"]) for t in types if t.get("pyeong_price")]
    total = sum(h for _, h in pairs)
    if not pairs:
        return None
    if not total:
        return round(sum(p for p, _ in pairs) / len(pairs))
    return round(sum(p * h for p, h in pairs) / total)


def analyze_unit(unit: dict) -> dict:
    d = unit.get("detail", {})
    types = type_rows(unit)
    gen, spc = sum(t["general"] for t in types), sum(t["special"] for t in types)
    out = {"no": str(d.get("HOUSE_MANAGE_NO")), "name": d.get("HOUSE_NM"), "kind": unit.get("kind"),
           "region": region_of(d), "notice_date": _ymd(d.get("RCRIT_PBLANC_DE")),
           "rank1_date": _ymd(d.get("GNRL_RNK1_CRSPAREA_RCPTDE") or d.get("SUBSCRPT_RCEPT_BGNDE")),
           "city": (str(d.get("HSSPLY_ADRES", "")).split() + ["", ""])[1],
           "supply_kind": str(d.get("HOUSE_DTL_SECD_NM") or ""),
           "url": d.get("PBLANC_URL"), "households": int(_num(d.get("TOT_SUPLY_HSHLDCO")) or 0),
           "types": types, "general_total": gen, "special_total": spc}
    if gen + spc:
        out["special_share_pct"] = round(spc * 100 / (gen + spc))
    pp = [t["pyeong_price"] for t in types if t.get("pyeong_price")]
    if pp:
        out["pyeong_min"], out["pyeong_max"], out["pyeong_avg"] = min(pp), max(pp), weighted_pyeong(types)
    p84 = [t["price"] for t in types if t["price"] and 84 <= t["size"] <= 85]
    if p84:
        out["price_84_min"], out["price_84_max"] = min(p84), max(p84)
    kinds = {}
    for key, label in SPECIAL_KINDS.items():
        n = sum(int(_num(m.get(key)) or 0) for m in unit.get("models", []))
        if n:
            kinds[label] = n
    if kinds:
        out["special_kinds"] = kinds
    c = competition(unit)
    if c:
        out["competition"] = c
    s = score(unit)
    if s:
        out["score"] = s
    return out


def _within(a: str, b: str, days: int) -> bool:
    try:
        return abs((date.fromisoformat(a) - date.fromisoformat(b)).days) <= days
    except ValueError:
        return False


def _peers(a: dict, apt: list[dict], need) -> tuple[str, list[dict]]:
    """비교 대상: 같은 시·구 + 같은 공급 구분(민영/국민) → 같은 시·도 + 같은 공급 구분 → 같은 시·도 전체.
    공고일 앞뒤 180일 안, 비교값이 있는 단지가 2곳 이상일 때만 쓴다."""
    near = [b for b in apt if b["no"] != a["no"] and _within(a["notice_date"], b["notice_date"], COMPARE_DAYS)
            and b["households"] >= MIN_PEER_HOUSEHOLDS and "취소분" not in str(b["name"]) and need(b)]
    for scope, pick in ((a["city"], lambda b: b["city"] == a["city"] and b["region"] == a["region"]
                         and b["supply_kind"] == a["supply_kind"]),
                        (a["region"], lambda b: b["region"] == a["region"] and b["supply_kind"] == a["supply_kind"]),
                        (a["region"], lambda b: b["region"] == a["region"])):
        peers = [b for b in near if pick(b)]
        if len(peers) >= 2 and scope:
            return scope, peers
    return "", []


def add_region_compare(all_: list[dict]) -> None:
    """비슷한 단지와 평당가·경쟁률·가점 커트라인을 비교한다 (무순위 제외)."""
    apt = [a for a in all_ if a["kind"] == "apt"]
    for a in apt:
        if a.get("pyeong_avg"):
            scope, peers = _peers(a, apt, lambda b: b.get("pyeong_avg"))
            if peers:
                ps = [b["pyeong_avg"] for b in peers]
                avg = round(sum(ps) / len(ps))
                ranked = sorted(ps + [a["pyeong_avg"]], reverse=True)
                a["region_price"] = {"scope": scope, "days": COMPARE_DAYS, "peer_count": len(ps),
                                     "peers": [b["name"] for b in peers][:8],
                                     "peer_avg_pyeong": avg, "diff": a["pyeong_avg"] - avg,
                                     "diff_pct": round((a["pyeong_avg"] - avg) * 100 / avg),
                                     "rank": ranked.index(a["pyeong_avg"]) + 1, "of": len(ranked)}
        rate = (a.get("competition") or {}).get("rank1_avg_rate")
        if rate is not None:
            scope, peers = _peers(a, apt, lambda b: (b.get("competition") or {}).get("rank1_avg_rate") is not None)
            if peers:
                rs = [b["competition"]["rank1_avg_rate"] for b in peers]
                ranked = sorted(rs + [rate], reverse=True)
                a["region_competition"] = {"scope": scope, "peer_count": len(rs),
                                           "peers": [b["name"] for b in peers][:8],
                                           "peer_avg_rate": round(sum(rs) / len(rs), 2),
                                           "rank": ranked.index(rate) + 1, "of": len(ranked)}
        cut = (a.get("score") or {}).get("min", {}).get("score")
        if cut is not None:
            scope, peers = _peers(a, apt, lambda b: (b.get("score") or {}).get("min"))
            if peers:
                cs = [b["score"]["min"]["score"] for b in peers]
                avg = round(sum(cs) / len(cs), 1)
                a["region_score"] = {"scope": scope, "peer_count": len(cs),
                                     "peers": [b["name"] for b in peers][:8],
                                     "peer_avg_min": avg, "diff": round(cut - avg, 1)}


def build_stats(all_: list[dict], today: date) -> dict:
    t = today.isoformat()
    week_ago = (today - timedelta(days=7)).isoformat()
    apt = [a for a in all_ if a["kind"] == "apt"]

    week = sorted([a for a in apt if a.get("competition") and week_ago <= a["rank1_date"] < t],
                  key=lambda a: a["competition"].get("rank1_avg_rate", 0), reverse=True)
    weekly_competition = [{"no": a["no"], "name": a["name"], "region": a["region"],
                           "rank1_avg_rate": a["competition"].get("rank1_avg_rate"),
                           "best": a["competition"].get("best"),
                           "final_shortfall_total": a["competition"]["final_shortfall_total"],
                           "rank1_closed_types": a["competition"]["rank1_closed_types"],
                           "type_count": a["competition"]["type_count"]} for a in week]

    soon = (today + timedelta(days=7)).isoformat()
    back = (today - timedelta(days=3)).isoformat()
    remainder = [{"no": a["no"], "name": a["name"], "region": a["region"], "households": a["households"],
                  "rcept_date": a["rank1_date"], "url": a["url"],
                  "types": [{"ty": x["ty"], "price": x["price"], "pyeong_price": x.get("pyeong_price")}
                            for x in a["types"]]}
                 for a in all_ if a["kind"] == "remndr" and back <= a["rank1_date"] <= soon]

    months: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for a in apt:
        if a.get("pyeong_avg") and a["notice_date"]:
            months[a["notice_date"][:7]][a["region"]].append(a["pyeong_avg"])
    monthly_region = {m: {r: {"count": len(v), "avg_pyeong": round(sum(v) / len(v)),
                              "max_pyeong": max(v), "min_pyeong": min(v)} for r, v in rs.items()}
                      for m, rs in sorted(months.items())[-12:]}

    def month_list(ym: str) -> list[dict]:
        xs = [a for a in apt if a["notice_date"].startswith(ym)]
        return sorted([{"no": a["no"], "name": a["name"], "region": a["region"], "households": a["households"],
                        "pyeong_avg": a.get("pyeong_avg"), "price_84_min": a.get("price_84_min"),
                        "special_kinds": a.get("special_kinds", {})} for a in xs],
                      key=lambda x: x["pyeong_avg"] or 0, reverse=True)

    this_m = today.strftime("%Y-%m")
    last_m = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    cutoffs = sorted([{"no": a["no"], "name": a["name"], "region": a["region"], "min": a["score"]["min"],
                       "max": a["score"].get("max")} for a in apt
                      if a.get("score") and a["notice_date"] >= (today - timedelta(days=90)).isoformat()],
                     key=lambda x: x["min"]["score"], reverse=True)
    out = {"date": t, "weekly_competition": weekly_competition, "weekly_remainder": remainder,
           "monthly_region_pyeong": monthly_region,
           "this_month": {"month": this_m, "units": month_list(this_m)},
           "last_month": {"month": last_m, "units": month_list(last_m)},
           "score_cutoffs_90d": cutoffs}
    for key in ("this_month", "last_month"):
        totals: dict[str, int] = defaultdict(int)
        for u in out[key]["units"]:
            for k, v in u["special_kinds"].items():
                totals[k] += v
        out[key]["special_totals"] = dict(totals)
        out[key]["households_total"] = sum(u["households"] for u in out[key]["units"])
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STATS.mkdir(parents=True, exist_ok=True)
    all_ = []
    for p in sorted(UNITS.glob("*.json")):
        try:
            all_.append(analyze_unit(json.loads(p.read_text("utf-8"))))
        except Exception as e:  # noqa: BLE001  한 단지 오류로 전체를 멈추지 않는다
            print(f"::warning::{p.name} 분석 실패: {e}")
    add_region_compare(all_)
    for a in all_:
        (OUT / f"{a['no']}.json").write_text(json.dumps(a, ensure_ascii=False, indent=1), "utf-8")
    stats = build_stats(all_, datetime.now(KST).date())
    (STATS / "latest.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), "utf-8")
    print(f"::notice::분석 {len(all_)}개 단지, 이번 주 경쟁률 {len(stats['weekly_competition'])}건, "
          f"무순위 {len(stats['weekly_remainder'])}건")


if __name__ == "__main__":
    main()
