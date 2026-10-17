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
MULTI_TYPES = ("remainder", "region", "monthly", "stats", "guide", "market")  # 여러 단지·통계: house_manage_nos
ALL_TYPES = UNIT_TYPES + MULTI_TYPES
ALLOWED_LABELS = {"청약일정", "경쟁률", "당첨가점", "무순위", "서울", "경기", "인천", "지방", "청약가이드",
                  "월간정리", "청약통계", "실거래가"}
MIN_ANALYSIS_NUMBERS = 2  # 원본에 없고 분석(data/analysis, data/stats)에만 있는 숫자가 최소 이만큼 있어야 한다
# 사람말투-글쓰기 규칙(위키피디아 'Signs of AI writing' 기반)에서 자동으로 잡을 수 있는 AI 말투
BANNED = ("주목할 점은", "중요한 것은", "눈여겨볼", "도움이 되었", "도움이 되셨", "궁금한 점", "궁금하신",
          "무조건 오른", "당첨 보장", "전문가들은", "많은 연구에 따르면", "업계에서는", "독자 여러분",
          "중요한 역할", "상징한다", "상징합니다", "전환점", "깊이 뿌리내린", "발자취", "숨 막히는", "꼭 가봐야",
          "눈부신", "다채로운", "명실상부", "밀접한 관련", "혁신적인", "심도 있게", "함양", "아우르",
          "시사합니다", "시사해요", "보여줍니다", "그럼에도 불구하고", "다양한", "살펴보겠습니다",
          "알아보겠습니다", "알아볼까요", "정리해 보겠습니다", "마무리하며", "결론적으로", "요약하자면",
          "한마디로", "놓치지 마세요", "필수 체크", "꿀팁",
          # 채움말(품질 평가 가이드 'Filler'): 어느 글에 붙여도 되는 마무리·당부
          "신중하게 결정", "신중히 결정", "꼼꼼히 따져", "꼼꼼하게 따져", "참고하시기 바랍니다", "도움이 되길",
          "도움이 되시길", "현명한 선택", "성공적인 청약", "좋은 결과 있으시길", "내 집 마련의 꿈")
CONNECTORS = ("또한", "게다가", "뿐만 아니라", "그러나", "한편", "더불어")
DISCLOSURE = "청약홈 공고 데이터를 바탕으로 정리했어요"
GUIDE_NOTICE = "청약홈 홈페이지를 참고해 주세요"
MARKET_DISCLOSURE = "국토교통부 실거래가 공개 데이터를 바탕으로 정리했어요"
# 출처 안내는 뜻만 같으면 표현을 바꿔도 된다(모든 글 끝이 똑같은 문장이 되지 않게)
DISCLOSURE_RE = re.compile(r"청약홈[^.\n]{0,20}(공고|분양정보|모집공고)[^.\n]{0,10}데이터를 바탕으로 정리했")
MARKET_DISCLOSURE_RE = re.compile(r"(국토교통부|국토부)[^.\n]{0,15}실거래[^.\n]{0,15}데이터를 바탕으로 정리했")
# 글의 중심(angle): 그 단지 데이터에서 가장 두드러진 점을 골라 첫 소제목과 글 순서를 정한다.
ANGLES = {
    "notice": ("가격", "시세", "일정", "특공", "타입"),
    "competition": ("마감단계", "타입격차", "지역비교", "미달"),
    "score": ("커트라인", "타입격차", "지역비교", "가점구간"),
}
MIN_CHARS = 1500
MAX_TITLE = 60
TITLE_KEYWORD_WITHIN = 25  # 모바일 검색 결과에서 잘리지 않는 앞부분 안에 메인 키워드
MAX_PARA_SENTENCES = 4
MAX_TABLE_COLS = 4
DONE = ROOT / "posts" / "published"
MAX_TEMPLATE_SENTENCES = 1  # 다른 글과 (숫자만 빼고) 똑같은 문장 허용 개수. 고정 안내 문구는 제외
FIXED_OK = ("바탕으로 정리했", "입주자모집공고 원문", "청약홈 홈페이지를 참고", "참고용으로만 봐 주세요")


