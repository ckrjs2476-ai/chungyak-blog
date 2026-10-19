"""블로그별 애드센스 신청 준비 상태. 매일 sitecheck 워크플로가 실행해 data/readiness.md를 남긴다.
기준은 rules/growth_plan.md 2장. 하나라도 '아직'이면 신청하지 않는다.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KST = timezone(timedelta(hours=9))
BLOGS = {"cheongyak": ("청약노트", ROOT), "jeonse": ("전세 온도계", ROOT / "blogs/jeonse"),
         "gongmoju": ("공모주 뜯어보기", ROOT / "blogs/gongmoju"), "gwanribi": ("관리비 돋보기", ROOT / "blogs/gwanribi")}
MIN_POSTS, MIN_DAYS, MIN_LABEL = 30, 28, 8


def main() -> int:
    today = datetime.now(KST).date()
    site = {r["key"]: r for r in json.loads((ROOT / "data/sitecheck.json").read_text("utf-8"))} if (ROOT / "data/sitecheck.json").exists() else {}
    value = (ROOT / "data/value_report.md").read_text("utf-8") if (ROOT / "data/value_report.md").exists() else ""
    lines = [f"# 애드센스 신청 준비 상태 ({today})", "", "기준: rules/growth_plan.md 2장. 모두 '충족'이어야 신청한다. 신청은 한 번에 한 블로그만.", ""]
    for key, (name, base) in BLOGS.items():
        files = sorted((base / "posts/published").glob("*.md"))
        n = len(files)
        first = date.fromisoformat(files[0].name[:10]) if files else today
        days = (today - first).days
        s = site.get(key, {})
        labels = s.get("labels") or {}
        thin = [f"{l}({c})" for l, c in labels.items() if c < MIN_LABEL]
        blocked = not s or any(str(p[0]).startswith("확인 못 함") for p in s.get("problems", []))
        probs = [p for p in s.get("problems", []) if not str(p[0]).startswith("확인 못 함")]
        m = re.search(rf"## {re.escape(name)} — 공개 글 \d+편, 가치 약한 글 (\d+)편", value)
        weak = int(m.group(1)) if m else None
        sw = (json.loads((ROOT / "data/sitewide.json").read_text("utf-8")).get("blogs", {}).get(key, {})
              if (ROOT / "data/sitewide.json").exists() else {})
        checks = [
            ("공개 글 30편 이상", n >= MIN_POSTS, f"{n}편"),
            ("첫 글 뒤 4주 이상", days >= MIN_DAYS, f"{days}일"),
            ("라벨마다 8편 이상(메뉴에 보이는 라벨)", not blocked and not thin, "오늘 확인 못 함(구글 429)" if blocked else (", ".join(thin[:6]) or "충족")),
            ("공개 화면 문제 없음(필수 페이지·메뉴·깨진 링크)", not blocked and not probs, "오늘 확인 못 함(구글 429)" if blocked else ("; ".join(f"{a}: {b}"[:60] for a, b in probs[:3]) or "충족")),
            ("가치 약한 글 0편", weak == 0, f"{weak}편" if weak is not None else "보고서 없음"),
            ("블로그 전체 점검 고칠 것 0건(틀 반복·낡은 글·기준일·이상값)", sw.get("to_fix", 1) == 0, f"{sw.get('to_fix', '보고서 없음')}건"),
            ("글 형식이 한 종류에 쏠리지 않음(최근 8편 중 75% 미만)", sw and not sw.get("format_concentrated"),
             ", ".join(f"{k} {v}" for k, v in (sw.get("type_share") or {}).items()) or "보고서 없음"),
        ]
        ok = all(c[1] for c in checks)
        # 남은 기간 어림(하루 2편 기준, 10/19 전에는 1편)
        need = max(0, MIN_POSTS - n)
        eta_posts = today + timedelta(days=(need + 1) // 2) if need else today
        eta = max(eta_posts, first + timedelta(days=MIN_DAYS))
        lines += [f"## {name}: {'신청 조건 충족' if ok else '아직'}", ""]
        lines += [f"- {'충족' if c[1] else '아직'} · {c[0]} — {c[2]}" for c in checks]
        if not ok:
            lines.append(f"- 글 수·기간만 보면 빨라야 {eta} 무렵 (서치콘솔 색인·노출은 사용자가 따로 확인)")
        lines.append("")
    (ROOT / "data/readiness.md").write_text("\n".join(lines), "utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
