"""전세 온도계 블로그 설정: 라벨, 요약 카드, 검수 규칙.
publish.py가 BLOG_KEY=jeonse일 때 이 파일을 불러 쓴다."""
from __future__ import annotations

import json
import re
import sys
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
import check as core  # noqa: E402  (청약노트 검수의 공통 함수)

split_post = core.split_post
UNIT_KEY = "lawd"
DATA = HERE / "data"
DONE = HERE / "posts" / "published"
PUBLISHED = DATA / "published.json"

REGION_LABELS = ["서울", "경기", "인천", "지방"]
TYPE_LABELS = ["지역 전세가율", "전세가율 순위"]
ALLOWED_LABELS = set(REGION_LABELS + TYPE_LABELS)
TYPES = ("region", "ranking")
ANGLES = {"region": ("전세가율", "흐름", "동네차이", "단지분포", "월세비중"),
          "ranking": ("상위", "변화", "수도권", "지방")}
# 청약노트와 다른 출처 문구(블로그마다 틀을 다르게). 뜻이 같으면 표현은 바꿔도 된다.
DISCLOSURE_RE = re.compile(r"(국토교통부|국토부)[^.\n]{0,25}(전월세|실거래)[^.\n]{0,30}(계산|산출|집계)했습니다")
SOURCE_LINK = "rt.molit.go.kr"
MIN_CHARS = 1500
MIN_ANALYSIS = 3
TITLE_WITHIN = 25

# 요약 카드: 남색 계열(청약노트는 회색 카드)
BOX = "margin:0 0 28px;padding:18px 18px 12px;border-radius:12px;background:#eef2ff;border:1px solid #c7d2fe;"
TITLE = "margin:0 0 4px;font-size:17px;font-weight:700;color:#1e3a8a;"
SUB = "margin:0 0 12px;font-size:13px;color:#3730a3;"
ROW_L = "padding:7px 0;color:#334155;font-size:14px;width:46%;border-bottom:1px solid #dbe3ff;"
ROW_R = "padding:7px 0;color:#0f172a;font-size:15px;font-weight:700;border-bottom:1px solid #dbe3ff;"
NOTE = "margin:10px 0 0;font-size:12px;color:#475569;"


def _eok(manwon) -> str:
    if not manwon:
        return "-"
    e, r = divmod(int(manwon), 10000)
    return (f"{e}억 {r:,}만 원" if r else f"{e}억 원") if e else f"{r:,}만 원"


def region(lawd: str) -> dict | None:
    p = DATA / "regions" / f"{lawd}.json"
    return json.loads(p.read_text("utf-8")) if p.exists() else None


def build_card(meta: dict) -> str:
    if meta.get("type") != "region":
        return ""
    r = region(str(meta.get("lawd") or ""))
    if not r or r.get("empty"):
        return ""
    rows = [("84㎡ 전세 중앙값", _eok(r.get("jeonse_median84"))),
            ("84㎡ 매매 중앙값", _eok(r.get("sale_median84"))),
            ("전세가율", f"{r['ratio84']}%" if r.get("ratio84") else "-"),
            ("전국 순위", f"{r['rank']}위 / {r['rank_of']}곳" if r.get("rank") else "-"),
            ("최근 3개월 전세 변화", f"{r['jeonse_change_pct']:+}%" if r.get("jeonse_change_pct") is not None else "-")]
    trs = "".join(f'<tr><td style="{ROW_L}">{escape(k)}</td><td style="{ROW_R}">{escape(v)}</td></tr>' for k, v in rows)
    return (f'<div style="{BOX}"><p style="{TITLE}">{escape(r["name"])} 전세 온도</p>'
            f'<p style="{SUB}">최근 12개월 아파트 실거래 · {escape(r["updated"])} 계산</p>'
            f'<table style="border-collapse:collapse;border:0;width:100%;">{trs}</table>'
            f'<p style="{NOTE}">출처: 국토교통부 실거래가 공개 자료</p></div>')


def recent_posts() -> list[dict]:
    return json.loads(PUBLISHED.read_text("utf-8")).get("posts", []) if PUBLISHED.exists() else []


def _allowed(meta: dict) -> set[str]:
    out: set[str] = {"84", "3", "12"}
    lawds = [str(meta.get("lawd") or "")] + [str(x) for x in meta.get("lawds") or []]
    for l in lawds:
        r = region(l)
        if r:
            core._walk_nums(r, out)
    rk = DATA / "ranking.json"
    if rk.exists():
        core._walk_nums(json.loads(rk.read_text("utf-8")), out)
    return out


