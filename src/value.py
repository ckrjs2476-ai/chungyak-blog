"""'가치가 별로 없는 콘텐츠'(애드센스 거절 사유 1위) 대비 매일 분석.

1) 공개 글 가치 점검(--report): 글마다 가치 신호를 재고 약한 글과 이유를 적는다.
   - 분석 문장 비율: 비교·순위·차이 숫자가 든 문장 / 전체 문장
   - 해설 문단 수: 조건·의미를 풀어 주는 문단(~라면, ~면, 경우, 뜻 등)
   - 일반 문장 비율: 숫자도 고유명사도 없어 다른 글에 그대로 옮겨도 되는 문장(채움말 후보)
   - 뼈대 겹침: 같은 블로그 다른 글과 소제목 구성(숫자·이름 뺀 모양)이 얼마나 같은지
   - 반복 표현: 여러 글에 되풀이되는 어절 묶음(5어절)
   - 부풀린 비율 표현: '두 배, 세 배, 절반' 등 말로 쓴 배수(데이터와 맞는지 사람이 확인)
2) 오늘 글감 분석(--brief): 블로그마다 아직 안 쓴 후보의 '이 대상만의 숫자'(중앙값·평균에서 멀리 떨어진 값)를 뽑아
   가치가 큰 순서로 늘어놓고, 최근 글에서 많이 쓴 뼈대·표현을 '오늘 피할 것'으로 적는다.
사용: python src/value.py            → 두 가지 모두, 4개 블로그
      python src/value.py --blog jeonse --brief
결과: data/value_report.md, <블로그 data>/value_brief.md
"""
from __future__ import annotations

import importlib
import json
import re
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import check as core  # noqa: E402

KST = timezone(timedelta(hours=9))
BLOGS = ("cheongyak", "jeonse", "gongmoju", "gwanribi")
NAMES = {"cheongyak": "청약노트", "jeonse": "전세 온도계", "gongmoju": "공모주 뜯어보기", "gwanribi": "관리비 돋보기"}
COMPARE = re.compile(r"(보다|대비|중앙값|평균|순위|\d+\s*위|차이|높|낮|많|적|배|%p?|격차|비교|커트라인|이상|이하|중 \d)")
EXPLAIN = re.compile(r"(라면|다면|이라면|으면|경우|뜻|의미|이유|때문|셈|할 수 있|될 수 있|볼 수 있|가능성|확인해|살펴|따져)")
MULT_WORDS = re.compile(r"(두 배|세 배|네 배|다섯 배|열 배|절반|반값|반토막|곱절)")


def base(blog: str) -> Path:
    return ROOT if blog == "cheongyak" else ROOT / "blogs" / blog


def data_dir(blog: str) -> Path:
    return ROOT / "data" if blog == "cheongyak" else base(blog) / "data"


def posts(blog: str) -> list[tuple[dict, dict, str]]:
    pub = data_dir(blog) / "published.json"
    rows = json.loads(pub.read_text("utf-8")).get("posts", []) if pub.exists() else []
    out = []
    for p in rows:
        f = base(blog) / "posts" / "published" / (p.get("file") or "")
        if p.get("file") and f.exists() and p.get("status", "LIVE") == "LIVE":
            meta, body = core.split_post(f.read_text("utf-8"))
            out.append((p, meta, body))
    return out


def paragraphs(body: str) -> list[str]:
    return [b.strip() for b in re.split(r"\n\s*\n", body)
            if b.strip() and not b.strip().startswith(("|", "#", ">"))]


def sents(body: str) -> list[str]:
    return [s for b in paragraphs(body) for s in core.sentences(b.replace("\n", " ")) if len(s.strip()) > 8]


def heads(body: str) -> list[str]:
    return [re.sub(r"[\d,.]+", "N", h.strip("# ").strip()) for h in body.splitlines() if h.startswith("## ")]