def _sentences(body: str) -> list[str]:
    text = re.sub(r"^\s*[|#>-].*$", "", body, flags=re.M)      # 표·소제목·목록 제외
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return [x.strip() for x in re.split(r"(?<=[.!?요다])\s+", text) if len(x.strip()) >= 20]


def _norm(sent: str) -> str:
    return re.sub(r"[\d,.]+", "N", re.sub(r"\s+", " ", sent)).strip()


def template_sentences(body: str, exclude_file: str = "", limit: int = 40) -> list[str]:
    """다른 공개 글과 숫자만 다르고 똑같은 문장. 바꿔 끼울 수 있는 '틀 문장'이 쌓이면 대량 생성으로 보인다."""
    if not DONE.exists():
        return []
    seen: set[str] = set()
    for f in sorted(DONE.glob("*.md"))[-limit:]:
        if f.name == exclude_file:
            continue
        try:
            _, b = split_post(f.read_text("utf-8"))
        except Exception:  # noqa: BLE001
            continue
        seen |= {_norm(x) for x in _sentences(b)}
    out = []
    for x in _sentences(body):
        if any(k in x for k in FIXED_OK):
            continue
        if _norm(x) in seen:
            out.append(x)
    return list(dict.fromkeys(out))


PHRASE_FIXED = re.compile(r"(바탕으로 정리했|입주자모집공고 원문|계산했습니다|나눠 계산했어요|투자 판단|dart\.fss|k-apt|rt\.molit|applyhome)", re.I)
MAX_SHARED_PHRASES = 5  # 공개 글 3편 이상에 이미 나온 5어절 표현을 새 글이 이만큼 넘게 쓰면 '틀 반복'


def _phrases(text: str, n: int = 5) -> set[str]:
    keep = [l for l in text.splitlines() if not l.lstrip().startswith(("|", "#", ">")) and not PHRASE_FIXED.search(l)]
    w = re.sub(r"[\d,.%]+", "N", strip_md("\n".join(keep))).split()
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def phrase_errors(body: str, done_dir: Path, exclude_file: str = "") -> list[str]:
    """문장 전체는 달라도 같은 어절 묶음(5어절)을 여러 글에 되풀이하면 같은 틀로 찍어 낸 글처럼 읽힌다.
    공개 글 3편 이상에 나온 표현을 새 글이 MAX_SHARED_PHRASES개 넘게 쓰면 막는다."""
    if not done_dir.exists():
        return []
    count: dict[str, int] = {}
    for f in sorted(done_dir.glob("*.md"))[-60:]:
        if f.name == exclude_file:
            continue
        try:
            _, b = split_post(f.read_text("utf-8"))
        except Exception:  # noqa: BLE001
            continue
        for g in _phrases(b):
            count[g] = count.get(g, 0) + 1
    shared = [g for g in _phrases(body) if count.get(g, 0) >= 3]
    if len(shared) > MAX_SHARED_PHRASES:
        return [f"다른 글 3편 이상에 이미 나온 표현을 {len(shared)}개 썼습니다({MAX_SHARED_PHRASES}개까지). "
                f"이 대상만의 말로 바꿔 주세요: " + " / ".join(shared[:4])]
    return []


