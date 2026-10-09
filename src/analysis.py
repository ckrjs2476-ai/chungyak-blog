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
           "winner_date": _ymd(d.get("PRZWNER_PRESNATN_DE")),
           "price_cap": str(d.get("PARCPRC_ULS_AT") or "").upper() == "Y",          # 분양가상한제
           "rental": str(d.get("RENT_SECD") or "0") not in ("0", ""),                # 임대(가격 비교 제외)
           "speculative_zone": str(d.get("SPECLT_RDN_EARTH_AT") or "").upper() == "Y",  # 투기과열지구
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


def _peers(a: dict, apt: list[dict], need, start: int = 0) -> tuple[str, list[dict]]:
    """비교 대상: 같은 시·구 + 같은 공급 구분(민영/국민) → 같은 시·도 + 같은 공급 구분 → 같은 시·도 전체.
    공고일 앞뒤 180일 안, 비교값이 있는 단지가 2곳 이상일 때만 쓴다."""
    near = [b for b in apt if b["no"] != a["no"] and _within(a["notice_date"], b["notice_date"], COMPARE_DAYS)
            and b["households"] >= MIN_PEER_HOUSEHOLDS and "취소분" not in str(b["name"]) and need(b)]
    # 시 이름은 앞 두 글자로 비교한다 (화성시 → 화성특례시처럼 이름이 바뀐 경우)
    for scope, pick in ((a["city"], lambda b: b["city"][:2] == a["city"][:2] and b["region"] == a["region"]
                         and b["supply_kind"] == a["supply_kind"]),
                        (a["region"], lambda b: b["region"] == a["region"] and b["supply_kind"] == a["supply_kind"]),
                        (a["region"], lambda b: b["region"] == a["region"]))[start:]:
        peers = [b for b in near if pick(b)]
        if len(peers) >= 2 and scope:
            return scope, peers
    return "", []


def add_region_compare(all_: list[dict]) -> None:
    """비슷한 단지와 평당가·경쟁률·가점 커트라인을 비교한다 (무순위 제외)."""
    apt = [a for a in all_ if a["kind"] == "apt"]
    for a in apt:
        if a.get("pyeong_avg"):
            # region_price: 가장 가까운 비교(같은 시), region_price_wide: 같은 시·도 같은 공급 구분
            for key, start in (() if a.get("rental") else (("region_price", 0), ("region_price_wide", 1))):
                scope, peers = _peers(a, apt, lambda b: b.get("pyeong_avg") and not b.get("rental"), start)
                if not peers or (key == "region_price_wide" and scope == a.get("region_price", {}).get("scope")
                                 and len(peers) == a.get("region_price", {}).get("peer_count")):
                    continue
                ps = [b["pyeong_avg"] for b in peers]
                avg = round(sum(ps) / len(ps))
                ranked = sorted(ps + [a["pyeong_avg"]], reverse=True)
                a[key] = {"scope": scope, "supply_kind": a["supply_kind"], "days": COMPARE_DAYS,
                          "peer_count": len(ps), "peers": [b["name"] for b in peers][:8],
                          "peer_avg_pyeong": avg, "diff": a["pyeong_avg"] - avg,
                          "diff_pct": round((a["pyeong_avg"] - avg) * 100 / avg),
                          "rank": ranked.index(a["pyeong_avg"]) + 1, "of": len(ranked)}
        # 지역 관심도: 이 단지 앞 6개월 동안 같은 지역 단지들의 1순위 평균 경쟁률 (공고 글 우선순위에 쓴다)
        scope, peers = _peers(a, [b for b in apt if b["notice_date"] < a["notice_date"]],
                              lambda b: (b.get("competition") or {}).get("rank1_avg_rate") is not None)
        if peers:
            rs = [b["competition"]["rank1_avg_rate"] for b in peers]
            a["area_competition"] = {"scope": scope, "peer_count": len(rs),
                                     "peer_avg_rate": round(sum(rs) / len(rs), 2),
                                     "peer_max_rate": max(rs)}
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


BRANDS = ("자이", "래미안", "힐스테이트", "푸르지오", "e편한세상", "롯데캐슬", "더샵", "아이파크", "SK뷰",
          "호반써밋", "디에이치", "아크로", "르엘", "포레나", "위브", "푸르지오", "하늘채", "센트럴")


def _days(a: str, b: date) -> int | None:
    try:
        return (b - date.fromisoformat(a)).days
    except ValueError:
        return None


