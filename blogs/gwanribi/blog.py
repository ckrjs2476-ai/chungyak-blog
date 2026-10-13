"""관리비 돋보기 블로그 설정: 라벨, 요약 카드, 검수 규칙.
publish.py가 BLOG_KEY=gwanribi일 때 이 파일을 불러 쓴다."""
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
UNIT_KEY = "kapt"
DATA = HERE / "data"
DONE = HERE / "posts" / "published"
PUBLISHED = DATA / "published.json"

REGION_LABELS = ["서울", "경기", "인천", "지방"]
TYPE_LABELS = ["단지 관리비", "지역 관리비", "관리비 읽는 법"]
ALLOWED_LABELS = set(REGION_LABELS + TYPE_LABELS)
TYPES = ("complex", "region", "topic")
ANGLES = {"complex": ("총액", "공용항목", "개별사용료", "장기수선", "같은규모"),
          "region": ("순위", "격차", "항목", "난방방식", "단지규모"),
          # topic: 검색이 있는 관리비 주제(장기수선충당금, 고지서 등)를 우리 단지 데이터를 예시로 풀어 주는 글
          "topic": ("장기수선", "고지서", "공용항목", "개별사용료")}
# 다른 블로그와 다른 출처 문구. 뜻이 같으면 표현은 바꿔도 된다.
DISCLOSURE_RE = re.compile(r"(공동주택관리정보시스템|K-apt|국토교통부)[^.\n]{0,40}(관리비)[^.\n]{0,40}(나눠|계산|비교)했어요")
SOURCE_LINK = "k-apt.go.kr"
MIN_CHARS = 1500
MIN_ANALYSIS = 3
TITLE_WITHIN = 25

# 요약 카드: 초록 계열(청약노트 회색, 전세 남색, 공모주 보라와 다르게)
BOX = "margin:0 0 28px;padding:18px 18px 12px;border-radius:12px;background:#ecfdf5;border:1px solid #a7f3d0;"
TITLE = "margin:0 0 4px;font-size:17px;font-weight:700;color:#065f46;"
SUB = "margin:0 0 12px;font-size:13px;color:#047857;"
ROW_L = "padding:7px 0;color:#334155;font-size:14px;width:46%;border-bottom:1px solid #d1fae5;"
ROW_R = "padding:7px 0;color:#0f172a;font-size:15px;font-weight:700;border-bottom:1px solid #d1fae5;"
NOTE = "margin:10px 0 0;font-size:12px;color:#475569;"


def region(lawd: str) -> dict | None:
    p = DATA / "regions" / f"{lawd}.json"
    return json.loads(p.read_text("utf-8")) if p.exists() else None


def find_complex(code: str) -> tuple[dict | None, dict | None]:
    for p in sorted((DATA / "regions").glob("*.json")) if (DATA / "regions").exists() else []:
        d = json.loads(p.read_text("utf-8"))
        for c in d.get("complexes") or []:
            if c["code"] == code:
                return d, c
    return None, None


def _won(n) -> str:
    if n is None:
        return "-"
    n = int(n)
    man, rest = divmod(n, 10000)
    return f"{man:,}만 {rest:,}원" if man and rest else f"{man:,}만 원" if man else f"{rest:,}원"