HEAD_KEYWORDS = {  # 새 블로그가 제목 키워드로 노리면 안 되는 머리 키워드(검색량 크고 대형 사이트 차지)
    "cheongyak": ["청약", "청약일정", "아파트청약", "분양일정", "아파트분양", "무순위청약", "줍줍", "청약가점", "청약경쟁률", "분양가"],
    "jeonse": ["전세", "전세가율", "전세시세", "깡통전세", "아파트전세", "전세사기", "전세보증보험", "아파트전세가율"],
    "gongmoju": ["공모주", "공모주일정", "공모주청약", "이번주공모주", "공모주수요예측", "공모주상장일정", "IPO"],
    "gwanribi": ["관리비", "아파트관리비", "관리비비교", "장기수선충당금", "관리비평균", "공용관리비", "아파트관리비평균"],
}
KEYWORD_STAGES = {1: (30, 1500), 2: (300, 5000), 3: (1000, 30000)}


def keyword_errors(blog: str, meta: dict) -> list[str]:
    """키워드 사다리(rules/keyword_ladder.md): 새 블로그는 대상(단지·지역·회사)이 들어간 구체 키워드로 시작한다."""
    kw = str(meta.get("keyword") or "")
    nk = re.sub(r"\s", "", kw).upper()
    if not kw:
        return []
    errs = []
    if nk in {h.upper() for h in HEAD_KEYWORDS.get(blog, [])}:
        errs.append(f"키워드 '{kw}'는 머리 키워드라 새 블로그가 노리기 어렵습니다. 대상 이름을 붙인 구체 키워드로 바꿔 주세요(예: '송파구 전세가율').")
    elif len(kw.split()) < 2:
        errs.append(f"키워드 '{kw}'가 한 단어입니다. 대상 + 주제어 두 단어 이상으로 써 주세요.")
    kf = ROOT / "data" / "keywords" / f"{blog}.json"
    if kf.exists():
        d = json.loads(kf.read_text("utf-8"))
        hi = (d.get("band") or [0, 1500])[1]
        hit = next((r for r in d.get("keywords", []) if re.sub(r"\s", "", r["keyword"]).upper() == nk), None)
        if hit and hit["volume"] > hi * 3:
            errs.append(f"키워드 '{kw}'는 월 {hit['volume']:,}회로 지금 단계 구간(~{hi:,})보다 훨씬 큽니다. 더 구체적인 키워드로 바꿔 주세요.")
    return errs


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


PRICE_KEYS = re.compile(r"(price|median|amount|p25|p75|diff_vs)", re.I)


def _walk_nums(x, out: set[str], key: str = "") -> None:
    if isinstance(x, dict):
        for k, v in x.items():
            _walk_nums(v, out, str(k))
    elif isinstance(x, list):
        for v in x:
            _walk_nums(v, out, key)
    elif x is not None and not isinstance(x, bool):
        out.update(_nums_from(x))
        if PRICE_KEYS.search(key) and "pct" not in key and "pyeong" not in key:
            try:
                out.update(_amount_forms(abs(int(float(x)))))  # 만원 금액 → '5억 2,000만' 같은 표기
            except (TypeError, ValueError):
                pass


def analysis_numbers(unit_nos: list[str], with_stats: bool, lawd_cds: list[str] | None = None) -> set[str]:
    """data/analysis·data/stats에서 계산한 분석 숫자"""
    out: set[str] = {"3.3"}  # '3.3㎡당' 표기
    for no in unit_nos:
        p = ANALYSIS / f"{no}.json"
        if p.exists():
            _walk_nums(json.loads(p.read_text("utf-8")), out)
    if with_stats and STATS.exists():
        _walk_nums(json.loads(STATS.read_text("utf-8")), out)
        out |= history_numbers("cheongyak")
    for lawd in lawd_cds or []:  # 실거래가 동향 글: data/market/regions/<시군구 코드>.json
        p = ROOT / "data" / "market" / "regions" / f"{lawd}.json"
        if p.exists():
            _walk_nums(json.loads(p.read_text("utf-8")), out)
    return out


