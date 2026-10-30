"""검색 노출 점검(구글 SEO·AEO·GEO). 근거: rules/seo_guide.md.

- seo_errors(meta, body): 발행을 막는 항목(검수에 포함). 새 글은 이것을 통과해야 올라간다.
- seo_warnings(meta, body): 고치면 좋은 항목. 매일 점검이 보고서로 보고 공개 글을 고친다.
- python src/seo.py            → 4개 블로그 공개 글 전부 점검, data/seo_report.md
- python src/seo.py <파일.md>  → 원고 하나 점검(쓰는 중 확인용)

구글은 순위 계산을 공개하지 않는다. 여기 항목은 구글 공식 문서가 권하는 것과
GEO 연구(통계·출처 문장·읽기 쉬운 문장)를 원고에서 기계로 잴 수 있는 형태로 옮긴 것이다.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KST = timezone(timedelta(hours=9))
BLOGS = {"cheongyak": ("청약노트", ROOT), "jeonse": ("전세 온도계", ROOT / "blogs/jeonse"),
         "gongmoju": ("공모주 뜯어보기", ROOT / "blogs/gongmoju"), "gwanribi": ("관리비 돋보기", ROOT / "blogs/gwanribi")}

SOURCES = r"(항공안전법|국가법령정보센터|법령 원문|시행규칙|시행령|드론원스톱|한국교통안전공단|고용24|보도자료|청약홈|입주자모집공고|국토교통부|국토부|실거래가|DART|전자공시|증권신고서|투자설명서|K-apt|공동주택관리정보시스템|공공데이터|한국부동산원)"
CITE_RE = re.compile(SOURCES + r"[^.\n]{0,40}?(따르면|기준|자료|공고|집계|공시|에서|에 공개|에 등록|에 올라|을 낸|를 낸|원문|원자료|가져)")
VAGUE_ANCHOR = re.compile(r"\[(여기|이곳|더 ?보기|클릭|링크|바로가기)\]\(")
DATE_RE = re.compile(r"(20\d\d년\s*\d{1,2}월(\s*\d{1,2}일)?|20\d\d[-.]\d{1,2}([-.]\d{1,2})?|\d{1,2}월\s*\d{1,2}일)")
NUM_RE = re.compile(r"\d[\d,]*(\.\d+)?\s*(억|만|천|원|세대|㎡|%|대\s*1|점|건|곳|개|배|위|kg|g|m|km|명|시간|분|년|개월|일)")
PRONOUN_START = re.compile(r"^(이는|이것은|이건|그래서|그러나|하지만|또한|게다가|이 때문에|이처럼|그런데)\b")


def _split(text: str) -> tuple[dict, str]:
    import yaml
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    return (yaml.safe_load(m.group(1)) or {}, m.group(2)) if m else ({}, text)


def _paragraphs(body: str) -> list[str]:
    """표·소제목·목록·인용·HTML을 뺀 일반 문단."""
    out = []
    for block in re.split(r"\n\s*\n", body):
        b = block.strip()
        if not b or b.startswith(("#", "|", "<", ">", "- ", "* ", "1.", "---")):
            continue
        out.append(re.sub(r"\s+", " ", b))
    return out


def _plain(s: str) -> str:
    return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s).replace("**", "")


def _sentences(text: str) -> list[str]:
    return [x.strip() for x in re.split(r"(?<=[.?!다요])\s+", text) if len(x.strip()) > 4]


def _target(meta: dict) -> str:
    """키워드의 대상(첫 단어). '송파구 아파트 전세' → '송파구'."""
    kw = str(meta.get("keyword", "")).strip()
    return kw.split()[0] if kw else ""


def _sections(body: str) -> list[tuple[str, str]]:
    parts = re.split(r"^##\s+(.+)$", body, flags=re.M)
    return [(parts[i].strip(), parts[i + 1]) for i in range(1, len(parts) - 1, 2)]


# 첫 두 문단에 원자료에 없는 비교(순위·평균/중앙값 대비·%차이)가 있어야 한다: 심사관이 처음 보는 화면 (2026-10-19 전수 점검)
COMPARE_RE = re.compile(r"(\d+\s*곳\s*(중|가운데)|\d+\s*(위|번째)(였|로|에|이|예|입|,|\.|\s)|(평균|중앙값|시세|신축)\s*(보다|대비|에 비해)"
                        r"|\d+(\.\d+)?\s*%p|\d+(\.\d+)?\s*%\s*(높|낮|많|적|비싸|싸|올랐|내렸|하락|상승|늘|줄|차이)|가장 (높|낮|많|적|비싸|싸|크|작))")
# 청약·투자 행동을 권하는 말투(YMYL): 사실만 쓰고 판단은 독자에게
ADVICE_RE = re.compile(r"(편이 (안전|낫|좋|편하|현실적)|먼저 보는 (게|것이) 순서|(하|넣|노리|신청하|청약하)는 게 (좋|낫)|기회예요|가능성이 높은 구조|노린다면|사실상 전부예요|확인해 둬야 해요)")


RANK_RE = re.compile(r"\d+\s*곳\s*(중|가운데)\s*\d+\s*(위|번째)")
BASIS_RE = re.compile(r"(\d{1,2}월 \d{1,2}일[^.\n]{0,15}(기준|집계)|공고(일)?[^.\n]{0,25}(이전|기준|전)|(기준|집계)일|발행일 기준"
                      r"|\d{4}년 \d{1,2}월[^.\n]{0,40}기준|\d{1,2}월 \d{1,2}일 공고 전)")


def seo_errors(meta: dict, body: str, blog: str = "", new: bool = False) -> list[str]:
    """new=True: 발행 전 새 글에만 더하는 규칙(rules/seo_guide.md 13장). 공개 글 일괄 점검에는 넣지 않는다."""
    errs: list[str] = new_post_errors(meta, body, blog) if new else []
    if RANK_RE.search(body) and not BASIS_RE.search(body):
        errs.append("[가치] 'N곳 중 M위' 같은 순위를 쓰면서 기준(○월 ○일 집계, 공고일 이전 6개월 등)을 밝히지 않았습니다. "
                    "데이터가 매일 바뀌어 기준 없는 순위는 글끼리 모순으로 읽힙니다.")
    for m in re.finditer(r"(\d{1,3}(,\d{3})+|\d{4,})(\.\d+)?\s*%", body):
        errs.append(f"[가치] 1,000% 넘는 비율({m.group(0)}): 기준값이 작은 항목입니다. 금액 두 개(예: 524원, 중앙값 28원)로 쓰세요.")
        break
    if re.search(r"(?<!\d)[23]\s*곳\s*(중|가운데)", str(meta.get("title", ""))):
        errs.append("[가치] 제목의 핵심이 2~3곳 비교입니다. 비교 대상이 적은 값은 제목·첫 문장 핵심으로 쓰지 마세요.")
    lead2 = _plain(" ".join(_paragraphs(body)[:2]))
    if blog != "drone" and not COMPARE_RE.search(lead2):
        errs.append("[가치] 첫 두 문단에 원자료에 없는 비교(N곳 중 M위, 평균·중앙값 대비 X% 등)가 없습니다. "
                    "공고·공시를 옮기는 문장으로 시작하지 말고 이 대상만의 비교로 시작하세요.")
    adv = ADVICE_RE.findall(_plain(body))
    if adv:
        errs.append(f"[가치] 청약·투자 행동을 권하는 표현: {', '.join(sorted({a[0] if isinstance(a, tuple) else a for a in adv}))}. 사실만 쓰세요.")
    paras = _paragraphs(body)
    lead = _plain(" ".join(paras[:1]))
    t = _target(meta)
    # AEO: 첫 문단에 대상과 핵심 숫자가 함께 있어야 검색 스니펫·AI 답변이 그 문단을 답으로 쓴다
    if t and t not in lead:
        errs.append(f"[검색] 첫 문단에 검색 대상('{t}')이 없습니다. 첫 문단에서 대상과 핵심 숫자로 답부터 쓰세요.")
    if not (NUM_RE.search(lead) or DATE_RE.search(lead)):
        errs.append("[검색] 첫 문단에 핵심 숫자나 날짜가 없습니다(답을 먼저: 가격·비율·건수·일정 등).")
    heads = _sections(body)
    if len(heads) < 3:
        errs.append(f"[검색] 소제목(##)이 {len(heads)}개입니다(3개 이상, 검색어에 쓰일 말로).")
    # GEO: 출처를 문장 안에서 밝힌다
    text = _plain(" ".join(paras))
    full = _plain(re.sub(r"^>\s?", "", body, flags=re.M))
    if not CITE_RE.search(text):
        errs.append("[검색] 본문 문장 안에 출처('청약홈 공고에 따르면', '국토교통부 실거래가 기준' 등)가 없습니다.")
    if not DATE_RE.search(full):
        errs.append("[검색] 기준일(언제 자료인지)이 본문에 없습니다.")
    if VAGUE_ANCHOR.search(body):
        errs.append("[검색] '여기·더 보기' 같은 링크 문구가 있습니다. 무엇으로 가는 링크인지 쓰세요.")
    return errs


# ---- 새 글에만 적용(2026-10-30 사용자 요청: SEO·GEO·AEO·AI 인용·신뢰·내부 링크·중복 방지·검색자 질문) ----
HOSTS = {"cheongyak": ("daily-cheongyak", ROOT), "jeonse": ("jeonse-ondogye", ROOT / "blogs/jeonse"),
         "gongmoju": ("gongmoju-breakdown", ROOT / "blogs/gongmoju"), "gwanribi": ("gwanribi-dotbogi", ROOT / "blogs/gwanribi"),
         "drone": ("drone-note", ROOT / "blogs/drone")}
OFFICIAL_LINK = re.compile(r"\]\(https?://[^)\s]*(\.go\.kr|\.or\.kr|applyhome\.co\.kr|kosis\.kr|korea\.kr|krx\.co\.kr|kind\.krx)", re.I)
GENERIC_HEAD = re.compile(r"^(개요|정리|마무리|결론|요약|들어가며|마치며|총정리|목차|참고|기타|소개|서론|본론)$|(총정리|마무리|결론)$")
QUESTION_HEAD = re.compile(r"(\?$|나요\??$|까요?\??$|일까|인가요?|얼마|어디|언제|왜|무엇|뭔가요|뭐예요|몇\s?[가-힣]*|어떻게|누가|누구)")
DEF_RE = re.compile(r"[가-힣A-Za-z0-9·()]{2,}\s?(은|는|이란|란|이라는 건|라는 건|이라고 하면)\s[^.?!\n]{3,100}?"
                    r"(말해요|말합니다|뜻해요|뜻합니다|가리켜요|가리킵니다|부르는 말|불러요|부릅니다"
                    r"|(값|비율|금액|제도|방식|절차|물량|비용|기간|가격|계약|공급|항목|돈|날|숫자|장치|기체|면허|자격|구역|공역|승인|신고)(이에요|예요|입니다|이고|이며|을 뜻|를 뜻))")
DEP_START = re.compile(r"^(이는|이것은|이건|이게|이처럼|이 때문에|이렇게|앞서|위에서|위 표|그래서|그러니|하지만|또한|게다가|그런데)\b")


NEW_RULES_FROM = "2026-10-30"  # 이 날짜 이후 파일 이름(YYYY-MM-DD-…)의 원고에만 새 규칙 적용


def is_new(fname: str) -> bool:
    return bool(re.match(r"20\d\d-\d\d-\d\d", fname or "")) and fname[:10] >= NEW_RULES_FROM


def _norm_kw(k: str) -> str:
    return re.sub(r"\s+", "", str(k or "")).lower()


def _published(blog: str) -> list[dict]:
    import json
    if blog not in HOSTS:
        return []
    p = HOSTS[blog][1] / "data/published.json"
    if not p.exists():
        return []
    d = json.loads(p.read_text("utf-8"))
    return d.get("posts", []) if isinstance(d, dict) else d


def new_post_errors(meta: dict, body: str, blog: str) -> list[str]:
    errs: list[str] = []
    heads = _sections(body)
    paras = _paragraphs(body)
    # 1. SEO 소제목: 내용이 드러나는 문장형
    bad = [h for h, _ in heads if GENERIC_HEAD.search(h.strip()) or len(h.strip()) < 6]
    if bad:
        errs.append(f"[SEO] 내용이 안 드러나는 소제목: {bad[:3]}. 검색어가 들어간 문장형으로 쓰세요.")
    # 2. AEO: 실제 질문형 소제목 + 바로 아래 첫 문장이 답
    need_q = 2 if blog == "drone" else 1
    qs = [(h, sec) for h, sec in heads if QUESTION_HEAD.search(h.strip())]
    if len(qs) < need_q:
        errs.append(f"[AEO] 질문형 소제목이 {len(qs)}개입니다({need_q}개 이상). 검색자가 실제로 묻는 말로 쓰세요.")
    for h, sec in qs:
        p = _paragraphs(sec)
        first = _sentences(_plain(p[0]))[:1] if p else []
        if not first or first[0].endswith("?") or DEP_START.match(first[0]) or len(first[0]) > 110:
            errs.append(f"[AEO] 질문 소제목 '{h[:25]}' 바로 아래 첫 문장이 답이 아닙니다(질문·접속사로 시작·110자 넘음). 답부터 한 문장으로.")
            break
    # 3. GEO: 핵심 용어 정의 문장 1개 이상
    if not DEF_RE.search(_plain(" ".join(paras))):
        errs.append("[GEO] 용어 정의 문장이 없습니다. 핵심 용어 하나를 한 문장으로 정의하세요. 예: 'OO는 ~을 말해요', 'OO는 ~로 계산한 값이에요', 'OO는 ~하는 제도예요'(글마다 다른 용어·다른 표현).")
    # 4. AI 인용: 문단만 떼어 읽어도 통하게
    dep = [p for p in paras if DEP_START.match(_plain(p))]
    if len(dep) >= 3:
        errs.append(f"[GEO] '이는·이처럼·그래서·하지만'처럼 앞 문단에 기대어 시작하는 문단 {len(dep)}개(2개까지). 주어를 다시 써서 문단만 읽어도 통하게.")
    # 5. 신뢰: 공식 자료 링크
    if not OFFICIAL_LINK.search(body):
        errs.append("[신뢰] 본문에 공식 자료(정부·공공기관·청약홈·DART 등) 링크가 없습니다.")
    # 6. 내부 링크: 실제 공개된 같은 블로그 글로만, 3편 이상 공개됐으면 1개 이상
    if blog in HOSTS:
        host = HOSTS[blog][0]
        pubs = _published(blog)
        live = {str(r.get("url", "")).split("?")[0].split("#")[0] for r in pubs if r.get("status") == "LIVE" and r.get("url")}
        own = [u.split("?")[0].split("#")[0] for u in re.findall(rf"\]\((https?://{host}\.blogspot\.com/[^)\s]*)\)", body)]
        posts_links = [u for u in own if "/p/" not in u and "/search" not in u]
        dead = [u for u in posts_links if u not in live]
        if dead:
            errs.append(f"[내부 링크] 공개 목록(published.json)에 없는 주소: {dead[:2]}")
        if len(live) >= 3 and not posts_links:
            errs.append("[내부 링크] 같은 블로그 공개 글로 가는 문맥 링크가 없습니다(1~2개, published.json의 LIVE 주소, 링크 문구는 그 글의 내용으로).")
    # 7. 중복(대표 키워드·주제·구성·내용)은 sitewide.overlap_errors()가 블로그 전체 글과 비교해 막는다.
    # 8. 검색자 질문: 실제 검색어에서 뽑은 질문을 머리말에 적고 소제목에 반영
    qlist = [str(q) for q in (meta.get("questions") or [])]
    if len(qlist) < 2:
        errs.append("[검색자] 머리말 questions에 실제 검색자 질문 2개 이상(keywords 목록·검색 화면 자동완성·연관검색어에서 실제로 본 말 그대로, 지어내지 않음)을 적으세요.")
    else:
        stop = {"드론", "아파트", "청약", "전세", "관리비", "공모주", "어떻게", "얼마", "언제", "무엇"}
        words = {w for q in qlist for w in re.findall(r"[가-힣A-Za-z0-9]{2,}", q) if w not in stop}
        hit = sum(1 for h, _ in heads if any(w in h for w in words))
        if hit < 2:
            errs.append(f"[검색자] questions의 말이 소제목 {hit}개에만 들어갔습니다(2개 이상). 검색자 질문에 답하는 소제목으로.")
    return errs


def seo_warnings(meta: dict, body: str) -> list[str]:
    w: list[str] = []
    heads = _sections(body)
    paras = _paragraphs(body)
    kw = str(meta.get("keyword", "")).strip()
    title = str(meta.get("title", ""))
    if len(title) > 45:
        w.append(f"제목 {len(title)}자: 검색 결과에서 잘릴 수 있음(40자 안팎 권장)")
    if heads and not any(h.rstrip().endswith("?") or re.search(r"(나요|까|일까|인가|얼마|어디|언제|왜|무엇|몇)", h) for h, _ in heads):
        w.append("질문형 소제목 없음(AEO: 사람들이 묻는 말로 1개 이상)")
    if heads and not any(t and t in h for h, _ in heads for t in [_target(meta)]):
        w.append("소제목 어디에도 검색 대상 이름이 없음")
    # 소제목 아래 첫 문장이 답(숫자)으로 시작하는 비율
    answered = 0
    for _, sec in heads:
        p = _paragraphs(sec)
        first = _sentences(_plain(p[0]))[:1] if p else []
        if first and NUM_RE.search(first[0]):
            answered += 1
    if heads and answered / len(heads) < 0.5:
        w.append(f"소제목 아래 첫 문장에 숫자 답이 있는 비율 {answered}/{len(heads)} (절반 이상 권장)")
    sents = _sentences(_plain(" ".join(paras)))
    long = [s for s in sents if len(s) > 110]
    if sents and len(long) / len(sents) > 0.15:
        w.append(f"긴 문장(110자 넘음) {len(long)}개: AI 답변은 짧은 문장을 잘라 인용함")
    starts = [p for p in paras if PRONOUN_START.match(_plain(p))]
    if len(starts) >= 3:
        w.append(f"'이는·그래서·또한'으로 시작하는 문단 {len(starts)}개: 문단만 떼어 읽어도 뜻이 통하게(GEO)")
    if kw and body.count(kw) > 6:
        w.append(f"메인 키워드 '{kw}' {body.count(kw)}번 반복(키워드 반복은 효과 없음, 6번 이하)")
    if "|" not in body:
        w.append("표 없음(숫자 비교는 표가 검색·AI 인용에 유리)")
    srcs = CITE_RE.findall(_plain(" ".join(paras)))
    if len(srcs) < 2:
        w.append("출처 문장 1개뿐(주장마다 출처 문장, 2개 이상 권장)")
    return w


def score(meta: dict, body: str) -> int:
    return max(0, 100 - 20 * len(seo_errors(meta, body)) - 6 * len(seo_warnings(meta, body)))


def report() -> int:
    today = datetime.now(KST).date()
    lines = [f"# 검색 노출 점검: SEO·AEO·GEO ({today})", "",
             "기준: rules/seo_guide.md. '막힘'은 새 글이면 발행이 막히는 항목, '권장'은 고치면 좋은 항목.",
             "70점 미만이거나 '막힘'이 있는 공개 글은 매일 점검에서 원고를 고친다.", ""]
    for key, (name, base) in BLOGS.items():
        files = sorted((base / "posts/published").glob("*.md"))
        rows, weak = [], 0
        for f in files:
            meta, body = _split(f.read_text("utf-8"))
            e, w, s = seo_errors(meta, body), seo_warnings(meta, body), score(meta, body)
            if e or s < 70:
                weak += 1
            rows.append((s, f.name, e, w))
        lines += [f"## {name} — 공개 글 {len(files)}편, 고칠 글 {weak}편", ""]
        for s, n, e, w in sorted(rows):
            lines.append(f"- {s}점 · {n}")
            lines += [f"  - 막힘: {x}" for x in e]
            lines += [f"  - 권장: {x}" for x in w]
        lines.append("")
    (ROOT / "data/seo_report.md").write_text("\n".join(lines), "utf-8")
    print("\n".join(l for l in lines if l.startswith("## ")))
    return 0


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        return report()
    bad = 0
    for a in args:
        meta, body = _split(Path(a).read_text("utf-8"))
        e, w = seo_errors(meta, body), seo_warnings(meta, body)
        print(f"{a}: {score(meta, body)}점")
        for x in e:
            print("  막힘:", x)
        for x in w:
            print("  권장:", x)
        bad += bool(e)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