def build_card(meta: dict) -> str:
    if meta.get("type") == "complex":
        d, c = find_complex(str(meta.get("kapt") or ""))
        if not c:
            return ""
        head = f"{c['name']} 관리비"
        sub = f"{d['ym_label']} 부과분 · {d['name']} {d['n_complex']}개 단지와 비교"
        rows = [("㎡당 관리비(장기수선 포함)", f"{c['total_m2']:,}원"),
                ("세대 평균", _won(c["total_hh"])),
                (f"{d['name']} 안 순위", f"{c['rank_total_m2_of']}곳 중 {c['rank_total_m2']}위 (높은 순)"),
                ("지역 중앙값과 차이", f"{c['total_m2_vs_median_pct']:+}%" if c.get("total_m2_vs_median_pct") is not None else "-"),
                ("공용관리비 ㎡당", f"{c['common_m2']:,}원")]
    elif meta.get("type") == "region":
        d = region(str(meta.get("lawd") or ""))
        if not d or d.get("empty"):
            return ""
        head = f"{d['name']} 아파트 관리비"
        sub = f"{d['ym_label']} 부과분 · {d['min_households']}세대 이상 {d['n_complex']}개 단지"
        rows = [("㎡당 관리비 중앙값(장기수선 포함)", f"{d['median']['total_m2']:,}원"),
                ("공용관리비 ㎡당 중앙값", f"{d['median']['common_m2']:,}원"),
                ("공용관리비 가장 높은 단지", f"{d['rank_common_high5'][0]['common_m2']:,}원/㎡"),
                ("공용관리비 가장 낮은 단지", f"{d['rank_common_low5'][0]['common_m2']:,}원/㎡"),
                ("세대 평균 중앙값", _won(d["median"]["total_hh"]))]
    else:
        return ""
    trs = "".join(f'<tr><td style="{ROW_L}">{escape(k)}</td><td style="{ROW_R}">{escape(v)}</td></tr>' for k, v in rows)
    return (f'<div style="{BOX}"><p style="{TITLE}">{escape(head)}</p><p style="{SUB}">{escape(sub)}</p>'
            f'<table style="border-collapse:collapse;border:0;width:100%;">{trs}</table>'
            f'<p style="{NOTE}">출처: 공동주택관리정보시스템(K-apt) 공개 관리비 · 관리비부과면적으로 나눈 값</p></div>')


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
            f = float(x)
        except (TypeError, ValueError):
            return
        n = int(f)
        if n >= 10000:  # 원 → '23만 4,567원', '23.5만 원', '약 23만 원'
            man = n / 10000
            out |= {str(n // 10000), str(n % 10000), str(round(man)), f"{man:.1f}".rstrip("0").rstrip(".")}
            if n % 10000:
                out.add(str((n % 10000) // 1000 * 1000))
        if n >= 10 ** 8:  # 원 → 억
            out |= core._amount_forms(n // 10000)
            e = n / 1e8
            out |= {str(round(e)), f"{e:.1f}".rstrip("0").rstrip(".")}
        if 0 < abs(f) < 1000 and f != n:  # 퍼센트 등 소수 → 반올림 정수도 허용
            out.add(str(round(abs(f))))


def _region_part(d: dict, body: str, keep: str = "") -> dict:
    """시군구 요약 숫자 + 글에 이름이 나온 단지(그리고 글의 대상 단지)만. 다른 단지 숫자까지 허용하면 틀린 숫자가 우연히 통과한다."""
    out = {k: v for k, v in d.items() if k != "complexes"}
    out["complexes"] = [c for c in d.get("complexes") or [] if c["code"] == keep or (c["name"] and c["name"] in body)]
    return out


def _allowed(meta: dict, body: str = "") -> set[str]:
    out: set[str] = {"84", "300", "500", "999", "1000", "1,000"}
    kapt = str(meta.get("kapt") or "")
    if meta.get("type") == "complex":
        d, _ = find_complex(kapt)
        if d:
            _walk(_region_part(d, body, kapt), out)
    for l in [str(meta.get("lawd") or "")] + [str(x) for x in meta.get("lawds") or []]:
        d = region(l)
        if d:
            _walk(_region_part(d, body, kapt), out)
    s = DATA / "summary.json"
    if s.exists():
        _walk(json.loads(s.read_text("utf-8")), out)
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
            if not re.search(r"(나눠 계산했어요|비교했어요|확인해 보세요|k-apt)", x, re.I) and core._norm(x) in seen]


def check_text(meta: dict, body: str, recent: list[dict] | None = None) -> list[str]:
    errs: list[str] = []
    for f in ("type", "title", "slug", "description", "labels", "keyword", "opening", "angle"):
        if not meta.get(f):
            errs.append(f"머리말에 {f}가 없습니다.")
    typ = meta.get("type")
    if typ not in TYPES:
        errs.append(f"알 수 없는 type: {typ}")
    if typ == "complex" and not find_complex(str(meta.get("kapt") or ""))[1]:
        errs.append("단지 글인데 kapt(단지코드) 데이터가 없습니다.")
    if typ == "topic":
        ls = [str(x) for x in meta.get("lawds") or []]
        if not ls or not all(region(l) and not region(l).get("empty") for l in ls):
            errs.append("주제 글은 예시로 쓸 시군구 코드 목록(lawds)이 필요하고, 모두 데이터가 있어야 합니다.")
    if typ == "region":
        d = region(str(meta.get("lawd") or ""))
        if not d or d.get("empty"):
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
    if "관리비" not in title:
        errs.append("제목에 '관리비'가 없습니다.")
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
        errs.append("공동주택관리정보시스템 링크(k-apt.go.kr)가 없습니다.")
    if not DISCLOSURE_RE.search(body):
        errs.append("출처 문구('공동주택관리정보시스템 … 관리비 … 나눠 계산했어요')가 없습니다.")
    for b in core.BANNED + ("비리", "횡령", "부정", "바가지", "과다 청구", "덤터기", "새고 있"):
        if b in body:
            errs.append(f"금지 표현: '{b}'")
    errs += core.style_errors(body, min_tables=2)
    errs += core.phrase_errors(body, DONE, meta.get("_file", ""))
    errs += core.keyword_errors("gwanribi", meta)
    tmpl = template_sentences(body, meta.get("_file", ""))
    if len(tmpl) > 1:
        errs.append(f"다른 글과 숫자만 다른 같은 문장이 {len(tmpl)}개입니다: " + " / ".join(t[:30] for t in tmpl[:3]))
    allowed = _allowed(meta, plain)
    allowed |= core.snapshot_numbers("gwanribi", meta.get("_file", ""))
    used = set()
    for tok, unit in re.findall(r"(\d[\d,]*(?:\.\d+)?)\s*(억|만|천|원|%p|%|곳|위|개|세대|㎡|배|년)?", plain):
        t = tok.replace(",", "")
        try:
            v = float(t)
        except ValueError:
            continue
        forms = {t, str(int(v))}
        if not unit and (v <= 12 or 2020 <= v <= 2035):
            continue
        if unit in ("년",) and 1960 <= v <= 2035:
            continue
        if forms & allowed:
            if unit in ("%", "%p", "위", "배") or v > 100:
                used |= forms
        else:
            errs.append(f"데이터에 없는 숫자: {tok}{unit or ''}")
    if len(used) < MIN_ANALYSIS:
        errs.append(f"계산 숫자(㎡당 금액·순위·중앙값 대비 % 등)가 {len(used)}개입니다 ({MIN_ANALYSIS}개 이상).")
    return list(dict.fromkeys(errs))


def allowed_set(meta: dict, body: str = "") -> set[str]:
    """이 글이 쓸 수 있는 숫자 전체(발행할 때 스냅샷으로 저장)."""
    plain = core.strip_md(body)
    return _allowed(meta, plain)
