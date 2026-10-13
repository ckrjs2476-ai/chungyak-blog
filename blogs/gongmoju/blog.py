"""공모주 뜯어보기 블로그 설정: 라벨, 요약 카드, 검수 규칙. publish.py가 BLOG_KEY=gongmoju일 때 불러 쓴다."""
from __future__ import annotations

import json
import re
import sys
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
import check as core  # noqa: E402

split_post = core.split_post
UNIT_KEY = "corp_code"
DATA = HERE / "data"
DONE = HERE / "posts" / "published"
PUBLISHED = DATA / "published.json"

REGION_LABELS = ["일반 기업", "스팩"]  # 상장 시장은 신고서 데이터로 구분할 수 없어 쓰지 않는다
TYPE_LABELS = ["공모 구조", "공모 일정"]
ALLOWED_LABELS = set(REGION_LABELS + TYPE_LABELS)
TYPES = ("ipo", "weekly")
ANGLES = {"ipo": ("규모", "자금용도", "공모가", "주관사", "회사"), "weekly": ("일정", "규모비교")}
DISCLOSURE_RE = re.compile(r"(DART|전자공시)[^.\n]{0,40}(가져왔|옮겨|정리했|계산했)")
INVEST_RE = re.compile(r"투자\s?(판단|결정|권유)")
SOURCE_LINK = "dart.fss.or.kr"
MIN_CHARS = 1500
MIN_ANALYSIS = 2
TITLE_WITHIN = 25

BOX = "margin:0 0 28px;padding:18px 18px 12px;border-radius:14px;background:#f5f3ff;border:1px solid #ddd6fe;"
TITLE = "margin:0 0 4px;font-size:17px;font-weight:700;color:#3f2a78;"
SUB = "margin:0 0 12px;font-size:13px;color:#5b4b8a;"
ROW_L = "padding:7px 0;color:#4b5563;font-size:14px;width:42%;border-bottom:1px dashed #ddd6fe;"
ROW_R = "padding:7px 0;color:#111827;font-size:15px;font-weight:700;border-bottom:1px dashed #ddd6fe;"
NOTE = "margin:10px 0 0;font-size:12px;color:#6b7280;"


def ipo(code: str) -> dict | None:
    p = DATA / "ipos" / f"{code}.json"
    return json.loads(p.read_text("utf-8")) if p.exists() else None


def _eok(v) -> str:
    return f"{v / 1e8:,.1f}억 원" if v else "-"


def build_card(meta: dict) -> str:
    if meta.get("type") != "ipo":
        return ""
    d = ipo(str(meta.get("corp_code") or ""))
    if not d:
        return ""
    rows = [("청약일", d.get("subscription") or "-"),
            ("공모가" + ("" if d.get("price_confirmed") else " (신고서 기준)"), f"{d['price']:,}원" if d.get("price") else "-"),
            ("공모 주식 수", f"{d['shares']:,}주" if d.get("shares") else "-"),
            ("공모 총액", _eok(d.get("total"))),
            ("대표 주관사", d.get("lead_underwriter") or "-")]
    trs = "".join(f'<tr><td style="{ROW_L}">{escape(k)}</td><td style="{ROW_R}">{escape(str(v))}</td></tr>' for k, v in rows)
    return (f'<div style="{BOX}"><p style="{TITLE}">{escape(d["corp_name"])} 공모 한눈에</p>'
            f'<p style="{SUB}">{escape(d.get("report_nm", ""))} · 접수 {escape(d["rcept_dt"])}</p>'
            f'<table style="border-collapse:collapse;border:0;width:100%;">{trs}</table>'
            f'<p style="{NOTE}">출처: <a href="{escape(d["dart_url"])}" rel="noopener">DART 증권신고서</a></p></div>')


def recent_posts() -> list[dict]:
    return json.loads(PUBLISHED.read_text("utf-8")).get("posts", []) if PUBLISHED.exists() else []


