"""글 맨 끝 '출처:' 문단 (2026-11-24 사용자 결정).

규칙: 모든 블로그 글의 마지막 문단은 '출처: [자료명](URL) · [자료명](URL)' 한 줄.
출처에는 공식 사이트(정부·공공기관·법령·공시 원문)만 넣는다. 분양 홈페이지·언론·블로그는 넣지 않는다.
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent

# 공식 사이트: .go.kr 전체, 외국 정부(.gov), 그리고 공공기관이 운영하는 아래 주소
OFFICIAL_HOSTS = {
    "applyhome.co.kr",      # 청약홈(한국부동산원)
    "dart.fss.or.kr",       # 금융감독원 전자공시
    "kind.krx.co.kr",       # 한국거래소 기업공시
    "data.krx.co.kr",       # 한국거래소 정보데이터
    "reb.or.kr",            # 한국부동산원
    "korea.kr",             # 대한민국 정책브리핑
    "kiast.or.kr",          # 항공안전기술원
    "droneportal.or.kr",    # 드론산업 정보포털(항공안전기술원)
    "kosis.kr",             # 국가통계포털
}
SOURCE_RE = re.compile(r"^출처\s*[:：]")
LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
DEFAULTS = {
    "cheongyak": [("청약홈", "https://www.applyhome.co.kr")],
    "jeonse": [("국토교통부 실거래가 공개시스템", "https://rt.molit.go.kr")],
    "gongmoju": [("금융감독원 전자공시시스템(DART)", "https://dart.fss.or.kr")],
    "gwanribi": [("공동주택관리정보시스템(K-apt)", "https://www.k-apt.go.kr")],
    "drone": [],
}


def is_official(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host.startswith("m."):
        host = host[2:]
    if host.endswith(".go.kr") or host == "go.kr" or host.endswith(".gov"):
        return True
    return any(host == h or host.endswith("." + h) for h in OFFICIAL_HOSTS)


def _paras(body: str) -> list[str]:
    return [b.strip() for b in re.split(r"\n\s*\n", body.strip()) if b.strip()]


def source_errors(body: str) -> list[str]:
    ps = _paras(body)
    last = ps[-1] if ps else ""
    if not SOURCE_RE.match(last):
        return ["[출처] 글 맨 끝 문단이 '출처: [자료명](공식 사이트 주소)' 줄이어야 합니다."]
    links = LINK_RE.findall(last)
    if not links:
        return ["[출처] 출처 줄에 링크가 없습니다. 공식 사이트 원문 링크를 넣으세요."]
    bad = [u for _, u in links if not is_official(u)]
    if bad:
        return [f"[출처] 공식 사이트가 아닌 출처: {bad[:3]}. 정부·공공기관·법령·공시 원문만 넣습니다."]
    return []


def _drone_note_links(slug: str) -> list[tuple[str, str]]:
    p = ROOT / "blogs/drone/data/sources" / f"{slug}.md"
    if not p.exists():
        return []
    out, name = [], ""
    for line in p.read_text("utf-8").splitlines():
        m = re.match(r"^##\s*\d*\.?\s*(.+)", line)
        if m:
            name = re.sub(r"\s*\([^)]*\d{4}[^)]*\)\s*$", "", m.group(1)).strip(" '\"")
            continue
        m = re.search(r"URL\s*[:：]\s*(https?://\S+)", line)
        if m and name:
            out.append((name[:40], m.group(1).rstrip(").,")))
    return out


def build_line(blog: str, meta: dict, body: str) -> str:
    """본문에 이미 있는 공식 링크 + 블로그 기본 출처로 '출처:' 줄을 만든다(최대 4개)."""
    items: list[tuple[str, str]] = []
    for t, u in LINK_RE.findall(body):
        if is_official(u):
            items.append((t.strip(), u))
    if blog == "drone":
        items += _drone_note_links(str(meta.get("slug", "")))
    if blog != "cheongyak" or "청약홈" in body:
        items += DEFAULTS.get(blog, [])
    if blog == "cheongyak" and not items:
        items += [("국토교통부 실거래가 공개시스템", "https://rt.molit.go.kr")]
    seen, out = set(), []
    for t, u in items:
        key = u.split("#")[0].rstrip("/")
        host = urlparse(u).hostname
        if key in seen or not t:
            continue
        # 같은 사이트 첫 화면 기본 링크는 그 사이트 원문 링크가 이미 있으면 뺀다
        if u.rstrip("/").count("/") <= 2 and any(urlparse(x).hostname == host for _, x in out):
            continue
        seen.add(key)
        out.append((t, u))
        if len(out) >= 4:
            break
    return "출처: " + " · ".join(f"[{t}]({u})" for t, u in out)
