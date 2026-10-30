"""드론 정보노트 블로그 설정: 라벨, 검수 규칙 (2026-10-30).
publish.py가 BLOG_KEY=drone일 때 이 파일을 불러 쓴다.
다른 블로그와 달리 숫자 데이터 파일이 없다. 대신 글마다 출처 노트(data/sources/<slug>.md)를 두고,
본문 숫자는 그 노트(공식 자료를 실제로 열어 옮겨 둔 것)에 있는 것만 쓴다."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
import check as core  # noqa: E402

split_post = core.split_post
UNIT_KEY = "topic_id"
DATA = HERE / "data"
SOURCES = DATA / "sources"
DONE = HERE / "posts" / "published"
PUBLISHED = DATA / "published.json"

REGION_LABELS: list[str] = []
TYPE_LABELS = ["드론 기초", "드론 규정", "드론 직업", "드론 소식"]
ALLOWED_LABELS = set(TYPE_LABELS)
TYPES = ("basic", "rule", "job", "news")
TYPE_LABEL = {"basic": "드론 기초", "rule": "드론 규정", "job": "드론 직업", "news": "드론 소식"}
ANGLES = ("방법", "비교", "기준", "변화", "현장", "오해")
# 2026-12-31까지 쓰지 않는 주제(사용자 결정): 자격증 취득 관련
BANNED_TOPICS = re.compile(r"(필기|실기|자격증\s*(종류|비용|취득|시험|난이도)|국비|국가\s*지원|내일배움|교육비|응시료|합격률)")
OFFICIAL = ("molit.go.kr", "law.go.kr", "onestop.go.kr", "kotsa.or.kr", "kadis.or.kr", "work24.go.kr",
            "kosis.kr", "korea.kr", "gov.kr", "go.kr", "or.kr")
MIN_CHARS = 1600
TITLE_WITHIN = 25

BOX = "margin:0 0 28px;padding:16px 18px;border-radius:12px;background:#f0fdfa;border:1px solid #99f6e4;"


def build_card(meta: dict) -> str:
    q = str(meta.get("answer") or "").strip()
    if not q:
        return ""
    from html import escape
    return (f'<div style="{BOX}"><p style="margin:0 0 6px;font-size:13px;color:#0f766e;font-weight:700;">한 줄 답</p>'
            f'<p style="margin:0;font-size:16px;color:#134e4a;line-height:1.7;">{escape(q)}</p></div>')


def recent_posts() -> list[dict]:
    return json.loads(PUBLISHED.read_text("utf-8")).get("posts", []) if PUBLISHED.exists() else []


def source_text(meta: dict) -> str:
    p = SOURCES / f"{meta.get('slug', '')}.md"
    return p.read_text("utf-8") if p.exists() else ""


def _allowed(meta: dict) -> set[str]:
    out: set[str] = set()
    for tok in re.findall(r"\d[\d,]*(?:\.\d+)?", source_text(meta)):
        t = tok.replace(",", "")
        out.add(t)
        try:
            out.add(str(int(float(t))))
        except ValueError:
            pass
    return out


def check_text(meta: dict, body: str, recent: list[dict] | None = None) -> list[str]:
    errs: list[str] = []
    for f in ("type", "title", "slug", "description", "labels", "keyword", "opening", "angle", "answer"):
        if not meta.get(f):
            errs.append(f"머리말에 {f}가 없습니다.")
    typ = meta.get("type")
    if typ not in TYPES:
        errs.append(f"알 수 없는 type: {typ} ({', '.join(TYPES)})")
    if meta.get("angle") not in ANGLES:
        errs.append(f"angle은 {', '.join(ANGLES)} 중 하나입니다.")
    labels = list(meta.get("labels") or [])
    if set(labels) - ALLOWED_LABELS:
        errs.append(f"허용되지 않은 라벨: {sorted(set(labels) - ALLOWED_LABELS)}")
    if typ in TYPE_LABEL and TYPE_LABEL[typ] not in labels:
        errs.append(f"type {typ}의 라벨 '{TYPE_LABEL[typ]}'이 없습니다.")
    if not 1 <= len(labels) <= 2:
        errs.append("라벨은 1~2개입니다.")
    if BANNED_TOPICS.search(str(meta.get("title", "")) + " " + str(meta.get("keyword", ""))):
        errs.append("자격증 취득 관련 주제(필기·실기·비용·국비 등)는 2026-12-31까지 쓰지 않습니다.")
    title, kw = str(meta.get("title", "")), str(meta.get("keyword", ""))
    if kw and kw.split()[0] not in title[:TITLE_WITHIN]:
        errs.append(f"제목 앞 {TITLE_WITHIN}자 안에 키워드 첫 단어('{kw.split()[0]}')가 없습니다.")
    if len(title) > 60:
        errs.append("제목이 60자를 넘습니다.")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", str(meta.get("slug", ""))):
        errs.append("slug는 영문 소문자·숫자·하이픈만 씁니다.")
    if not 50 <= len(str(meta.get("description", ""))) <= 160:
        errs.append("검색 설명은 50~160자입니다.")
    if not 20 <= len(str(meta.get("answer", ""))) <= 120:
        errs.append("answer(한 줄 답)는 20~120자입니다.")
    if recent and recent[-1].get("opening") == meta.get("opening"):
        errs.append("직전 글과 시작 방식(opening)이 같습니다.")
    same = [r for r in (recent or []) if r.get("type") == typ][-2:]
    if len(same) == 2 and all(r.get("angle") == meta.get("angle") for r in same):
        errs.append("같은 종류 직전 2편과 글의 중심(angle)이 같습니다.")
    src = source_text(meta)
    if len(src) < 300:
        errs.append(f"출처 노트(blogs/drone/data/sources/{meta.get('slug')}.md)가 없거나 짧습니다. 공식 자료를 열어 확인한 내용·URL·확인일을 적어 둡니다.")
    links = re.findall(r"\]\((https?://[^)\s]+)\)", body)
    if not any(any(d in l for d in OFFICIAL) for l in links):
        errs.append("본문에 공식 출처(정부·공공기관·법령) 링크가 없습니다.")
    if not re.search(r"(20\d\d년 \d{1,2}월 \d{1,2}일|20\d\d\.\s?\d{1,2}\.\s?\d{1,2}).{0,20}(기준|확인)", body):
        errs.append("확인일('2026년 10월 30일 기준/확인')이 본문에 없습니다.")
    plain = core.strip_md(body)
    chars = len(re.sub(r"[\s|#>*\-:]", "", plain))
    if chars < MIN_CHARS:
        errs.append(f"본문이 {chars}자로 짧습니다 ({MIN_CHARS}자 이상).")
    for b in core.BANNED + ("추천합니다", "무조건", "합격 보장", "100%", "최고의 학원", "꼭 수강", "지금 바로 신청"):
        if b in body:
            errs.append(f"금지 표현: '{b}'")
    errs += core.style_errors(body, min_tables=1)
    errs += core.phrase_errors(body, DONE, meta.get("_file", ""))
    allowed = _allowed(meta) | core.snapshot_numbers("drone", meta.get("_file", ""))
    for tok, unit in re.findall(r"(\d[\d,]*(?:\.\d+)?)\s*(억|만|천|%p|%|kg|g|m|km|시간|분|년|개월|일|명|건|곳|개|원|만 원|미터)?", plain):
        t = tok.replace(",", "")
        try:
            v = float(t)
        except ValueError:
            continue
        if not unit and v <= 10:
            continue
        if 2015 <= v <= 2035 and not unit:
            continue
        if {t, str(int(v))} & allowed:
            continue
        errs.append(f"출처 노트에 없는 숫자: {tok}{unit or ''}")
    return list(dict.fromkeys(errs))


def allowed_set(meta: dict, body: str = "") -> set[str]:
    return _allowed(meta)