def head_shape(h: str) -> str:
    """소제목에서 숫자·고유명사를 뺀 모양: 끝말과 질문 여부 정도만 남긴다."""
    h = re.sub(r"N", "", h)
    tail = re.sub(r"\s+", " ", h).strip()[-6:]
    return ("Q:" if h.rstrip().endswith("?") else "S:") + tail


FIXED = re.compile(r"(바탕으로 정리했|입주자모집공고 원문|계산했습니다|나눠 계산했어요|투자 판단|dart\.fss|k-apt|rt\.molit|applyhome)", re.I)


def ngrams(text: str, n: int = 5) -> set[str]:
    """본문 문장의 5어절 묶음. 표와 고정 안내 문구(출처·확인 안내)는 뺀다."""
    keep = [l for l in text.splitlines() if not l.lstrip().startswith(("|", "#")) and not FIXED.search(l)]
    w = re.sub(r"[\d,.%]+", "N", core.strip_md("\n".join(keep))).split()
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def entity_words(meta: dict) -> set[str]:
    words = set()
    for k in ("title", "keyword"):
        for w in re.split(r"[\s,·()]+", str(meta.get(k, ""))):
            w = re.sub(r"(의|은|는|이|가|을|를|에서|으로|로)$", "", w)
            if len(w) >= 2 and not re.search(r"\d", w):
                words.add(w)
    return words


def analyze_post(meta: dict, body: str) -> dict:
    ss = sents(body)
    ents = entity_words(meta)
    comp = [s for s in ss if re.search(r"\d", s) and COMPARE.search(s)]
    generic = [s for s in ss if not re.search(r"\d", s) and not any(e in s for e in ents)]
    expl = [p for p in paragraphs(body) if EXPLAIN.search(p) and len(core.sentences(p)) >= 2]
    tables = sum(1 for i, l in enumerate(body.splitlines()) if l.startswith("|") and (i == 0 or not body.splitlines()[i - 1].startswith("|")))
    return {"sents": len(ss), "compare_ratio": round(len(comp) / max(1, len(ss)), 2),
            "generic_ratio": round(len(generic) / max(1, len(ss)), 2), "generic_examples": [g[:50] for g in generic[:3]],
            "explain_paras": len(expl), "tables": tables, "heads": heads(body),
            "mult_words": sorted(set(MULT_WORDS.findall(body))), "ngrams": ngrams(body)}