def history_numbers(blog: str, keys: list[str] | None = None, prefixes: list[str] | None = None) -> set[str]:
    """data/history/<blog>_changes.json에 미리 계산된 4주·12주 변화값(우리만의 시간 기록, src/history.py).
    keys: 정확히 맞는 대상, prefixes: 앞부분이 맞는 대상(예: 시군구 코드 → 그 동들). '_all'은 늘 포함."""
    p = ROOT / "data" / "history" / f"{blog}_changes.json"
    if not p.exists():
        return set()
    ch = json.loads(p.read_text("utf-8"))
    want = set(keys or []) | {"_all"}
    out: set[str] = set()
    for ent, v in ch.items():
        if keys is None or ent in want or any(ent.startswith(x) for x in prefixes or [] if x):
            _walk_nums(v, out)
    return out


def notice_compare_errors(no: str, plain: str) -> list[str]:
    """공고 글은 공고 내용 정리에 그치지 않도록 '같은 지역 최근 분양 단지와의 평당가 비교'를 반드시 넣는다
    (rules/unique_value.md 2장). 비교 대상이 없으면 시세(실거래 중앙값) 비교로 대신한다."""
    p = ANALYSIS / f"{no}.json"
    if not p.exists():
        return []
    a = json.loads(p.read_text("utf-8"))
    rp = a.get("region_price") or {}
    text = plain.replace(",", "")
    def has(n) -> bool:
        return n is not None and re.search(rf"(?<![\d.]){re.escape(str(n))}(?![\d.])", text) is not None
    # 발행 뒤 비교 대상이 늘어 숫자가 바뀌어도 통과하도록, 비교 문장의 형태도 인정한다(숫자 자체는 따로 대조)
    if re.search(r"\d+곳 (중|가운데)[^.]{0,30}?\d+(위|번째)", plain) or \
            re.search(r"(평균|중앙값)(보다|에 비해|대비)[^.]{0,15}?\d+(\.\d+)?% ?(높|낮|비싸|싸)", plain):
        return []
    if (rp.get("peer_count") or 0) >= 2:
        if (has(rp.get("rank")) and has(rp.get("of"))) or has(rp.get("peer_avg_pyeong")) or \
                (rp.get("diff_pct") not in (None, 0) and has(abs(rp["diff_pct"]))):
            return []
        return [f"공고 글에 같은 지역 최근 분양 단지와의 평당가 비교가 없습니다 "
                f"({rp.get('scope')} {rp.get('supply_kind', '')} {rp.get('of')}곳 중 {rp.get('rank')}위, "
                f"평균 {rp.get('peer_avg_pyeong')}만 원 등 data/analysis의 region_price를 쓰세요)."]
    m = a.get("market") or {}
    if m.get("diff_pct_vs_median84") is not None:
        if has(abs(m["diff_pct_vs_median84"])) or has(m.get("median84")):
            return []
        return ["공고 글에 주변 시세(실거래 84㎡ 중앙값)와의 비교가 없습니다 (data/analysis의 market을 쓰세요)."]
    return []


SNAPSHOTS = ROOT / "data" / "snapshots"


def snapshot_path(blog: str, file_name: str) -> Path:
    """발행할 때 그 글의 숫자 근거를 얼려 둔 파일. 실거래가처럼 매일 다시 계산되는 데이터 때문에
    올린 뒤 숫자가 '데이터에 없음'으로 바뀌는 것을 막는다(글은 발행일 기준으로 맞았던 것)."""
    base = SNAPSHOTS if blog == "cheongyak" else ROOT / "blogs" / blog / "data" / "snapshots"
    return base / (Path(file_name).stem + ".json")


def snapshot_numbers(blog: str, file_name: str) -> set[str]:
    p = snapshot_path(blog, file_name) if file_name else None
    return set(json.loads(p.read_text("utf-8"))["numbers"]) if p and p.exists() else set()


def save_snapshot(blog: str, file_name: str, numbers: set[str], when: str) -> None:
    p = snapshot_path(blog, file_name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"date": when, "numbers": sorted(numbers)}, ensure_ascii=False), "utf-8")


