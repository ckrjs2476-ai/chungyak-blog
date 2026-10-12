"""애드센스 신청 전 점검. 공개 글 전체를 보고 약한 글·얇은 라벨·틀 문장을 찾아 data/audit.md로 남긴다.
사용: python src/audit.py
기준(rules/adsense_approval.md): 라벨마다 8편 이상, 글마다 분석 숫자·해설·내부 링크, 틀 문장 최소.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from check import DONE, PUBLISHED, check_text, split_post, template_sentences, _sentences, _norm

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "audit.md"
KST = timezone(timedelta(hours=9))
MIN_PER_LABEL = 8


def main() -> int:
    posts = json.loads(PUBLISHED.read_text("utf-8"))["posts"] if PUBLISHED.exists() else []
    live = [p for p in posts if p.get("status") == "LIVE"]
    labels = Counter(l for p in live for l in p.get("labels", []))
    # 블로그 전체에서 2편 이상에 나온 문장(숫자 무시) 비율
    sent_count: Counter = Counter()
    per_post: dict[str, list[str]] = {}
    for p in live:
        f = DONE / p.get("file", "")
        if not f.exists():
            continue
        _, body = split_post(f.read_text("utf-8"))
        ss = {_norm(x) for x in _sentences(body)}
        per_post[p["file"]] = list(ss)
        sent_count.update(ss)
    total = sum(sent_count.values()) or 1
    dup = sum(c for c in sent_count.values() if c > 1)

    rows, weak = [], []
    for p in live:
        f = DONE / p.get("file", "")
        if not f.exists():
            continue
        meta, body = split_post(f.read_text("utf-8"))
        meta["_file"] = f.name
        errs = check_text(meta, body, [])
        tmpl = template_sentences(body, exclude_file=f.name)
        chars = len(re.sub(r"\s", "", body))
        inlinks = len(re.findall(r"\]\(https://daily-cheongyak\.blogspot\.com/20", body))
        score = 100 - 15 * len(errs) - 10 * len(tmpl) - (10 if inlinks == 0 else 0) - (10 if chars < 1800 else 0)
        rows.append((score, p["title"], chars, len(tmpl), inlinks, errs, p.get("url", "")))
        if score < 70:
            weak.append(p["title"])
    rows.sort()

    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    lines = [f"# 애드센스 신청 전 점검 ({now} KST)", "",
             f"- 공개 글: {len(live)}편 (권장 30~40편, 단 약한 글은 수보다 해롭다)",
             f"- 블로그 전체 문장 중 2편 이상에 반복된 문장 비율: {dup * 100 // total}% (낮을수록 좋음, 목표 5% 미만)",
             f"- 약한 글(점수 70 미만): {len(weak)}편", "", "## 라벨별 글 수 (라벨마다 8편 이상 권장)", ""]
    for l, c in labels.most_common():
        lines.append(f"- {l}: {c}편{'' if c >= MIN_PER_LABEL else '  ← 부족 (신청 전 보강하거나 메뉴에서 숨김)'}")
    lines += ["", "## 글별 점수 (낮은 순)", "", "| 점수 | 글 | 글자 | 틀 문장 | 본문 내부 링크 | 검수 오류 |", "| --- | --- | --- | --- | --- | --- |"]
    for s, t, ch, tm, il, er, url in rows:
        lines.append(f"| {s} | [{t[:28]}]({url}) | {ch} | {tm} | {il} | {'; '.join(er)[:80] or '-'} |")
    lines += ["", "약한 글 처리(비공개·통합)는 사용자와 상의한 뒤에만 한다."]
    OUT.write_text("\n".join(lines) + "\n", "utf-8")
    print("\n".join(lines[:8 + len(labels) + 2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