def report_blog(blog: str) -> tuple[list[str], dict]:
    ps = posts(blog)
    stats = {p["file"]: analyze_post(m, b) for p, m, b in ps}
    gram_count: Counter = Counter()
    for s in stats.values():
        gram_count.update(s["ngrams"])
    shared = {g for g, c in gram_count.items() if c >= 3}
    shape_count: Counter = Counter(tuple(head_shape(h) for h in s["heads"]) for s in stats.values())
    rows, weak = [], []
    for p, meta, body in ps:
        s = stats[p["file"]]
        reasons = []
        if s["compare_ratio"] < 0.35:
            reasons.append(f"비교·분석 문장 {int(s['compare_ratio'] * 100)}% (35% 이상 권장)")
        if s["explain_paras"] < 1:
            reasons.append("해설 문단 없음")
        if s["generic_ratio"] > 0.25:
            reasons.append(f"일반 문장 {int(s['generic_ratio'] * 100)}% (예: {s['generic_examples'][0] if s['generic_examples'] else ''})")
        rep = len(s["ngrams"] & shared)
        if rep >= 8:
            reasons.append(f"3편 이상에 반복되는 표현 {rep}개")
        if shape_count[tuple(head_shape(h) for h in s["heads"])] >= 3 and s["heads"]:
            reasons.append("소제목 뼈대가 다른 글 2편 이상과 같음")
        if s["mult_words"]:
            reasons.append(f"말로 쓴 배수 '{', '.join(s['mult_words'])}' → 데이터 비율과 맞는지 확인")
        score = 100 - 15 * len(reasons)
        # 2026-10-19 전수 점검으로 맞춘 기준: 검토자가 '위험'으로 본 글의 공통점(무거운 감점)
        import seo as _seo
        import sitewide as _sw
        lead = _seo._plain(" ".join(_seo._paragraphs(body)[:2]))
        heavy = []
        if not _seo.COMPARE_RE.search(lead):
            heavy.append(("첫 두 문단에 비교 없음(공고·결과 옮기기로 시작)", 30))
        if _seo.ADVICE_RE.search(_seo._plain(body)):
            heavy.append(("행동 권유 표현", 25))
        if _seo.RANK_RE.search(body) and not _seo.BASIS_RE.search(body):
            heavy.append(("순위 기준일 없음", 20))
        if _sw.skeleton_errors(blog, meta, body, p["file"]):
            heavy.append(("앞선 글과 뼈대·마무리가 거의 같음", 20))
        st = _sw.stale(blog, {"file": p["file"], "meta": meta, "body": body, "date": p["file"][:10]}, date.today())
        if st:
            heavy.append(("낡은 내용: " + st[0], 20))
        reasons += [r for r, _ in heavy]
        score -= sum(w for _, w in heavy)
        score = max(0, score)
        rows.append((score, p.get("title", "")[:34], p["file"], reasons, s))
        if score < 70:
            weak.append(p["file"])
    rows.sort(key=lambda r: r[0])
    top_grams = [(c, g) for g, c in gram_count.most_common(12) if c >= 3]
    lines = [f"## {NAMES[blog]} — 공개 글 {len(ps)}편, 가치 약한 글 {len(weak)}편", ""]
    if rows:
        lines += ["| 점수 | 글 | 분석 문장 | 해설 문단 | 일반 문장 | 걸린 것 |", "| --- | --- | --- | --- | --- | --- |"]
        for sc, t, fn, rs, s in rows:
            lines.append(f"| {sc} | {t} `{fn}` | {int(s['compare_ratio'] * 100)}% | {s['explain_paras']} | "
                         f"{int(s['generic_ratio'] * 100)}% | {'; '.join(rs) or '-'} |")
    if top_grams:
        lines += ["", "여러 글에 반복되는 표현(3편 이상):"] + [f"- {c}편: {g}" for c, g in top_grams]
    lines.append("")
    return lines, {"weak": weak, "shared_grams": [g for _, g in top_grams], "stats": stats}


# ---------- 오늘 글감 분석: 블로그마다 '이 대상만의 숫자' 뽑기 ----------

def _written(blog: str, key: str, typ: str | None = None) -> set[str]:
    """이미 올렸거나 올릴 예정인 글의 대상(원고 머리말 기준). typ을 주면 그 종류 글만."""
    out = set()
    for d in ("published", "pending"):
        folder = base(blog) / "posts" / d
        for f in folder.glob("*.md") if folder.exists() else []:
            m, _ = core.split_post(f.read_text("utf-8"))
            if typ is None or m.get("type") == typ:
                out.add(str(m.get(key) or ""))
    return out


def cand_jeonse() -> list[dict]:
    done = _written("jeonse", "lawd")
    rk = data_dir("jeonse") / "ranking.json"
    out = []
    for f in sorted((data_dir("jeonse") / "regions").glob("*.json")):
        r = json.loads(f.read_text("utf-8"))
        if r.get("empty") or not r.get("ratio84") or r["lawd"] in done:
            continue
        if (r.get("jeonse_n84") or 0) < 20 or (r.get("sale_n84") or 0) < 20:
            continue
        facts = []
        if r.get("rank") and r.get("rank_of"):
            q = r["rank"] / r["rank_of"]
            if q <= 0.2 or q >= 0.8:
                facts.append(f"전세가율 순위 {r['rank_of']}곳 중 {r['rank']}위")
        if r.get("ratio84") and (r["ratio84"] >= 70 or r["ratio84"] <= 45):
            facts.append(f"전세가율 {r['ratio84']}%")
        if r.get("jeonse_change_pct") is not None and abs(r["jeonse_change_pct"]) >= 3:
            facts.append(f"최근 3개월 전세 변화 {r['jeonse_change_pct']:+}%")
        if r.get("umd_spread_pp") and r["umd_spread_pp"] >= 15:
            facts.append(f"동별 전세가율 차이 {r['umd_spread_pp']}%p")
        if r.get("ratio_vs_avg_pp") is not None and abs(r["ratio_vs_avg_pp"]) >= 8:
            facts.append(f"전국 평균과 {r['ratio_vs_avg_pp']:+}%p")
        out.append({"id": r["lawd"], "name": r["name"], "facts": facts, "size": r.get("jeonse_n84") or 0})
    return out


