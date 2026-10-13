"""애드센스 기준 점검. 공개 글 전체를 보고 약한 글·겹치는 글·얇은 라벨·틀 문장을 찾아 audit.md로 남긴다.
사용: BLOG_KEY=<cheongyak|jeonse|gongmoju|gwanribi> python src/audit.py   (BLOG_KEY가 없으면 청약노트)
결과: 청약노트 data/audit.md, 다른 블로그 blogs/<key>/data/audit.md
기준(rules/adsense_approval.md): 라벨마다 8편 이상, 글마다 분석 숫자·해설·내부 링크, 틀 문장 최소, 같은 주제 중복 없음.
"""
from __future__ import annotations

import importlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import check as core  # noqa: E402

BLOG = os.environ.get("BLOG_KEY", "cheongyak")
DOMAINS = {"cheongyak": "daily-cheongyak", "jeonse": "jeonse-ondogye", "gongmoju": "gongmoju-breakdown",
           "gwanribi": "gwanribi-dotbogi"}
UNIT_KEYS = {"cheongyak": "house_manage_no", "jeonse": "lawd", "gongmoju": "corp_code", "gwanribi": "kapt"}
if BLOG == "cheongyak":
    mod = core
    OUT = ROOT / "data" / "audit.md"
else:
    sys.path.insert(0, str(ROOT / "blogs" / BLOG))
    mod = importlib.import_module("blog")
    OUT = ROOT / "blogs" / BLOG / "data" / "audit.md"
DONE, PUBLISHED = mod.DONE, mod.PUBLISHED
KST = timezone(timedelta(hours=9))
MIN_PER_LABEL = 8
OVERLAP = 0.30  # 두 글의 문장(숫자 무시) 겹침 비율이 이 이상이면 합치기 후보


def main() -> int:
    posts = json.loads(PUBLISHED.read_text("utf-8"))["posts"] if PUBLISHED.exists() else []
    live = [p for p in posts if p.get("status", "LIVE") == "LIVE" and p.get("file")]
    labels = Counter(l for p in live for l in p.get("labels", []))
    docs: dict[str, tuple[dict, str, set[str]]] = {}
    sent_count: Counter = Counter()
    for p in live:
        f = DONE / p["file"]
        if not f.exists():
            continue
        meta, body = mod.split_post(f.read_text("utf-8"))
        ss = {core._norm(x) for x in core._sentences(body) if len(core._norm(x)) >= 12}
        docs[p["file"]] = (meta, body, ss)
        sent_count.update(ss)
    total = sum(sent_count.values()) or 1
    dup = sum(c for c in sent_count.values() if c > 1)

    # 겹치는 글: 같은 대상(단지·지역·회사)+같은 종류, 또는 문장 겹침이 큰 쌍
    pairs = []
    files = list(docs)
    by_unit = defaultdict(list)
    for fn in files:
        meta = docs[fn][0]
        u = str(meta.get(UNIT_KEYS[BLOG]) or meta.get("lawd") or "")
        if u:
            by_unit[(u, meta.get("type"))].append(fn)
    for (u, t), fs in by_unit.items():
        if len(fs) > 1:
            pairs.append((1.0, fs[0], fs[1], f"같은 대상({u})·같은 종류({t})"))
    for i, a in enumerate(files):
        for b in files[i + 1:]:
            sa, sb = docs[a][2], docs[b][2]
            if sa and sb:
                r = len(sa & sb) / min(len(sa), len(sb))
                if r >= OVERLAP:
                    pairs.append((round(r, 2), a, b, f"문장 {int(r * 100)}% 겹침"))
    pairs.sort(reverse=True)

    rows, weak = [], []
    titles = {p["file"]: p.get("title", p["file"]) for p in live}
    urls = {p["file"]: p.get("url", "") for p in live}
    for fn, (meta, body, _) in docs.items():
        meta = dict(meta, _file=fn)
        try:
            errs = mod.check_text(meta, body, [])
        except Exception as e:  # noqa: BLE001  (데이터 파일이 바뀌어 검수가 못 도는 경우도 기록)
            errs = [f"검수 실행 실패: {type(e).__name__}"]
        errs = [e for e in errs if "직전" not in e]  # 순서 규칙은 발행 때만 의미가 있다
        tmpl = mod.template_sentences(body, exclude_file=fn)
        chars = len(re.sub(r"\s", "", core.strip_md(body)))
        inlinks = len(re.findall(rf"\]\(https://{DOMAINS[BLOG]}\.blogspot\.com/20", body))
        score = 100 - 15 * len(errs) - 10 * len(tmpl) - (10 if inlinks == 0 else 0) - (10 if chars < 1800 else 0)
        rows.append((score, titles[fn], chars, len(tmpl), inlinks, errs, urls[fn], fn))
        if score < 70:
            weak.append(fn)
    rows.sort()

    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    lines = [f"# 애드센스 기준 점검: {BLOG} ({now} KST)", "",
             f"- 공개 글: {len(live)}편",
             f"- 2편 이상에 반복된 문장 비율: {dup * 100 // total}% (목표 5% 미만)",
             f"- 약한 글(점수 70 미만): {len(weak)}편",
             f"- 겹침·합치기 후보: {len(pairs)}쌍", "",
             "## 라벨별 글 수 (라벨마다 8편 이상 권장)", ""]
    for l, c in labels.most_common():
        lines.append(f"- {l}: {c}편{'' if c >= MIN_PER_LABEL else '  ← 부족'}")
    lines += ["", "## 겹침·합치기 후보", ""]
    if pairs:
        lines += ["| 겹침 | 글 A | 글 B | 이유 |", "| --- | --- | --- | --- |"]
        for r, a, b, why in pairs[:30]:
            lines.append(f"| {r} | {titles[a][:30]} ({a}) | {titles[b][:30]} ({b}) | {why} |")
    else:
        lines.append("- 없음")
    lines += ["", "## 반복이 많은 문장 (3편 이상)", ""]
    common = [(c, s) for s, c in sent_count.most_common(15) if c >= 3]
    lines += [f"- {c}편: {s[:60]}" for c, s in common] or ["- 없음"]
    lines += ["", "## 글별 점수 (낮은 순)", "", "| 점수 | 글 | 글자 | 틀 문장 | 본문 내부 링크 | 검수 오류 |",
              "| --- | --- | --- | --- | --- | --- |"]
    for s, t, ch, tm, il, er, url, fn in rows:
        lines.append(f"| {s} | [{t[:28]}]({url}) `{fn}` | {ch} | {tm} | {il} | {'; '.join(er)[:100] or '-'} |")
    lines += ["", "비공개·통합·삭제는 사용자와 상의한 뒤에만 한다. 보강(내용 추가·문장 수정)은 바로 해도 된다."]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", "utf-8")
    print("\n".join(lines[:7]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
