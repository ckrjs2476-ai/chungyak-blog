"""글 자동 검수. 사람(Claude)이 스스로 채점하지 않고, 코드가 원본 데이터와 규칙으로 판정한다.

사용: python src/check.py posts/pending/파일.md   → 통과면 0, 실패면 1과 사유 출력
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
UNITS = ROOT / "data" / "units"
ANALYSIS = ROOT / "data" / "analysis"
STATS = ROOT / "data" / "stats" / "latest.json"
PUBLISHED = ROOT / "data" / "published.json"

REQUIRED_FIELDS = ("type", "title", "slug", "description", "labels", "keyword", "opening")
UNIT_TYPES = ("notice", "competition", "score")                  # 단지 1곳: house_manage_no
MULTI_TYPES = ("remainder", "region", "monthly", "stats", "guide")  # 여러 단지·통계: house_manage_nos
ALL_TYPES = UNIT_TYPES + MULTI_TYPES
ALLOWED_LABELS = {"청약일정", "경쟁률", "당첨가점", "무순위", "서울", "경기", "인천", "지방", "청약가이드",
                  "월간정리", "청약통계"}
MIN_ANALYSIS_NUMBERS = 2  # 원본에 없고 분석(data/analysis, data/stats)에만 있는 숫자가 최소 이만큼 있어야 한다
BANNED = ("주목할 점은", "중요한 것은", "도움이 되었", "궁금한 점", "무조건 오른", "당첨 보장",
          "전문가들은", "많은 연구에 따르면", "독자 여러분")
DISCLOSURE = "청약홈 공고 데이터를 바탕으로 자동 정리했어요"
GUIDE_NOTICE = "청약홈 홈페이지를 참고해 주세요"
MIN_CHARS = 1500
MAX_TITLE = 60
TITLE_KEYWORD_WITHIN = 25  # 모바일 검색 결과에서 잘리지 않는 앞부분 안에 메인 키워드
MAX_PARA_SENTENCES = 4
MAX_TABLE_COLS = 4


def split_post(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        raise ValueError("앞부분(--- 머리말 ---)이 없습니다.")
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


def _nums_from(value) -> set[str]:
    out: set[str] = set()
    for tok in re.findall(r"\d[\d,]*(?:\.\d+)?", str(value)):
        t = tok.replace(",", "")
        out.add(t)
        try:
            f = float(t)
        except ValueError:
            continue
        out.add(str(int(f)))
        if "." in t:
            out.add(f"{f:.1f}".rstrip("0").rstrip("."))
            out.add(f"{f:.2f}".rstrip("0").rstrip("."))
        if len(t) == 8 and t.isdigit():  # 20261014
            out |= {t[:4], str(int(t[4:6])), str(int(t[6:]))}
    for y, mth, d in re.findall(r"(\d{4})-(\d{2})-(\d{2})", str(value)):
        out |= {y, str(int(mth)), str(int(d))}
    return out


def _amount_forms(manwon: int) -> set[str]:
    """만원 단위 금액 → 글에 쓰일 수 있는 표기들 (6억 2,000만 / 6.2억 / 62,000만 원 / 620,000,000원)"""
    eok, rest = divmod(manwon, 10000)
    forms = {str(manwon), str(eok), str(rest), str(manwon * 10000)}
    if rest:
        forms |= {str(rest // 1000), f"{manwon / 10000:.1f}".rstrip("0").rstrip("."),
                  f"{manwon / 10000:.2f}".rstrip("0").rstrip(".")}
    return forms


def _walk_nums(x, out: set[str]) -> None:
    if isinstance(x, dict):
        for v in x.values():
            _walk_nums(v, out)
    elif isinstance(x, list):
        for v in x:
            _walk_nums(v, out)
    elif x is not None and not isinstance(x, bool):
        out.update(_nums_from(x))


def analysis_numbers(unit_nos: list[str], with_stats: bool) -> set[str]:
    """data/analysis·data/stats에서 계산한 분석 숫자"""
    out: set[str] = {"3.3"}  # '3.3㎡당' 표기
    for no in unit_nos:
        p = ANALYSIS / f"{no}.json"
        if p.exists():
            _walk_nums(json.loads(p.read_text("utf-8")), out)
    if with_stats and STATS.exists():
        _walk_nums(json.loads(STATS.read_text("utf-8")), out)
    return out


def allowed_numbers(unit_nos: list[str]) -> set[str]:
    allowed: set[str] = set()
    for no in unit_nos:
        p = UNITS / f"{no}.json"
        if not p.exists():
            continue
        unit = json.loads(p.read_text("utf-8"))

        def walk(x):
            if isinstance(x, dict):
                for k, v in x.items():
                    if k.endswith("AMOUNT"):
                        try:
                            allowed.update(_amount_forms(int(float(str(v).replace(",", "")))))
                        except ValueError:
                            pass
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)
            else:
                allowed.update(_nums_from(x))

        walk(unit)
        sup = [int(m.get("SUPLY_HSHLDCO") or 0) + int(m.get("SPSPLY_HSHLDCO") or 0)
               for m in unit.get("models", []) if str(m.get("SUPLY_HSHLDCO", "0")).isdigit()]
        if sup:
            allowed.add(str(sum(sup)))
        # 주택형을 합친 세대수(일반공급 합계, 신혼부부 특공 합계 등)도 원본에서 계산한 값으로 허용
        for field in {k for m in unit.get("models", []) for k in m if k.endswith("HSHLDCO")}:
            vals = [str(m.get(field, "")).strip() for m in unit.get("models", [])]
            if all(v.isdigit() for v in vals if v):
                allowed.add(str(sum(int(v) for v in vals if v)))
        allowed.add(str(len(unit.get("models", []))))
    return allowed


def strip_md(body: str) -> str:
    body = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", body)
    body = re.sub(r"https?://\S+", "", body)
    return body


def sentences(line: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", line.strip())
    return [p for p in parts if p]


def check_text(meta: dict, body: str, recent: list[dict] | None = None) -> list[str]:
    errs: list[str] = []
    for f in REQUIRED_FIELDS:
        if not meta.get(f):
            errs.append(f"머리말에 {f}가 없습니다.")
    typ = meta.get("type")
    unit_nos = [str(x) for x in (meta.get("house_manage_nos") or
                                 ([meta["house_manage_no"]] if meta.get("house_manage_no") else []))]
    if typ not in ALL_TYPES:
        errs.append(f"알 수 없는 type: {typ}")
    if typ in UNIT_TYPES and not unit_nos:
        errs.append("단지 글인데 house_manage_no가 없습니다.")
    if typ in ("remainder", "region", "monthly") and not unit_nos:
        errs.append("여러 단지 글인데 house_manage_nos가 없습니다.")
    title = str(meta.get("title", ""))
    kw = str(meta.get("keyword", ""))
    if kw and kw.split()[0] not in title[:TITLE_KEYWORD_WITHIN]:
        errs.append(f"제목 앞 {TITLE_KEYWORD_WITHIN}자 안에 메인 키워드('{kw}')의 첫 단어가 없습니다.")
    if len(title) > MAX_TITLE:
        errs.append(f"제목이 {len(title)}자로 깁니다 ({MAX_TITLE}자 이하).")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", str(meta.get("slug", ""))):
        errs.append("slug는 영문 소문자·숫자·하이픈만 씁니다.")
    bad_labels = set(meta.get("labels") or []) - ALLOWED_LABELS
    if bad_labels:
        errs.append(f"허용되지 않은 라벨: {sorted(bad_labels)}")
    if not 2 <= len(meta.get("labels") or []) <= 3:
        errs.append("라벨은 2~3개입니다.")
    desc = str(meta.get("description", ""))
    if not 50 <= len(desc) <= 160:
        errs.append(f"검색 설명이 {len(desc)}자입니다 (50~160자).")

    plain = strip_md(body)
    chars = len(re.sub(r"[\s|#>*\-:]", "", plain))
    if chars < MIN_CHARS:
        errs.append(f"본문이 {chars}자로 짧습니다 ({MIN_CHARS}자 이상).")
    if "applyhome.co.kr" not in body:
        errs.append("청약홈 원문 링크(applyhome.co.kr)가 없습니다.")
    if typ == "guide":
        if GUIDE_NOTICE not in body:
            errs.append("가이드 글에 '청약홈 홈페이지를 참고해 주세요' 안내가 없습니다.")
    elif DISCLOSURE not in body:
        errs.append("자동 정리 안내 문구가 없습니다.")
    for b in BANNED:
        if b in body:
            errs.append(f"금지 표현: '{b}'")

    # 표: 개수와 열 수
    tables = 0
    in_table = False
    for line in body.splitlines():
        if line.strip().startswith("|"):
            if not in_table:
                tables += 1
                in_table = True
                cols = len([c for c in line.strip().strip("|").split("|")])
                if cols > MAX_TABLE_COLS:
                    errs.append(f"표 열이 {cols}개입니다 ({MAX_TABLE_COLS}열 이하).")
        else:
            in_table = False
    if tables < 2:
        errs.append(f"표가 {tables}개입니다 (2개 이상).")

    # 문장 끝 말투, 문단 길이
    for block in re.split(r"\n\s*\n", body):
        lines = [l for l in block.splitlines() if l.strip() and not l.strip().startswith(("|", "#", ">"))]
        if not lines:
            continue
        sents = [s for l in lines for s in sentences(re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", l))]
        if len(lines) == 1 and len(sents) > MAX_PARA_SENTENCES:
            errs.append(f"문단이 {len(sents)}문장입니다: '{sents[0][:20]}…'")
        for s in sents:
            s2 = s.rstrip(" .!?\"')")
            if s2.endswith("다") and not s2.endswith("니다"):
                errs.append(f"딱딱한 말투: '…{s2[-15:]}.'")

    # 숫자 대조: 원본 데이터 또는 분석 데이터에 있는 숫자만 쓴다
    with_stats = typ in MULTI_TYPES
    raw = allowed_numbers(unit_nos)
    extra = analysis_numbers(unit_nos, with_stats)
    allowed = raw | extra
    analysis_only = extra - raw
    used_analysis: set[str] = set()
    for tok, unit in re.findall(r"(\d[\d,]*(?:\.\d+)?)\s*(억|만|천|세대|㎡|%|대\s*1|점|건|곳|개)?", plain):
        t = tok.replace(",", "")
        try:
            v = float(t)
        except ValueError:
            continue
        forms = {t, str(int(v))}
        if forms & analysis_only and (unit or v > 12):
            used_analysis |= forms & analysis_only
        # 작은 수와 연도는 넘어가되, 금액·세대·면적·비율·가점 단위가 붙은 수는 항상 대조
        if not unit and (v <= 12 or 2020 <= v <= 2035):
            continue
        if not (forms & allowed):
            errs.append(f"원본·분석 데이터에 없는 숫자: {tok}")
    if len(used_analysis) < MIN_ANALYSIS_NUMBERS:
        errs.append(f"분석 숫자가 {len(used_analysis)}개입니다 ({MIN_ANALYSIS_NUMBERS}개 이상). "
                    "data/analysis 또는 data/stats의 평당가·비교·순위 같은 숫자를 넣어 주세요.")

    # 직전 글과 구조 비교
    recent = recent or []
    heads = [h.strip("# ").strip() for h in body.splitlines() if h.startswith("## ")]
    if recent:
        if recent[-1].get("opening") == meta.get("opening"):
            errs.append("직전 글과 시작 방식(opening)이 같습니다.")
        for r in recent[-10:]:
            prev = set(r.get("headings_pattern") or [])
            cur = {re.sub(r"[\d,.]+", "N", h) for h in heads}
            if prev and cur and len(prev & cur) / len(prev | cur) > 0.6:
                errs.append(f"최근 글 '{r.get('title', '')[:15]}…'과 소제목 구성이 비슷합니다.")
                break
    return list(dict.fromkeys(errs))


def recent_posts() -> list[dict]:
    if PUBLISHED.exists():
        return json.loads(PUBLISHED.read_text("utf-8")).get("posts", [])
    return []


def check_file(path: Path) -> list[str]:
    try:
        meta, body = split_post(path.read_text("utf-8"))
    except Exception as e:  # noqa: BLE001
        return [str(e)]
    return check_text(meta, body, recent_posts())


if __name__ == "__main__":
    bad = 0
    for arg in sys.argv[1:]:
        errs = check_file(Path(arg))
        print(f"[{'통과' if not errs else '실패'}] {arg}")
        for e in errs:
            print("  -", e)
        bad += bool(errs)
    sys.exit(1 if bad else 0)