def cand_gongmoju() -> list[dict]:
    done = _written("gongmoju", "corp_code")
    today = date.today()
    out = []
    for f in sorted((data_dir("gongmoju") / "ipos").glob("*.json")):
        d = json.loads(f.read_text("utf-8"))
        if d.get("is_spac") or d["corp_code"] in done:
            continue
        m = re.search(r"(\d{4})년 (\d{2})월 (\d{2})일", str(d.get("subscription") or ""))
        if not m or date(int(m[1]), int(m[2]), int(m[3])) < today:
            continue
        facts = []
        if d.get("total_vs_median_pct") is not None and abs(d["total_vs_median_pct"]) >= 50:
            facts.append(f"공모 규모가 비슷한 공모 중앙값과 {d['total_vs_median_pct']:+}%")
        if d.get("total_rank") and d.get("total_rank_of"):
            facts.append(f"최근 공모 {d['total_rank_of']}곳 중 규모 {d['total_rank']}위")
        if d.get("underwriting_fee_pct") and d.get("median_fee_pct"):
            if abs(d["underwriting_fee_pct"] - d["median_fee_pct"]) >= 0.5:
                facts.append(f"인수수수료율 {d['underwriting_fee_pct']}% (중앙값 {d['median_fee_pct']}%)")
        if d.get("fund_matches_total") is False:
            facts.append("자금 사용 계획 합계가 공모 총액과 다름")
        t = d.get("top_fund_use")
        if isinstance(t, dict) and t.get("share_pct") and t["share_pct"] >= 60:
            facts.append(f"자금의 {t['share_pct']}%가 {t['use']}")
        if d.get("company_age_years") is not None and (d["company_age_years"] <= 5 or d["company_age_years"] >= 25):
            facts.append(f"설립 {d['company_age_years']}년 차")
        if (d.get("sellers") or []) and d.get("sell_shares"):
            facts.append("구주 매출 있음")
        out.append({"id": d["corp_code"], "name": d["corp_name"], "facts": facts, "size": d.get("total_eok") or 0,
                    "when": f"{m[1]}-{m[2]}-{m[3]}"})
    return sorted(out, key=lambda x: x["when"])