def _walk(x, out: set[str]) -> None:
    if isinstance(x, dict):
        for v in x.values():
            _walk(v, out)
    elif isinstance(x, list):
        for v in x:
            _walk(v, out)
    elif x is not None and not isinstance(x, bool):
        out.update(core._nums_from(x))
        try:
            n = int(float(x))
        except (TypeError, ValueError):
            return
        if n >= 10000:  # 2,228,917주 → '222만 8,917주'
            out |= {str(n // 10000), str(n % 10000)}
        if n >= 10 ** 8:  # 원 → 억
            e = n / 1e8
            out |= {str(round(e)), f"{e:.1f}".rstrip("0").rstrip("."), str(int(e))}
            out |= core._amount_forms(n // 10000)


def _allowed(meta: dict) -> set[str]:
    out: set[str] = set()
    for c in [str(meta.get("corp_code") or "")] + [str(x) for x in meta.get("corp_codes") or []]:
        d = ipo(c)
        if d:
            _walk(d, out)
    s = DATA / "summary.json"
    if s.exists():
        _walk(json.loads(s.read_text("utf-8")), out)
    return out


def template_sentences(body: str, exclude_file: str = "") -> list[str]:
    if not DONE.exists():
        return []
    seen: set[str] = set()
    for f in sorted(DONE.glob("*.md"))[-40:]:
        if f.name != exclude_file:
            seen |= {core._norm(x) for x in core._sentences(split_post(f.read_text("utf-8"))[1])}
    return [x for x in core._sentences(body)
            if not re.search(r"(DART|전자공시|투자 판단|투자설명서)", x) and core._norm(x) in seen]


def check_text(meta: dict, body: str, recent: list[dict] | None = None) -> list[str]:
    errs: list[str] = []
    for f in ("type", "title", "slug", "description", "labels", "keyword", "opening", "angle"):
        if not meta.get(f):
            errs.append(f"머리말에 {f}가 없습니다.")
    typ = meta.get("type")
    if typ not in TYPES:
        errs.append(f"알 수 없는 type: {typ}")
    if typ == "ipo" and not ipo(str(meta.get("corp_code") or "")):
        errs.append("공모 글인데 corp_code 데이터가 없습니다.")
    if typ in ANGLES and meta.get("angle") not in ANGLES[typ]:
        errs.append(f"angle은 {', '.join(ANGLES[typ])} 중 하나입니다.")
    same = [r for r in (recent or []) if r.get("type") == typ][-2:]
    if len(same) == 2 and all(r.get("angle") == meta.get("angle") for r in same):
        errs.append("같은 종류 직전 2편과 글의 중심(angle)이 같습니다.")
    if recent and recent[-1].get("opening") == meta.get("opening"):
        errs.append("직전 글과 시작 방식(opening)이 같습니다.")
    title, kw = str(meta.get("title", "")), str(meta.get("keyword", ""))
    if "공모주" not in title:
        errs.append("제목에 '공모주'가 들어가야 합니다(청약노트와 검색어 구분).")
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
        errs.append("DART 원문 링크(dart.fss.or.kr)가 없습니다.")
    if not DISCLOSURE_RE.search(body):
        errs.append("출처 문구('DART 증권신고서에서 가져왔어요' 등)가 없습니다.")
    if not INVEST_RE.search(body):
        errs.append("투자 판단은 투자설명서를 보고 직접 하라는 안내가 없습니다.")
    for b in core.BANNED + ("추천합니다", "추천해요", "사세요", "꼭 청약", "무조건", "대박", "따상", "수익 보장"):
        if b in body:
            errs.append(f"금지 표현: '{b}'")
    errs += core.style_errors(body, min_tables=2)
    errs += core.phrase_errors(body, DONE, meta.get("_file", ""))
    errs += core.keyword_errors("gongmoju", meta)
    tmpl = template_sentences(body, meta.get("_file", ""))
    if len(tmpl) > 1:
        errs.append(f"다른 글과 숫자만 다른 같은 문장이 {len(tmpl)}개입니다: " + " / ".join(t[:30] for t in tmpl[:3]))
    allowed = _allowed(meta)
    allowed |= core.snapshot_numbers("gongmoju", meta.get("_file", ""))
    used = set()
    for tok, unit in re.findall(r"(\d[\d,]*(?:\.\d+)?)\s*(억|만|천|%p|%|주|원|곳|위|개|년|배)?", plain):
        t = tok.replace(",", "")
        try:
            v = float(t)
        except ValueError:
            continue
        forms = {t, str(int(v))}
        if not unit and (v <= 12 or 2020 <= v <= 2035):
            continue
        if unit == "년" and 1950 <= v <= 2035:
            continue
        if forms & allowed:
            if unit in ("%", "%p", "위") :
                used |= forms
        else:
            errs.append(f"데이터에 없는 숫자: {tok}{unit or ''}")
    if len(used) < MIN_ANALYSIS:
        errs.append(f"계산 숫자(순위·비중·수수료율 등)가 {len(used)}개입니다 ({MIN_ANALYSIS}개 이상).")
    return list(dict.fromkeys(errs))


def allowed_set(meta: dict, body: str = "") -> set[str]:
    """이 글이 쓸 수 있는 숫자 전체(발행할 때 스냅샷으로 저장)."""
    plain = core.strip_md(body)
    return _allowed(meta)