def used_valid_numbers(body: str, allowed: set[str]) -> set[str]:
    """본문에 쓰인 숫자 중 지금 데이터로 확인되는 것만(스냅샷에 저장할 것)."""
    out = set()
    for tok in re.findall(r"\d[\d,]*(?:\.\d+)?", strip_md(body)):
        t = tok.replace(",", "")
        forms = {t}
        try:
            forms.add(str(int(float(t))))
        except ValueError:
            pass
        if forms & allowed:
            out |= forms
    return out


def allowed_set(meta: dict, body: str = "") -> set[str]:
    """청약노트 글 하나가 쓸 수 있는 숫자 전체(원본 + 분석)."""
    typ = meta.get("type")
    unit_nos = [str(x) for x in (meta.get("house_manage_nos") or
                                 ([meta["house_manage_no"]] if meta.get("house_manage_no") else []))]
    lawds = [str(x) for x in (meta.get("lawd_cds") or ([meta["lawd_cd"]] if meta.get("lawd_cd") else []))]
    return allowed_numbers(unit_nos) | analysis_numbers(unit_nos, typ in MULTI_TYPES, lawds)


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


def style_errors(body: str, min_tables: int = 2) -> list[str]:
    """모든 블로그 공통: AI 말투 구조, 표, 문장 끝 말투, 문단 길이 점검."""
    errs: list[str] = []
    # AI 말투 구조 점검
    paras = [b.strip() for b in re.split(r"\n\s*\n", body)
             if b.strip() and not b.strip().startswith(("|", "#", ">", "-", "*", "1."))]
    if paras and sentences(paras[0])[0].rstrip().endswith("?"):
        errs.append("첫 문장을 질문으로 시작하지 않습니다. 가장 구체적인 숫자·날짜로 시작해 주세요.")
    if body.count("아니라") > 1:
        errs.append(f"'~이 아니라 ~' 구조가 {body.count('아니라')}번입니다 (1번까지).")
    if body.count("**") // 2 > 2:
        errs.append(f"굵은 글씨가 {body.count('**') // 2}곳입니다 (2곳까지).")
    run = 0
    for b in paras:
        run = run + 1 if b.startswith(CONNECTORS) else 0
        if run >= 3:
            errs.append("'또한·게다가·그러나' 같은 접속사로 시작하는 문단이 3번 연속입니다.")
            break
    all_sents = [x.rstrip(" .!?\"')") for b in paras for x in sentences(b.replace("\n", " "))]
    for i in range(len(all_sents) - 2):
        tails = {x[-3:] for x in all_sents[i:i + 3]}
        if len(tails) == 1 and len(all_sents[i]) >= 3:
            errs.append(f"같은 어미('{all_sents[i][-3:]}')가 세 문장 연속입니다: '{all_sents[i][:15]}…'")
            break

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
    if tables < min_tables:
        errs.append(f"표가 {tables}개입니다 ({min_tables}개 이상).")

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

    return errs