def cand_gwanribi() -> list[dict]:
    done = _written("gwanribi", "kapt") | {""}
    done_l = _written("gwanribi", "lawd", "region")
    out = []
    for f in sorted((data_dir("gwanribi") / "regions").glob("*.json")):
        d = json.loads(f.read_text("utf-8"))
        if d.get("empty"):
            continue
        if d["lawd"] not in done_l:
            facts = [f"㎡당 중앙값 {d['median']['total_m2']:,}원, {d['n_complex']}개 단지"]
            if d.get("total_m2_ratio_high_low"):
                facts.append(f"최고·최저 단지 {d['total_m2_ratio_high_low']}배 (임대 단지 표시 {d.get('n_indiv_incomplete', 0)}곳 주의)")
            out.append({"id": "region:" + d["lawd"], "name": d["name"] + " 지역 글", "facts": facts, "size": 10 ** 6})
        for c in d["complexes"]:
            if c["code"] in done:
                continue
            facts = []
            if c.get("total_m2_vs_median_pct") is not None and abs(c["total_m2_vs_median_pct"]) >= 15 and not c.get("indiv_incomplete"):
                facts.append(f"㎡당 관리비 중앙값 대비 {c['total_m2_vs_median_pct']:+}% ({c['rank_total_m2_of']}곳 중 {c['rank_total_m2']}위)")
            med_items = d.get("item_median_m2") or {}
            big = sorted(((k, v) for k, v in (c.get("items_vs_median_pct") or {}).items()
                          if v is not None and abs(v) >= 50 and (med_items.get(k) or 0) >= 20 and v > -100),
                         key=lambda x: -abs(x[1]))[:2]
            facts += [f"{k} 중앙값 대비 {v:+}%" for k, v in big]
            if c.get("common_m2_vs_size_median_pct") is not None and abs(c["common_m2_vs_size_median_pct"]) >= 20:
                facts.append(f"같은 규모 단지보다 공용관리비 {c['common_m2_vs_size_median_pct']:+}%")
            if c.get("rank_ltsm_m2") and c.get("rank_ltsm_m2_of"):
                q = c["rank_ltsm_m2"] / c["rank_ltsm_m2_of"]
                if q <= 0.1 or q >= 0.9:
                    facts.append(f"장기수선충당금 ㎡당 {c['rank_ltsm_m2_of']}곳 중 {c['rank_ltsm_m2']}위")
            if c.get("indiv_incomplete"):
                facts.append("주의: 개별사용료 일부 별도 징수 가능(총액 비교 금지)")
            out.append({"id": c["code"], "name": f"{c['name']} ({d['name'].split()[-1]}, {c['households']}세대)",
                        "facts": facts, "size": c["households"]})
    return out


def cand_cheongyak() -> list[dict]:
    jobs = json.loads((ROOT / "data" / "jobs.json").read_text("utf-8")).get("jobs", []) if (ROOT / "data" / "jobs.json").exists() else []
    out = []
    for j in jobs:
        no = j["house_manage_no"]
        a = ROOT / "data" / "analysis" / f"{no}.json"
        an = json.loads(a.read_text("utf-8")) if a.exists() else {}
        facts = []
        rp = an.get("region_price") or {}
        if rp.get("diff_pct") is not None and abs(rp["diff_pct"]) >= 10:
            facts.append(f"평당 분양가가 지역 최근 공고 {rp.get('peer_count')}곳 평균과 {rp['diff_pct']:+}%")
        mk = an.get("market") or {}
        if mk.get("diff_pct_vs_new_median84") is not None:
            facts.append(f"84㎡ 최고가가 주변 신축 실거래 중앙값과 {mk['diff_pct_vs_new_median84']:+}%")
        cp = an.get("competition") or {}
        for k in ("rank1_rate", "overall_rate"):
            if cp.get(k) is not None:
                facts.append(f"경쟁률 {cp[k]}대 1")
                break
        out.append({"id": no, "name": f"{j['name']} ({j['type']})", "facts": facts, "size": j.get("priority", 0)})
    return out


CANDS = {"jeonse": cand_jeonse, "gongmoju": cand_gongmoju, "gwanribi": cand_gwanribi, "cheongyak": cand_cheongyak}


