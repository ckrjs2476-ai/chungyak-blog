"""새 블로그용 키워드 고르기: 검색은 있지만 크지 않고, 우리 데이터로만 제대로 답할 수 있는 키워드.

원리 (rules/keyword_ladder.md)
- 새 블로그는 검색량이 큰 머리 키워드(예: '아파트 관리비')에서 뉴스·대형 사이트를 이기기 어렵다.
  그래서 단계(stage)에 맞는 검색량 구간부터 쓰고, 공개 글·색인이 쌓이면 구간을 올린다.
- '경쟁력'은 세 가지로 본다.
  1) 데이터 우위: 키워드의 대상(단지·지역·회사)에 대해 우리 데이터 파일에 계산값이 있다 (가장 중요)
  2) 구체성: 대상 + 주제어 조합(예: '잠실파크리오 관리비'). 일반어 하나짜리는 뺀다
  3) 광고 경쟁도(네이버 compIdx: 낮음/중간/높음): 상업성이 약할수록 대형 사이트가 덜 노린다고 보는 약한 대리 지표
- 한계: 검색량은 네이버 기준이다. 구글 검색량·구글 순위 난이도는 무료로 받을 방법이 없다.
  구글 실제 성적은 서치콘솔 노출·순위가 쌓이면 그걸로 다시 맞춘다.
환경변수: NAVER_AD_CUSTOMER_ID, NAVER_AD_API_KEY, NAVER_AD_SECRET
결과: data/keywords/<blog>.json, data/keywords/report.md
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import check as core  # noqa: E402
from search_volume import API, _num, _sign  # noqa: E402

KST = timezone(timedelta(hours=9))
OUT = ROOT / "data" / "keywords"
CONFIG = ROOT / "data" / "keyword_stage.json"
NAMES = {"cheongyak": "청약노트", "jeonse": "전세 온도계", "gongmoju": "공모주 뜯어보기", "gwanribi": "관리비 돋보기"}
TOPIC = {"cheongyak": r"(청약|분양|경쟁률|가점|커트라인|모집공고|줍줍|무순위)",
         "jeonse": r"(전세|전세가|전세가율|깡통|전월세|보증금)",
         "gongmoju": r"(공모주|공모|청약|상장|수요예측|공모가|IPO)",
         "gwanribi": r"(관리비|장기수선|관리사무소|난방비|공용관리)"}
# 단계별 노릴 월간 검색량(네이버 PC+모바일) 구간. 처음엔 작게, 공개 글과 노출이 쌓이면 올린다.
STAGES = {1: (30, 1500), 2: (300, 5000), 3: (1000, 30000)}
FAILS = [0]
COMP = {"낮음": 1.0, "중간": 0.6, "높음": 0.3}


PROMOTE = {2: (30, 42), 3: (80, 90)}  # 단계: (공개 글 수, 첫 글 뒤 지난 날) 둘 다 넘으면 올린다 [가정]


def stage_of(blog: str) -> int:
    """설정 파일의 단계와, 공개 글 수·운영 기간으로 계산한 단계 중 큰 쪽. 올라가면 설정 파일에 기록한다."""
    cfg = json.loads(CONFIG.read_text("utf-8")) if CONFIG.exists() else {}
    cur = int((cfg.get(blog) or {}).get("stage", 1))
    base = ROOT if blog == "cheongyak" else ROOT / "blogs" / blog
    files = sorted((base / "posts" / "published").glob("*.md")) if (base / "posts" / "published").exists() else []
    if files:
        first = date.fromisoformat(files[0].name[:10])
        days = (date.today() - first).days
        for st, (n, d) in sorted(PROMOTE.items()):
            if len(files) >= n and days >= d and st > cur:
                cur = st
                cfg[blog] = {"stage": st, "since": date.today().isoformat()}
                CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), "utf-8")
                print(f"::notice::{NAMES[blog]} 키워드 {st}단계로 올림 (공개 글 {len(files)}편, {days}일)")
    return cur


def call(hints: list[str]) -> list[dict]:
    cid, key, sec = (os.environ.get(k, "") for k in ("NAVER_AD_CUSTOMER_ID", "NAVER_AD_API_KEY", "NAVER_AD_SECRET"))
    if not (cid and key and sec):
        raise SystemExit("::error::네이버 검색광고 API 키가 없습니다")
    hints = [re.sub(r"[^0-9A-Za-z가-힣]", "", h)[:40] for h in hints if h]
    hints = [h for h in dict.fromkeys(hints) if len(h) >= 2][:5]
    if not hints:
        return []
    for wait in (0, 2, 6, 15):
        time.sleep(wait or 0.4)
        ts = str(int(time.time() * 1000))
        h = {"X-Timestamp": ts, "X-API-KEY": key, "X-Customer": str(cid), "X-Signature": _sign(ts, "GET", "/keywordstool", sec)}
        try:
            r = requests.get(API + "/keywordstool", params={"hintKeywords": ",".join(hints), "showDetail": "1"}, headers=h, timeout=30)
        except requests.RequestException:
            continue
        if r.status_code == 200:
            return r.json().get("keywordList", [])
        if r.status_code not in (429, 500, 502, 503):
            FAILS[0] += 1
            print(f"::warning::키워드 도구 HTTP {r.status_code}: {r.text[:400].replace(chr(34), chr(39))}")
            return []
    return []


def written(blog: str) -> set[str]:
    base = ROOT if blog == "cheongyak" else ROOT / "blogs" / blog
    out = set()
    for d in ("published", "pending"):
        for f in (base / "posts" / d).glob("*.md") if (base / "posts" / d).exists() else []:
            m, _ = core.split_post(f.read_text("utf-8"))
            out.add(re.sub(r"\s", "", str(m.get("keyword") or "")))
    return out


# ---- 블로그마다 '우리 데이터가 있는 대상'과 씨앗 키워드 ----

def entities(blog: str) -> list[dict]:
    """[{name, id, seeds:[...]}] 데이터 파일에 계산값이 있는 대상."""
    out = []
    if blog == "gwanribi":
        for f in sorted((ROOT / "blogs/gwanribi/data/regions").glob("*.json")):
            d = json.loads(f.read_text("utf-8"))
            if d.get("empty"):
                continue
            gu = d["name"].split()[-1]
            out.append({"name": gu, "id": "region:" + d["lawd"], "seeds": [f"{gu}관리비", f"{gu}아파트관리비"]})
            for c in d["complexes"]:
                nm = re.sub(r"(아파트|\(.*?\))", "", c["name"]).strip()
                out.append({"name": nm, "id": c["code"], "seeds": [f"{nm}관리비"]})
    elif blog == "jeonse":
        for f in sorted((ROOT / "blogs/jeonse/data/regions").glob("*.json")):
            r = json.loads(f.read_text("utf-8"))
            if r.get("empty") or not r.get("ratio84"):
                continue
            gu = r["name"].split()[-1]
            out.append({"name": gu, "id": r["lawd"], "seeds": [f"{gu}전세가율", f"{gu}전세시세", f"{gu}전세"]})
    elif blog == "gongmoju":
        for f in sorted((ROOT / "blogs/gongmoju/data/ipos").glob("*.json")):
            d = json.loads(f.read_text("utf-8"))
            if d.get("is_spac"):
                continue
            nm = re.sub(r"(주식회사|\(주\)|㈜)", "", d["corp_name"]).strip()
            out.append({"name": nm, "id": d["corp_code"], "seeds": [f"{nm}공모주", f"{nm}공모가", f"{nm}수요예측"]})
    elif blog == "cheongyak":
        jobs = json.loads((ROOT / "data/jobs.json").read_text("utf-8")).get("jobs", []) if (ROOT / "data/jobs.json").exists() else []
        for j in jobs:
            from search_volume import name_variants
            v = name_variants(j["name"])
            nm = v[-1] if v else j["name"]
            out.append({"name": nm, "id": j["house_manage_no"],
                        "seeds": [f"{nm}분양가", f"{nm}경쟁률", f"{nm}당첨가점", f"{nm}청약"]})
    return out


GENERIC = {"gwanribi": ["아파트관리비", "관리비비교", "장기수선충당금", "관리비평균", "공용관리비"],
           "jeonse": ["전세가율", "전세가율높은지역", "깡통전세", "전세시세", "아파트전세가율"],
           "gongmoju": ["공모주일정", "공모주청약", "공모주수요예측", "이번주공모주", "공모주상장일정"],
           "cheongyak": ["청약일정", "아파트청약", "분양일정", "무순위청약", "청약가점"]}


def norm(s: str) -> str:
    return re.sub(r"\s", "", s).upper()


def collect(blog: str) -> list[dict]:
    ents = entities(blog)
    rows: dict[str, dict] = {}
    batches = [GENERIC[blog][i:i + 5] for i in range(0, len(GENERIC[blog]), 5)]
    seeds = [s for e in ents for s in e["seeds"]]
    batches += [seeds[i:i + 5] for i in range(0, len(seeds), 5)]
    ent_names = sorted({norm(e["name"]): e for e in ents}.items(), key=lambda x: -len(x[0]))
    for b in batches[:120]:
        if FAILS[0] >= 3:
            break  # 같은 오류가 이어지면 더 부르지 않는다
        for k in call(b):
            kw = str(k.get("relKeyword", ""))
            nk = norm(kw)
            vol = _num(k.get("monthlyPcQcCnt")) + _num(k.get("monthlyMobileQcCnt"))
            if nk in rows or not re.search(TOPIC[blog], kw):
                continue
            ent = next((e for n, e in ent_names if n and n in nk), None)
            rows[nk] = {"keyword": kw, "volume": vol, "comp": k.get("compIdx", ""),
                        "entity": ent["name"] if ent else "", "entity_id": ent["id"] if ent else ""}
    return list(rows.values())


def score(r: dict, lo: int, hi: int) -> float:
    v = r["volume"]
    if v < lo * 0.5:
        band = 0.2
    elif v < lo:
        band = 0.6
    elif v <= hi:
        band = 1.0
    elif v <= hi * 3:
        band = 0.4  # 다음 단계에서 노릴 키워드
    else:
        band = 0.05  # 머리 키워드: 지금은 제목 키워드로 쓰지 않음
    data = 1.0 if r["entity_id"] else 0.25
    return round(100 * band * data * COMP.get(r["comp"], 0.6), 1)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    blogs = [sys.argv[sys.argv.index("--blog") + 1]] if "--blog" in sys.argv else list(NAMES)
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    rep = [f"# 블로그별 키워드 사다리 ({now} KST)", "",
           "검색량은 네이버 월간(PC+모바일). 경쟁도는 네이버 광고 경쟁도(검색 순위 난이도가 아님). '데이터'는 우리 계산값이 있는 대상.", ""]
    for b in blogs:
        st = stage_of(b)
        lo, hi = STAGES[st]
        rows = collect(b)
        done = written(b)
        for r in rows:
            r["score"] = score(r, lo, hi)
            r["used"] = norm(r["keyword"]) in {norm(x) for x in done}
        rows.sort(key=lambda r: -r["score"])
        pick = [r for r in rows if r["score"] >= 60 and not r["used"]]
        nxt = [r for r in rows if hi < r["volume"] <= hi * 3 and r["entity_id"]]
        head = [r for r in rows if r["volume"] > hi * 3][:8]
        (OUT / f"{b}.json").write_text(json.dumps({"updated": now, "stage": st, "band": [lo, hi], "keywords": rows},
                                                  ensure_ascii=False, indent=1), "utf-8")
        rep += [f"## {NAMES[b]} — {st}단계, 노릴 구간 월 {lo:,}~{hi:,}회", "",
                f"- 모은 키워드 {len(rows)}개, 지금 쓸 키워드 {len(pick)}개", "",
                "| 키워드 | 월 검색 | 광고 경쟁 | 우리 데이터 |", "| --- | --- | --- | --- |"]
        rep += [f"| {r['keyword']} | {r['volume']:,} | {r['comp']} | {r['entity'] or '-'} |" for r in pick[:25]]
        if nxt:
            rep += ["", "다음 단계에서 노릴 키워드: " + ", ".join(f"{r['keyword']}({r['volume']:,})" for r in nxt[:10])]
        if head:
            rep += ["", "지금은 제목 키워드로 쓰지 않을 머리 키워드: " + ", ".join(f"{r['keyword']}({r['volume']:,})" for r in head)]
        rep.append("")
        print(f"{NAMES[b]}: {len(rows)}개 중 {len(pick)}개 선정")
    (OUT / "report.md").write_text("\n".join(rep), "utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
