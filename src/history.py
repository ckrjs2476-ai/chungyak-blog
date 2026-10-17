"""우리만의 시간 기록: 4개 블로그 핵심 지표를 날짜별로 쌓고, 4주·12주 변화를 미리 계산한다.

원자료 사이트는 '지금 값'만 보여 준다. 날짜별로 쌓은 값과 그 변화는 이 블로그에만 있는 데이터다
(rules/unique_value.md 1장). 글은 여기서 미리 계산된 변화값만 쓴다(직접 빼기·나누기 금지 규칙 유지).

- data/history/<blog>.json : {"series": {대상: {지표: [[날짜, 값], ...]}}} 값이 바뀐 날만 기록
- data/history/<blog>_changes.json : {대상: {지표: {"4주"|"12주": {from, to, from_date, to_date, diff, pct}}}}
매일 sitecheck 워크플로가 실행한다(추가 비용 없음).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "history"
KST = timezone(timedelta(hours=9))
WINDOWS = {"4주": 28, "12주": 84}


def _load(p: Path):
    return json.loads(p.read_text("utf-8")) if p.exists() else None


def current(blog: str) -> dict[str, dict[str, float]]:
    """{대상 id: {지표: 값}} 지금 데이터 파일에서."""
    out: dict[str, dict[str, float]] = {}
    if blog == "jeonse":
        r = _load(ROOT / "blogs/jeonse/data/ranking.json") or {}
        for x in r.get("regions", []):
            out[x["lawd"]] = {k: x[k] for k in ("ratio84", "jeonse_median84", "sale_median84", "rank") if x.get(k) is not None}
        if r.get("avg_ratio84") is not None:
            out["_all"] = {"avg_ratio84": r["avg_ratio84"]}
        for f in sorted((ROOT / "blogs/jeonse/data/regions").glob("*.json")):
            d = _load(f) or {}
            for umd, u in (d.get("umd") or {}).items():  # 동 단위
                if (u.get("jeonse_n") or 0) >= 10:
                    out[f"{d.get('lawd')}:{umd}"] = {k: u[k] for k in ("ratio", "jeonse_median84") if u.get(k) is not None}
    elif blog == "gwanribi":
        s = _load(ROOT / "blogs/gwanribi/data/summary.json") or {}
        for x in s.get("regions", []):
            out[x["lawd"]] = {k: x[k] for k in ("median_total_m2", "median_common_m2", "rank_median_total_m2") if x.get(k) is not None}
        for f in sorted((ROOT / "blogs/gwanribi/data/regions").glob("*.json")):
            d = _load(f) or {}
            for c in d.get("complexes") or []:  # 단지 단위(월 단위로 바뀜)
                out[c["code"]] = {k: c[k] for k in ("total_m2", "common_m2", "ltsm_m2") if c.get(k) is not None}
    elif blog == "gongmoju":
        s = _load(ROOT / "blogs/gongmoju/data/summary.json") or {}
        out["_all"] = {k: s[k] for k in ("count", "median_total_eok", "median_fee_pct") if s.get(k) is not None}
    elif blog == "cheongyak":
        st = _load(ROOT / "data/stats/latest.json") or {}
        tm = st.get("this_month") or {}
        for reg, v in (tm.get("regions") or {}).items() if isinstance(tm.get("regions"), dict) else []:
            if isinstance(v, dict) and v.get("avg_pyeong"):
                out[reg] = {"avg_pyeong": v["avg_pyeong"]}
        mp = st.get("monthly_region_pyeong") or {}
        if mp:
            last = sorted(mp)[-1]
            for reg, v in mp[last].items():
                out.setdefault(reg, {})[f"avg_pyeong_{last}"] = v.get("avg_pyeong")
    return {k: {m: float(v) for m, v in d.items() if v is not None} for k, d in out.items()}


def record(blog: str, today: date) -> dict:
    p = OUT / f"{blog}.json"
    h = _load(p) or {"series": {}}
    for ent, metrics in current(blog).items():
        for m, v in metrics.items():
            s = h["series"].setdefault(ent, {}).setdefault(m, [])
            if s and s[-1][0] == today.isoformat():
                s[-1][1] = v
            elif not s or s[-1][1] != v:
                s.append([today.isoformat(), v])
    h["updated"] = today.isoformat()
    h.setdefault("started", today.isoformat())
    OUT.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(h, ensure_ascii=False, separators=(",", ":")), "utf-8")
    return h


def _value_on(s: list, d: date):
    """d 이전(포함) 마지막 기록 값."""
    best = None
    for ds, v in s:
        if date.fromisoformat(ds) <= d:
            best = (ds, v)
    return best


def changes(blog: str, h: dict, today: date) -> dict:
    out: dict = {}
    started = date.fromisoformat(h.get("started", today.isoformat()))
    for ent, metrics in h["series"].items():
        for m, s in metrics.items():
            if not s:
                continue
            now = s[-1]
            for name, days in WINDOWS.items():
                ref_day = today - timedelta(days=days)
                if ref_day < started:
                    continue  # 그 기간만큼 쌓이지 않았으면 계산하지 않는다
                old = _value_on(s, ref_day)
                if not old:
                    continue
                diff = round(now[1] - old[1], 2)
                pct = round(diff / old[1] * 100, 1) if old[1] else None
                out.setdefault(ent, {}).setdefault(m, {})[name] = {
                    "from": old[1], "to": now[1], "from_date": old[0], "to_date": now[0],
                    "diff": diff, "abs_diff": abs(diff), "pct": pct, "abs_pct": abs(pct) if pct is not None else None}
    (OUT / f"{blog}_changes.json").write_text(json.dumps(out, ensure_ascii=False, indent=0), "utf-8")
    return out


def main() -> int:
    today = datetime.now(KST).date()
    for b in ("cheongyak", "jeonse", "gongmoju", "gwanribi"):
        h = record(b, today)
        c = changes(b, h, today)
        n = sum(len(v) for v in h["series"].values())
        print(f"{b}: 대상 {len(h['series'])}개, 지표 {n}개, 기록 시작 {h['started']}, 변화 계산된 대상 {len(c)}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