def brief_blog(blog: str, rep: dict) -> list[str]:
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    cands = CANDS[blog]()
    for c in cands:
        c["value"] = len([f for f in c["facts"] if not f.startswith("주의")])
    ranked = sorted(cands, key=lambda c: (-c["value"], -c["size"]))
    ps = posts(blog)
    recent = ps[-6:]
    lines = [f"# {NAMES[blog]} 오늘 글감 분석 ({now} KST)", "",
             "애드센스 거절 사유 1위 '가치가 별로 없는 콘텐츠'를 피하려고, 글을 쓰기 전에 매번 이 파일을 먼저 본다.",
             "원칙: 이 대상만의 숫자(아래 '두드러진 점')가 2개 이상인 글감만 쓴다. 0~1개면 쓰지 않거나 모음 글로 묶는다.", "",
             "## 1. 가치가 큰 글감 순서 (아직 안 쓴 것)", ""]
    if ranked:
        lines += ["| 순서 | 글감 | 두드러진 점(글의 중심 후보) | 판단 |", "| --- | --- | --- | --- |"]
        for i, c in enumerate(ranked[:12], 1):
            verdict = "쓸 만함" if c["value"] >= 2 else ("모음 글로" if c["value"] == 1 else "쓰지 않음")
            lines.append(f"| {i} | {c['name']} `{c['id']}` | {'; '.join(c['facts']) or '-'} | {verdict} |")
        thin = sum(1 for c in cands if c["value"] < 2)
        lines += ["", f"- 후보 {len(cands)}개 중 두드러진 점 2개 이상: {len(cands) - thin}개. 나머지 {thin}개는 단독 글로 쓰면 얇아질 위험."]
    else:
        lines.append("- 쓸 후보가 없다. 오늘은 쓰지 않고 이유만 남긴다.")
    lines += ["", "## 2. 오늘 피할 것 (최근 글과 같아 보이면 '틀 반복'으로 읽힌다)", ""]
    if recent:
        lines.append("- 최근 글의 시작 방식(opening)·중심(angle): " +
                     ", ".join(f"{m.get('opening', '-')}/{m.get('angle', '-')}" for _, m, _ in recent))
        last_heads = [h for _, _, b in recent[-3:] for h in heads(b)]
        lines.append("- 최근 3편 소제목(이와 비슷한 소제목·순서 금지): " + " / ".join(last_heads[:15]))
    if rep.get("shared_grams"):
        lines.append("- 여러 글에 반복되는 표현(쓰지 말 것): " + " / ".join(rep["shared_grams"][:8]))
    lines += ["", "## 3. 가치를 더하는 방법 (글마다 최소 2개)", "",
              "- 두드러진 점 하나를 글의 중심으로 삼고, 소제목 1개를 통째로 그 숫자의 의미 해설에 쓴다.",
              "- 비교 대상을 2개 이상 둔다(지역 중앙값 + 같은 규모/같은 방식/같은 시기 등). 비교 없는 숫자 나열 금지.",
              "- 독자 조건별 해설 1문단: '~라면 ~부터 확인' 식으로 상황을 나눈다(권유·판정 없이).",
              "- 원자료 사이트에서 바로 보이는 값(일정, 원래 가격)은 표 1개 안에 몰고, 본문은 계산·비교에 쓴다.",
              "- 다 쓴 뒤 숫자도 이름도 없는 문장을 찾아 지우거나, 이 대상의 숫자를 넣어 고친다.", ""]
    return lines


def main() -> int:
    only = sys.argv[sys.argv.index("--blog") + 1] if "--blog" in sys.argv else None
    want_report = "--brief" not in sys.argv or "--report" in sys.argv
    want_brief = "--report" not in sys.argv or "--brief" in sys.argv
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    out = [f"# '가치가 별로 없는 콘텐츠' 공개 글 점검 ({now} KST)", "",
           "점수 70 미만이 고칠 대상. 기준: 분석 문장 35% 이상, 해설 문단 1개 이상, 일반 문장 25% 이하, 반복 표현·뼈대 적게.", ""]
    for b in BLOGS:
        if only and b != only:
            continue
        lines, rep = report_blog(b)
        out += lines
        if want_brief:
            br = brief_blog(b, rep)
            (data_dir(b) / "value_brief.md").write_text("\n".join(br), "utf-8")
            print(f"{NAMES[b]}: 글감 분석 저장")
    if want_report and not only:
        (ROOT / "data" / "value_report.md").write_text("\n".join(out), "utf-8")
        print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