def template_sentences(body: str, exclude_file: str = "") -> list[str]:
    if not DONE.exists():
        return []
    seen: set[str] = set()
    for f in sorted(DONE.glob("*.md"))[-40:]:
        if f.name == exclude_file:
            continue
        _, b = split_post(f.read_text("utf-8"))
        seen |= {core._norm(x) for x in core._sentences(b)}
    return [x for x in core._sentences(body)
            if not re.search(r"(계산했습니다|산출했습니다|집계했습니다|확인해 주세요)", x) and core._norm(x) in seen]


def check_text(meta: dict, body: str, recent: list[dict] | None = None) -> list[str]:
    errs: list[str] = []
    for f in ("type", "title", "slug", "description", "labels", "keyword", "opening", "angle"):
        if not meta.get(f):
            errs.append(f"머리말에 {f}가 없습니다.")
    typ = meta.get("type")
    if typ not in TYPES:
        errs.append(f"알 수 없는 type: {typ}")
    if typ == "region" and not region(str(meta.get("lawd") or "")):
        errs.append("지역 글인데 lawd(시군구 코드) 데이터가 없습니다.")
    if typ in ANGLES and meta.get("angle") not in ANGLES[typ]:
        errs.append(f"angle은 {', '.join(ANGLES[typ])} 중 하나입니다.")
    same = [r for r in (recent or []) if r.get("type") == typ][-2:]
    if len(same) == 2 and all(r.get("angle") == meta.get("angle") for r in same):
        errs.append("같은 종류 직전 2편과 글의 중심(angle)이 같습니다.")
    if recent and recent[-1].get("opening") == meta.get("opening"):
        errs.append("직전 글과 시작 방식(opening)이 같습니다.")
    title, kw = str(meta.get("title", "")), str(meta.get("keyword", ""))
    if kw and kw.split()[0] not in title[:TITLE_WITHIN]:
        errs.append(f"제목 앞 {TITLE_WITHIN}자 안에 키워드 첫 단어('{kw.split()[0]}')가 없습니다.")
    if len(title) > 60:
        errs.append("제목이 60자를 넘습니다.")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", str(meta.get("slug", ""))):
        errs.append("slug는 영문 소문자·숫자·하이픈만 씁니다.")
    labels = set(meta.get("labels") or [])
    if labels - ALLOWED_LABELS:
        errs.append(f"허용되지 않은 라벨: {sorted(labels - ALLOWED_LABELS)}")
    if not 2 <= len(labels) <= 3:
        errs.append("라벨은 2~3개입니다.")
    if not 50 <= len(str(meta.get("description", ""))) <= 160:
        errs.append("검색 설명은 50~160자입니다.")
    plain = core.strip_md(body)
    chars = len(re.sub(r"[\s|#>*\-:]", "", plain))
    if chars < MIN_CHARS:
        errs.append(f"본문이 {chars}자로 짧습니다 ({MIN_CHARS}자 이상).")
    if SOURCE_LINK not in body:
        errs.append("국토교통부 실거래가 공개시스템 링크(rt.molit.go.kr)가 없습니다.")
    if not DISCLOSURE_RE.search(body):
        errs.append("출처 문구('국토교통부 … 실거래 … 계산했습니다')가 없습니다.")
    for b in core.BANNED + ("깡통전세 확정", "안전합니다", "위험합니다", "사지 마세요", "들어가지 마세요"):
        if b in body:
            errs.append(f"금지 표현: '{b}'")
    errs += core.style_errors(body, min_tables=2)
    tmpl = template_sentences(body, meta.get("_file", ""))
    if len(tmpl) > 1:
        errs.append(f"다른 글과 숫자만 다른 같은 문장이 {len(tmpl)}개입니다: " + " / ".join(t[:30] for t in tmpl[:3]))
    allowed = _allowed(meta)
    used = set()
    for tok, unit in re.findall(r"(\d[\d,]*(?:\.\d+)?)\s*(억|만|천|%|%p|건|곳|위|개|㎡)?", plain):
        t = tok.replace(",", "")
        try:
            v = float(t)
        except ValueError:
            continue
        forms = {t, str(int(v))}
        if not unit and (v <= 12 or 2020 <= v <= 2035):
            continue
        if forms & allowed:
            if unit in ("%", "위", "곳") or v > 100:
                used |= forms
        else:
            errs.append(f"데이터에 없는 숫자: {tok}{unit or ''}")
    if len(used) < MIN_ANALYSIS:
        errs.append(f"계산 숫자(전세가율·순위·변화율 등)가 {len(used)}개입니다 ({MIN_ANALYSIS}개 이상).")
    return list(dict.fromkeys(errs))
