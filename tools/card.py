"""글 요약 이미지(카드) 만들기 — 본문 내용을 우리가 다시 정리한 한 장짜리 그림 (2026-11-18, 드론부터).

captures/queue.json 항목: {"name": "dr-<slug>-card", "card": {...}}
card = {
  "blog": "drone",                    # 색 구분
  "layout": "points" | "steps" | "compare",   # 글마다 내용에 맞게 고른다(같은 모양 반복 금지)
  "title": "드론 기체신고, 누가 해야 하나요?",    # 그림 맨 위 질문(글의 대표 질문)
  "answer": "최대이륙중량 2kg 초과 또는 사업용이면 신고",  # 한 줄 답
  "points": [{"label": "무게 기준", "value": "2kg 초과"}, ...],   # points: 핵심 숫자 2~4개
  "steps": ["드론원스톱 접속", "기체 정보 입력", ...],             # steps: 절차 3~6단계
  "compare": {"head": ["구분", "취미", "사업"], "rows": [["신고", "2kg 초과", "무게 무관"], ...]},  # compare: 2~4행
  "source": "항공안전법 시행규칙 제301조",       # 숫자의 출처
  "date": "2026-11-18"                 # 기준일
}
규칙: 그림 속 숫자·기준은 본문에 있는 것만(검수가 captures/log.json의 card와 본문을 대조). 실제 화면처럼 꾸미지 않는다(요약 그림임이 보이게).
결과: 가로 760px webp."""
from __future__ import annotations

import html

COLORS = {
    "drone": ("#0f4c81", "#e8f1fa"),
    "cheongyak": ("#1f6f43", "#e9f6ee"),
    "jeonse": ("#8a3b12", "#fbefe7"),
    "gongmoju": ("#5b2a86", "#f2ebf9"),
    "gwanribi": ("#235e6f", "#e7f3f6"),
}
BLOG_NAME = {"drone": "드론 정보노트", "cheongyak": "청약노트", "jeonse": "전세 온도계",
             "gongmoju": "공모주 뜯어보기", "gwanribi": "관리비 돋보기"}


def _e(x) -> str:
    return html.escape(str(x))


def build_html(c: dict) -> str:
    main, soft = COLORS.get(c.get("blog", "drone"), COLORS["drone"])
    layout = c.get("layout", "points")
    body = ""
    if layout == "points":
        pts = c.get("points") or []
        cells = "".join(f'<div class="pt"><div class="v">{_e(p["value"])}</div><div class="l">{_e(p["label"])}</div></div>'
                        for p in pts[:4])
        body = f'<div class="grid g{min(len(pts), 4)}">{cells}</div>'
    elif layout == "steps":
        st = c.get("steps") or []
        body = '<ol class="steps">' + "".join(f'<li><span class="n">{i}</span><span>{_e(s)}</span></li>'
                                               for i, s in enumerate(st[:6], 1)) + "</ol>"
    elif layout == "compare":
        cp = c.get("compare") or {}
        head = "".join(f"<th>{_e(h)}</th>" for h in cp.get("head", []))
        rows = "".join("<tr>" + "".join(f"<td>{_e(x)}</td>" for x in r) + "</tr>" for r in cp.get("rows", [])[:4])
        body = f'<table class="cmp"><tr>{head}</tr>{rows}</table>'
    foot = " · ".join(x for x in [f"출처 {_e(c['source'])}" if c.get("source") else "",
                                   f"{_e(c['date'])} 기준" if c.get("date") else ""] if x)
    return f"""<html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box}} body{{margin:0;font-family:"Noto Sans CJK KR","Noto Sans KR",sans-serif;background:#fff}}
.card{{width:760px;padding:34px 38px 26px;background:{soft};border-top:10px solid {main}}}
.q{{font-size:30px;font-weight:700;color:#111;line-height:1.35;margin:0 0 12px}}
.a{{font-size:21px;color:{main};font-weight:700;line-height:1.45;margin:0 0 24px;padding:12px 16px;background:#fff;border-left:6px solid {main}}}
.grid{{display:grid;gap:12px}} .g1{{grid-template-columns:1fr}} .g2{{grid-template-columns:1fr 1fr}}
.g3{{grid-template-columns:1fr 1fr 1fr}} .g4{{grid-template-columns:1fr 1fr}}
.pt{{background:#fff;border-radius:10px;padding:16px 14px;text-align:center}}
.v{{font-size:30px;font-weight:800;color:{main};line-height:1.2}} .l{{font-size:16px;color:#444;margin-top:6px}}
.steps{{list-style:none;margin:0;padding:0}} .steps li{{display:flex;align-items:center;gap:14px;background:#fff;border-radius:10px;
padding:12px 14px;margin:0 0 9px;font-size:19px;color:#222}}
.n{{flex:0 0 34px;height:34px;border-radius:17px;background:{main};color:#fff;font-weight:700;display:flex;align-items:center;justify-content:center}}
.cmp{{width:100%;border-collapse:collapse;background:#fff;font-size:18px}} .cmp th{{background:{main};color:#fff;padding:10px}}
.cmp td{{border:1px solid #dde3ea;padding:10px;text-align:center;color:#222}}
.f{{display:flex;justify-content:space-between;margin-top:20px;font-size:14px;color:#555}} .b{{font-weight:700;color:{main}}}
</style></head><body><div class="card" id="card">
<div class="q">{_e(c.get("title", ""))}</div>
{f'<div class="a">{_e(c["answer"])}</div>' if c.get("answer") else ""}
{body}
<div class="f"><span>{foot}</span><span class="b">{_e(BLOG_NAME.get(c.get("blog", "drone"), ""))} 정리</span></div>
</div></body></html>"""


def card_numbers(c: dict) -> list[str]:
    """그림에 들어간 글자 중 숫자가 든 조각(검수용)."""
    import re
    texts = [c.get("answer", "")]
    texts += [p.get("value", "") for p in c.get("points") or []]
    texts += list(c.get("steps") or [])
    for r in (c.get("compare") or {}).get("rows", []):
        texts += list(r)
    out = []
    for t in texts:
        out += re.findall(r"\d[\d,]*(?:\.\d+)?\s*[가-힣A-Za-z%㎡]*", str(t))
    return [x.strip() for x in out if x.strip()]