def job_priority(job: dict, a: dict, today: date) -> int | None:
    """검색이 몰리는 시점에 맞춰 글 후보의 점수를 매긴다. None이면 후보에서 뺀다.

    검색은 대체로 (1) 공고 뒤~1순위 접수 전 '분양가·일정', (2) 1순위 다음 날 '경쟁률',
    (3) 당첨 발표 당일 '당첨 가점·커트라인'에 몰린다. 시점이 지난 글은 검색이 크게 줄어든다.
    아래 가산점은 가정이며, 서치콘솔 데이터가 쌓이면(2개월 뒤) 조정한다 (rules/keyword_rules.md).
    """
    if a["households"] < 30 or "취소분" in str(a["name"]):
        return None  # 소규모 재공급은 검색이 거의 없고 글이 얇아진다
    # 규모가 아니라 '청약하려는 사람이 얼마나 찾을까'를 본다 (2026-10-09 사용자 요청)
    region = a["region"]
    base = {"서울": 25, "경기": 15, "인천": 12}.get(
        region, 8 if region in ("부산", "대구", "광주", "대전", "울산", "세종") else 0)
    if a.get("price_cap") and a.get("supply_kind") == "민영":
        base += 20  # 민영 분양가상한제: 시세보다 싸게 나와 신청자가 몰린다 (공공분양은 모두 상한제라 가산 안 함)
    if a.get("speculative_zone"):
        base += 5
    rp = a.get("region_price_wide") or a.get("region_price") or {}
    dp = rp.get("diff_pct")
    if dp is not None:
        base += 12 if dp <= -15 else 6 if dp <= -5 else -6 if dp >= 15 else 0  # 주변보다 싸면 관심이 커진다
    if any(b in str(a["name"]) for b in BRANDS):
        base += 8
    base += min(a["households"] // 200, 5)

    def heat(rate) -> int:
        if rate is None:
            return 0
        return 30 if rate >= 50 else 22 if rate >= 20 else 15 if rate >= 10 else 8 if rate >= 3 else 3 if rate >= 1 else -8
    typ = job["type"]
    if typ == "notice":
        to_rank1 = -(_days(a["rank1_date"], today) or 0) if a["rank1_date"] else None
        if to_rank1 is None or to_rank1 < 0:
            return None  # 1순위 접수가 지난 단지의 공고 글은 쓰지 않는다
        age = _days(a["notice_date"], today) or 0
        area = heat((a.get("area_competition") or {}).get("peer_avg_rate"))  # 그 지역 최근 청약 열기
        # 접수 전이면 모두 쓸 가치가 있으니, 순서는 관심도가 정하고 시점은 작은 보정만 한다
        return base + area + 20 - age + (8 if to_rank1 <= 5 else 0)
    c = a.get("competition") or {}
    hot = heat(c.get("rank1_avg_rate"))
    if typ == "competition":
        d = _days(a["rank1_date"], today)
        if d is None or d > 21:
            return None
        return base + hot + (50 if d <= 2 else 25 if d <= 7 else 0)
    if typ == "score":
        d = _days(a.get("winner_date", ""), today)
        if d is None or d < 0 or d > 21:
            return None
        return base + hot + (50 if d <= 1 else 25 if d <= 7 else 0)
    return base


def rescore_jobs(all_: list[dict], today: date) -> None:
    p = ROOT / "data" / "jobs.json"
    if not p.exists():
        return
    data = json.loads(p.read_text("utf-8"))
    by_no = {a["no"]: a for a in all_}
    pub = ROOT / "data" / "published.json"
    done = {f"{x.get('house_manage_no')}:{x.get('type')}" for x in
            (json.loads(pub.read_text("utf-8")).get("posts", []) if pub.exists() else [])}
    kept = []
    for j in data.get("jobs", []):
        if f"{j['house_manage_no']}:{j['type']}" in done:
            continue
        a = by_no.get(str(j["house_manage_no"]))
        pr = job_priority(j, a, today) if a else None
        if pr is not None:
            kept.append({**j, "priority": pr, "rank1_date": a["rank1_date"], "winner_date": a.get("winner_date")})
    kept.sort(key=lambda j: j["priority"], reverse=True)
    data["jobs"] = kept
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")
    print(f"::notice::글 후보 {len(kept)}건(시점 기준 재정렬). 상위: "
          f"{[str(j['name'])[:12] + '/' + j['type'] for j in kept[:5]]}")


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
    today = datetime.now(KST).date()
    rescore_jobs(all_, today)
    stats = build_stats(all_, today)
    (STATS / "latest.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), "utf-8")
    print(f"::notice::분석 {len(all_)}개 단지, 이번 주 경쟁률 {len(stats['weekly_competition'])}건, "
          f"무순위 {len(stats['weekly_remainder'])}건")


if __name__ == "__main__":
    main()
