"""블로그 전체 점검(사이트 단위). 애드센스는 글 한 편이 아니라 블로그 전체를 본다(2026-10-19 전수 점검 교훈).

글 한 편씩 보는 검수(check·seo·value)가 놓친 것을 사이트 단위로 잡는다.
  1. 뼈대 유사도: 소제목·표·문단 배치와 마무리 문단이 같은 블로그 다른 글과 거의 같은가(숫자만 바꾼 틀 글)
  2. 형식 쏠림: 최근 글이 한 종류(type)·한 라벨·한 지역에 몰렸는가(도어웨이 위험)
  3. 낡은 글: 날짜가 지난 미래형 안내, 결과·확정가·정정요구가 새로 나왔는데 반영 안 된 글
  4. 글끼리 숫자 충돌: 같은 대상의 순위를 글마다 다르게 쓰면서 기준일을 밝히지 않은 경우
  5. 데이터 이상값 사용: 1,000% 넘는 비율, 2~3곳 비교를 제목·첫 문장 핵심으로 쓴 경우
→ data/sitewide.md(사람이 읽는 보고서), data/sitewide.json(readiness·매일 점검이 읽음)

새 글 발행 때는 skeleton_errors()가 1번을, format_errors()가 2번(관리비만 막음)을 검수에 더한다.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
KST = timezone(timedelta(hours=9))
BLOGS = {"cheongyak": ("청약노트", ROOT), "jeonse": ("전세 온도계", ROOT / "blogs/jeonse"),
         "gongmoju": ("공모주 뜯어보기", ROOT / "blogs/gongmoju"), "gwanribi": ("관리비 돋보기", ROOT / "blogs/gwanribi")}

STRUCT_LIMIT = 0.80   # 블록 배치 유사도(0~1). 이 이상인 글이 최근 글 중 2편 이상이면 틀 글
CLOSE_LIMIT = 0.45    # 마무리 문단 표현 겹침(0~1)
RECENT = 8
FORMAT_SHARE = 0.75   # 최근 8편 중 같은 type 비율


def _split(text: str) -> tuple[dict, str]:
    import yaml
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    return (yaml.safe_load(m.group(1)) or {}, m.group(2)) if m else ({}, text)


def posts(blog: str) -> list[dict]:
    base = BLOGS[blog][1]
    out = []
    for f in sorted((base / "posts/published").glob("*.md")):
        meta, body = _split(f.read_text("utf-8"))
        out.append({"file": f.name, "meta": meta, "body": body, "date": f.name[:10]})
    return out


def _norm(s: str, meta: dict) -> str:
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    for w in str(meta.get("keyword", "")).split()[:1] + [str(meta.get("title", "")).split(",")[0]]:
        if w:
            s = s.replace(w, "X")
    s = re.sub(r"\d[\d,.]*", "N", s)
    return re.sub(r"\s+", " ", s).strip()


def _head_tok(h: str) -> str:
    """소제목을 대상 이름·숫자를 뺀 핵심어로: '송파구 1위와 81위 차이는?' → 'H:위와 위 차이는'."""
    h = re.sub(r"[\d,.]+", "", h)
    h = re.sub(r"[가-힣A-Za-z]+(구|시|군|동|읍|면|단지|아파트|주택)\b", "", h)
    return "H:" + " ".join(h.split()[:3])


def blocks(body: str) -> list[str]:
    out = []
    for b in re.split(r"\n\s*\n", body.strip()):
        b = b.strip()
        if not b:
            continue
        if b.startswith("## "):
            out.append(_head_tok(b[3:]))
        elif b.startswith("|"):
            out.append("T")
        elif b.startswith(">"):
            out.append("Q")
        elif re.match(r"^([-*]|\d+\.)\s", b):
            out.append("L")
        elif b.startswith("<"):
            out.append("X")
        else:
            out.append("P")
    return out


def closing(body: str, meta: dict) -> set[str]:
    paras = [b.strip() for b in re.split(r"\n\s*\n", body.strip())
             if b.strip() and not b.strip().startswith(("#", "|", ">", "<"))]
    text = _norm(" ".join(paras[-2:]), meta)
    w = text.split()
    return {" ".join(w[i:i + 4]) for i in range(len(w) - 3)}


def struct_sim(a: list[str], b: list[str]) -> float:
    return SequenceMatcher(None, a, b).ratio()


def jacc(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def skeleton_errors(blog: str, meta: dict, body: str, file_name: str = "") -> list[str]:
    """새 글 검수용: 최근 같은 블로그 글과 뼈대·마무리가 거의 같으면 막는다."""
    allp = posts(blog)
    if file_name and any(p["file"] == file_name for p in allp):  # 이미 올린 글은 그보다 앞선 글하고만 비교
        allp = [p for p in allp if p["file"] < file_name]
    others = [p for p in allp if p["file"] != file_name][-RECENT:]
    if len(others) < 3:
        return []
    bs, cl = blocks(body), closing(body, meta)
    same = [p["file"] for p in others if struct_sim(bs, blocks(p["body"])) >= STRUCT_LIMIT]
    close = [(p["file"], round(jacc(cl, closing(p["body"], p["meta"])), 2)) for p in others]
    close = [x for x in close if x[1] >= CLOSE_LIMIT]
    errs = []
    if len(same) >= 2:
        errs.append(f"[전체] 소제목·표·문단 배치가 최근 글 {len(same)}편과 거의 같습니다({', '.join(same[:3])}). "
                    "이 대상에서 두드러진 점에 맞게 순서와 구성을 바꾸세요(숫자만 바꾼 틀 글로 보입니다).")
    if close:
        errs.append(f"[전체] 마무리 문단이 {close[0][0]}와 거의 같습니다(겹침 {close[0][1]}). 이 글의 중심과 관련된 다른 마무리로 쓰세요.")
    return errs


def format_errors(blog: str, meta: dict, file_name: str = "") -> list[str]:
    """형식 쏠림: 관리비는 주제·단지 글을 언제든 쓸 수 있으므로 막는다. 다른 블로그는 보고서로만 알린다."""
    if blog != "gwanribi":
        return []
    recent = [p for p in posts(blog) if p["file"] != file_name][-RECENT:]
    if len(recent) < 4:
        return []
    share = sum(p["meta"].get("type") == meta.get("type") for p in recent) / len(recent)
    if share >= FORMAT_SHARE:
        return [f"[전체] 최근 {len(recent)}편 중 {round(share * 100)}%가 '{meta.get('type')}' 글입니다. "
                "주제 글(topic)이나 단지 글(complex)을 쓰세요(같은 형식 반복은 도어웨이로 읽힙니다)."]
    return []


# ---- 낡은 글 ----
FUTURE_RE = re.compile(r"(\d{1,2})월 (\d{1,2})일[^.\n]{0,40}?(접수|청약|발표|납입|상장|계약)[^.\n]{0,15}?(예정|해요|합니다|받아요|받습니다|이에요|입니다|시작|열려|열립니다|나와요|나옵니다)")


def stale(blog: str, p: dict, today: date) -> list[str]:
    out = []
    body = p["body"]
    year = int(p["date"][:4])
    for m in FUTURE_RE.finditer(body):
        try:
            d = date(year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            continue
        if d < today - timedelta(days=1) and d >= date.fromisoformat(p["date"]):
            out.append(f"지난 날짜를 앞으로의 일처럼 씀: '{m.group(0)[:40]}'")
            break
    meta = p["meta"]
    if blog == "cheongyak" and meta.get("type") == "notice":
        u = ROOT / "data/units" / f"{meta.get('house_manage_no')}.json"
        if u.exists() and json.loads(u.read_text("utf-8")).get("competition") and "경쟁률" not in body:
            out.append("경쟁률 결과가 나왔는데 본문에 결과 언급이 없음(결과 표는 코드가 붙이지만 본문 안내가 어긋날 수 있음)")
    if blog == "gongmoju":
        f = ROOT / "blogs/gongmoju/data/ipos" / f"{meta.get('corp_code')}.json"
        if f.exists():
            d = json.loads(f.read_text("utf-8"))
            if d.get("price_confirmed") and re.search(r"(확정하지 않|아직 확정|확정 전)", body):
                out.append("공모가가 확정됐는데 '아직 확정 전'으로 씀")
            if d.get("correction_requested") and "정정" not in body:
                out.append("정정제출요구 상태인데 본문에 언급이 없음")
    return out


# ---- 글끼리 숫자 충돌: 기준 없는 순위 ----
def conflicts(blog: str, ps: list[dict]) -> list[str]:
    """순위를 쓰면서 기준(집계일·공고일 이전)을 밝히지 않은 글. 데이터가 매일 바뀌어 글끼리 모순으로 읽힌다."""
    from seo import BASIS_RE, RANK_RE
    return [f"{p['file']}: 순위를 쓰면서 기준일이 없음" for p in ps if RANK_RE.search(p["body"]) and not BASIS_RE.search(p["body"])]


PLACES = {"서울", "경기", "인천", "부산", "대구", "광주", "대전", "울산", "세종", "강원", "충북", "충남", "전북", "전남",
          "경북", "경남", "제주", "지방", "수도권"}


# ---- 데이터 이상값 사용 ----
def anomalies(p: dict) -> list[str]:
    out = []
    body = p["body"]
    for m in re.finditer(r"(\d{1,3}(,\d{3})+|\d{4,})(\.\d+)?\s*%", body):
        out.append(f"1,000% 넘는 비율: {m.group(0)} (기준값이 작은 항목은 금액 두 개로)")
        break
    title = str(p["meta"].get("title", ""))
    first = re.split(r"(?<=[.?!다요])\s+", re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", body).strip())[0] if body.strip() else ""
    for where, txt in (("제목", title), ("첫 문장", first)):
        if re.search(r"\b[23]\s*곳\s*(중|가운데)", txt):
            out.append(f"{where}에 2~3곳 비교를 핵심으로 씀: '{txt[:40]}'")
    return out


def run() -> dict:
    today = datetime.now(KST).date()
    report: dict = {"date": today.isoformat(), "blogs": {}}
    lines = [f"# 블로그 전체 점검 ({today})", "",
             "애드센스는 블로그 전체를 본다. 글 한 편씩 보는 검수가 놓치는 사이트 단위 문제를 모았다. "
             "'고칠 것'이 있으면 매일 점검(10:37)이 고친다. 기준: src/sitewide.py 머리말.", ""]
    for key, (name, _) in BLOGS.items():
        ps = posts(key)
        r: dict = {"posts": len(ps)}
        # 1. 뼈대
        pairs = []
        for i in range(len(ps)):
            for j in range(i + 1, len(ps)):
                s = struct_sim(blocks(ps[i]["body"]), blocks(ps[j]["body"]))
                c = jacc(closing(ps[i]["body"], ps[i]["meta"]), closing(ps[j]["body"], ps[j]["meta"]))
                if s >= STRUCT_LIMIT or c >= CLOSE_LIMIT:
                    pairs.append((ps[i]["file"], ps[j]["file"], round(s, 2), round(c, 2)))
        r["skeleton_pairs"] = pairs
        # 2. 형식 쏠림
        recent = ps[-RECENT:]
        types = Counter(p["meta"].get("type") for p in recent)
        labels = Counter(l for p in ps for l in (p["meta"].get("labels") or []))
        top_type, top_n = (types.most_common(1)[0] if types else ("-", 0))
        r["type_share"] = {k: v for k, v in types.items()}
        r["format_concentrated"] = bool(recent) and top_n / len(recent) >= FORMAT_SHARE
        # 3~5
        r["stale"] = {p["file"]: s for p in ps if (s := stale(key, p, today))}
        r["conflicts"] = conflicts(key, ps)
        r["anomalies"] = {p["file"]: a for p in ps if (a := anomalies(p))}
        n_fix = len(pairs) + len(r["stale"]) + len(r["conflicts"]) + len(r["anomalies"])
        r["to_fix"] = n_fix
        report["blogs"][key] = r
        lines += [f"## {name} — 공개 글 {len(ps)}편, 고칠 것 {n_fix}건", ""]
        lines.append(f"- 최근 {len(recent)}편 형식: " + ", ".join(f"{k} {v}편" for k, v in types.most_common())
                     + (" → **한 형식에 쏠림(도어웨이 위험), 다른 형식 글 필요**" if r["format_concentrated"] else ""))
        lines.append("- 라벨: " + ", ".join(f"{k} {v}" for k, v in labels.most_common()))
        for a, b, s, c in pairs[:12]:
            lines.append(f"- 틀 반복: {a} ↔ {b} (배치 {s}, 마무리 {c})")
        for f, s in r["stale"].items():
            lines += [f"- 낡은 글 {f}: {x}" for x in s]
        lines += [f"- 숫자 충돌: {x}" for x in r["conflicts"]]
        for f, a in r["anomalies"].items():
            lines += [f"- 이상값 {f}: {x}" for x in a]
        lines.append("")
    (ROOT / "data/sitewide.md").write_text("\n".join(lines), "utf-8")
    (ROOT / "data/sitewide.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), "utf-8")
    print("\n".join(l for l in lines if l.startswith("## ") or "쏠림" in l))
    return report


if __name__ == "__main__":
    run()