def check_text(meta: dict, body: str, recent: list[dict] | None = None) -> list[str]:
    errs: list[str] = []
    for f in REQUIRED_FIELDS:
        if not meta.get(f):
            errs.append(f"머리말에 {f}가 없습니다.")
    typ = meta.get("type")
    if typ in ANGLES:
        if meta.get("angle") not in ANGLES[typ]:
            errs.append(f"머리말 angle은 {', '.join(ANGLES[typ])} 중 하나여야 합니다.")
        else:
            same = [r for r in (recent or []) if r.get("type") == typ][-2:]
            if len(same) == 2 and all(r.get("angle") == meta["angle"] for r in same):
                errs.append(f"같은 종류 직전 2편과 글의 중심(angle: {meta['angle']})이 같습니다. 이 단지에서 다른 점을 중심으로 써 주세요.")
    unit_nos = [str(x) for x in (meta.get("house_manage_nos") or
                                 ([meta["house_manage_no"]] if meta.get("house_manage_no") else []))]
    if typ not in ALL_TYPES:
        errs.append(f"알 수 없는 type: {typ}")
    if typ in UNIT_TYPES and not unit_nos:
        errs.append("단지 글인데 house_manage_no가 없습니다.")
    if typ in ("remainder", "region", "monthly") and not unit_nos:
        errs.append("여러 단지 글인데 house_manage_nos가 없습니다.")
    if typ == "market" and not meta.get("lawd_cd") and not meta.get("lawd_cds"):
        errs.append("실거래가 글인데 lawd_cd(시군구 코드)가 없습니다.")
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
    if typ == "market":
        if "rt.molit.go.kr" not in body:
            errs.append("실거래가 글에 국토교통부 실거래가 공개시스템 링크(rt.molit.go.kr)가 없습니다.")
    elif "applyhome.co.kr" not in body:
        errs.append("청약홈 원문 링크(applyhome.co.kr)가 없습니다.")
    if typ == "guide":
        if GUIDE_NOTICE not in body:
            errs.append("가이드 글에 '청약홈 홈페이지를 참고해 주세요' 안내가 없습니다.")
    elif typ == "market":
        if not MARKET_DISCLOSURE_RE.search(body):
            errs.append(f"실거래가 글에 '{MARKET_DISCLOSURE}' 안내가 없습니다.")
    elif not DISCLOSURE_RE.search(body):
        errs.append("출처 안내 문구('…데이터를 바탕으로 정리했어요')가 없습니다.")
    for b in BANNED:
        if b in body:
            errs.append(f"금지 표현: '{b}'")

    errs += style_errors(body)

    # 숫자 대조: 원본 데이터 또는 분석 데이터에 있는 숫자만 쓴다
    with_stats = typ in MULTI_TYPES
    raw = allowed_numbers(unit_nos)
    lawds = [str(x) for x in (meta.get("lawd_cds") or ([meta["lawd_cd"]] if meta.get("lawd_cd") else []))]
    extra = analysis_numbers(unit_nos, with_stats, lawds)
    allowed = raw | extra | snapshot_numbers("cheongyak", meta.get("_file", ""))
    analysis_only = (extra | snapshot_numbers("cheongyak", meta.get("_file", ""))) - raw
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
    if typ == "notice" and unit_nos:
        errs += notice_compare_errors(unit_nos[0], plain)
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
    errs += phrase_errors(body, DONE, meta.get("_file", ""))
    errs += keyword_errors("cheongyak", meta)
    tmpl = template_sentences(body, exclude_file=meta.get("_file", ""))
    if len(tmpl) > MAX_TEMPLATE_SENTENCES:
        errs.append(f"다른 글과 숫자만 다른 똑같은 문장이 {len(tmpl)}개입니다 ({MAX_TEMPLATE_SENTENCES}개까지). "
                    "이 단지만의 내용으로 바꿔 써 주세요: " + " / ".join(t[:30] for t in tmpl[:3]))
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
    meta["_file"] = path.name
    # 이미 올린 글을 다시 검사할 때는 자기 자신과 비교하지 않는다
    recent = [r for r in recent_posts() if r.get("file") != path.name]
    if path.parent.name == "published":
        recent = []  # 발행 순서 규칙(직전 글과 같은 시작·소제목)은 새 글에만 의미가 있다
    return check_text(meta, body, recent)


if __name__ == "__main__":
    bad = 0
    for arg in sys.argv[1:]:
        from seo import _split, seo_errors, seo_warnings
        m_, b_ = _split(Path(arg).read_text("utf-8"))
        errs = check_file(Path(arg)) + seo_errors(m_, b_)
        print(f"[{'통과' if not errs else '실패'}] {arg}")
        for e in errs:
            print("  -", e)
        for w in seo_warnings(m_, b_):
            print("  · 검색 권장:", w)
        bad += bool(errs)
    sys.exit(1 if bad else 0)
