"""결과로 맞춰 보는 후속 글 후보 (rules/unique_value.md 9장).

이미 올린 글의 대상에 '그 뒤 결과'가 생기면 후보로 적는다. 글쓴이는 이 파일의 숫자만 쓴다(직접 빼기·나누기 금지).
- 전세·관리비·공모주: 글 올린 날의 값(우리 매일 기록 data/history)과 지금 값. 21일 이상 지났고 값이 바뀐 대상만.
- 청약: 한 달 동안 공고한 단지들의 '공고 때 3.3㎡당 분양가'와 '실제 1순위 해당지역 경쟁률·최저 가점'(결과 5곳 이상인 달).
결과: data/followup/<blog>.json {"updated", "candidates": [...]}, 이미 쓴 후보(원고 머리말 followup: <id>)는 빠진다.
검수는 이 파일의 숫자를 허용 숫자로 넣는다(src/check.py history_numbers).
매일 sitecheck 워크플로가 history.py 다음에 실행한다.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "followup"
KST = timezone(timedelta(hours=9))
MIN_DAYS = 21

BLOGS = {
    "jeonse": (ROOT / "blogs/jeonse", {"region": {"ratio84": ("84㎡ 전세가율", "%"), "jeonse_median84": ("84㎡ 전세 중앙값", "만 원"),
                                                  "sale_median84": ("84㎡ 매매 중앙값", "만 원")}}),
    "gwanribi": (ROOT / "blogs/gwanribi", {"complex": {"total_m2": ("㎡당 관리비", "원"), "common_m2": ("㎡당 공용관리비", "원"),
                                                       "ltsm_m2": ("㎡당 장기수선충당금", "원")},
                                           "region": {"median_total_m2": ("㎡당 관리비 중앙값", "원"),
                                                      "rank_median_total_m2": ("시군구 순위(높은 순)", "위")}}),
    "gongmoju": (ROOT / "blogs/gongmoju", {"ipo": {"price": ("공모가", "원"), "total_eok": ("공모 규모", "억 원"),
                                                   "total_rank": ("공모 규모 순위(큰 순)", "위")}}),
}


def _load(p: Path):
    return json.loads(p.read_text("utf-8")) if p.exists() else None


def used_ids() -> set[str]:
    """원고 머리말 followup: <id> 로 이미 쓴(쓰는 중인) 후보."""
    out = set()
    for d in [ROOT / "posts"] + [ROOT / "blogs" / b / "posts" for b in ("jeonse", "gwanribi", "gongmoju", "drone")]:
        for f in d.rglob("*.md"):
            m = re.search(r"^followup:\s*\"?([^\"\n]+)\"?\s*$", f.read_text("utf-8")[:3000], re.M)
            if m:
                out.add(m.group(1).strip())
    return out


def _value_on(s: list, d: date):
    best = None
    for ds, v in s:
        if date.fromisoformat(ds) <= d:
            best = (ds, v)
    return best or (s[0] if s else None)


def post_changes(blog: str, today: date, used: set[str]) -> list[dict]:
    base, types = BLOGS[blog]
    pub = _load(base / "data" / "published.json") or {}
    hist = (_load(ROOT / "data" / "history" / f"{blog}.json") or {}).get("series", {})
    out = []
    for p in pub.get("posts", []):
        if p.get("status") != "LIVE" or p.get("type") not in types:
            continue
        ent = str(p.get("house_manage_no") or "")
        if not ent or ent not in hist:
            continue
        pdate = date.fromisoformat(p["published_at"][:10])
        days = (today - pdate).days
        if days < MIN_DAYS:
            continue
        metrics = {}
        for m, (label, unit) in types[p["type"]].items():
            s = hist[ent].get(m) or []
            if not s:
                continue
            old = _value_on(s, pdate)
            now = s[-1]
            if not old or old[1] == now[1]:
                continue
            diff = round(now[1] - old[1], 2)
            metrics[m] = {"label": label, "unit": unit, "from": old[1], "from_date": old[0], "to": now[1], "to_date": now[0],
                          "diff": diff, "abs_diff": abs(diff),
                          "pct": round(diff / old[1] * 100, 1) if old[1] else None,
                          "baseline_after_post": date.fromisoformat(old[0]) > pdate}
        if not metrics:
            continue
        cid = f"{blog}:{ent}:{p['published_at'][:10]}"
        if cid in used:
            continue
        out.append({"id": cid, "kind": "post_change", "entity": ent, "days_since": days,
                    "post": {k: p.get(k) for k in ("title", "url", "file", "keyword", "type")}
                    | {"published_at": p["published_at"][:10]}, "metrics": metrics})
    out.sort(key=lambda c: -max((v.get("abs_diff") or 0) / (abs(v["from"]) or 1) for v in c["metrics"].values()))
    return out


def _rank1_local(unit: dict) -> dict | None:
    """1순위 해당지역 접수 합계 ÷ 공급 세대 합계(주택형 합산)와 해당지역 최저 가점."""
    rows = [r for r in unit.get("competition") or [] if r.get("SUBSCRPT_RANK_CODE") in (1, "1") and r.get("RESIDE_SECD") == "01"]
    if not rows:
        return None
    req = sum(int(r.get("REQ_CNT") or 0) for r in rows)
    sup = sum(int(r.get("SUPLY_HSHLDCO") or 0) for r in {r["HOUSE_TY"]: r for r in rows}.values())
    lows = [int(float(r["LWET_SCORE"])) for r in unit.get("score") or []
            if r.get("RESIDE_SECD") == "01" and re.fullmatch(r"\d+(\.\d+)?", str(r.get("LWET_SCORE") or "")) and float(r["LWET_SCORE"]) > 0]
    return {"rank1_local_req": req, "supply": sup, "rank1_local_rate": round(req / sup, 2) if sup else None,
            "local_low_score": min(lows) if lows else None}


def cheongyak_months(today: date, used: set[str]) -> list[dict]:
    st = _load(ROOT / "data" / "stats" / "latest.json") or {}
    pubs = {str(p.get("house_manage_no")): p.get("url") for p in (_load(ROOT / "data" / "published.json") or {}).get("posts", [])
            if p.get("status") == "LIVE" and p.get("house_manage_no")}
    out = []
    for key in ("last_month",):  # 결과가 다 나오는 건 지난달 공고분
        mon = st.get(key) or {}
        month = mon.get("month")
        if not month:
            continue
        cid = f"cheongyak:month:{month}"
        if cid in used:
            continue
        reg_avg = (st.get("monthly_region_pyeong") or {}).get(month, {})
        rows = []
        for u in mon.get("units", []):
            unit = _load(ROOT / "data" / "units" / f"{u['no']}.json") or {}
            r = _rank1_local(unit)
            if not r or not u.get("pyeong_avg"):
                continue
            ra = (reg_avg.get(u.get("region")) or {}).get("avg_pyeong")
            rows.append({"no": u["no"], "name": u["name"], "region": u.get("region"), "households": u.get("households"),
                         "pyeong_avg": u["pyeong_avg"], "region_month_avg_pyeong": ra,
                         "vs_region_pct": round((u["pyeong_avg"] - ra) / ra * 100, 1) if ra else None, **r,
                         "our_post": pubs.get(u["no"])})
        if len(rows) < 5:
            continue
        rows.sort(key=lambda x: -(x["rank1_local_rate"] or 0))
        for i, x in enumerate(rows, 1):
            x["rate_rank"] = i
        by_price = sorted(rows, key=lambda x: -x["pyeong_avg"])
        for i, x in enumerate(by_price, 1):
            x["price_rank"] = i
        out.append({"id": cid, "kind": "month_results", "entity": f"month:{month}", "month": month, "count": len(rows),
                    "house_manage_nos": [x["no"] for x in rows], "units": rows,
                    "note": "1순위 해당지역 접수 합계 ÷ 공급 세대 합계(주택형 합산). 공급 세대는 해당지역·기타지역 배분 전 주택형 물량."})
    return out


def main() -> int:
    today = datetime.now(KST).date()
    used = used_ids()
    OUT.mkdir(parents=True, exist_ok=True)
    allc = {"cheongyak": cheongyak_months(today, used)}
    for b in BLOGS:
        allc[b] = post_changes(b, today, used)
    for b, c in allc.items():
        (OUT / f"{b}.json").write_text(json.dumps({"updated": today.isoformat(), "candidates": c}, ensure_ascii=False, indent=1), "utf-8")
        print(f"{b}: 후속 글 후보 {len(c)}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
