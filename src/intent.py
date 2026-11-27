"""검색 의도 검사 (사용자 지적 2026-11-28: 형식은 맞는데 검색한 사람이 원하는 답이 없던 문제).

대표 키워드로 검색한 사람이 가장 먼저 알고 싶은 답이 첫 문단에 있어야 한다.
- 공모주 '○○ 공모주/청약/공모가/수요예측': 청약일·공모가(또는 희망 공모가) 첫 문단, 수요예측·상장 일정은 첫 두 문단 안
- 청약 '○○ 청약 일정': 접수 날짜 / '○○ 분양가': 금액 / '○○ 당첨 가점': 점수
- 전세 '○○ 아파트 전세': 전세 금액(억·만 원)
- 관리비 '○○ 관리비'(단지·지역): 세대당 한 달 금액
"""
from __future__ import annotations

import re

DATE = re.compile(r"\d{1,2}월\s*\d{1,2}일|\d{1,2}월\s*\d{1,2}\s*[~～-]\s*\d{1,2}일")
MONEY = re.compile(r"\d[\d,]*\s*억|\d[\d,]*\s*만\s*[\d,]*\s*원")
GONGMOJU_TOPIC = re.compile(r"수수료|자금|구주|인수단|설립|본사|발행제|정정|주관사|규모|증거금|일정$|스팩")
GWANRIBI_TOPIC = re.compile(r"항목|장기수선|고지서|난방비|전기료|경비비|승강기|수선비|공용관리비|계획|계산")


def _paras(body: str) -> list[str]:
    ps = [p.strip() for p in re.split(r"\n\s*\n", body.strip()) if p.strip()]
    return [p for p in ps if not p.startswith(("#", "!", "|", ">"))]


def intent_errors(meta: dict, body: str, blog: str) -> list[str]:
    kw = str(meta.get("keyword") or "").strip()
    ps = _paras(body)
    p1 = ps[0] if ps else ""
    p12 = " ".join(ps[:2])
    errs: list[str] = []
    tag = "[검색 의도]"
    if blog == "gongmoju" and re.search(r"공모주|공모가|수요예측|청약", kw) and not GONGMOJU_TOPIC.search(kw):
        if not DATE.search(p1):
            errs.append(f"{tag} '{kw}' 검색자는 청약 일정을 먼저 찾습니다. 첫 문단에 청약일(○월 ○~○일)을 쓰세요.")
        if not re.search(r"공모가|희망", p1):
            errs.append(f"{tag} 첫 문단에 공모가(확정 전이면 희망 공모가 범위)를 쓰세요.")
        if not re.search(r"수요예측|상장", p12):
            errs.append(f"{tag} 첫 두 문단 안에 수요예측 일정·결과나 상장 예정일을 쓰세요.")
    elif blog == "cheongyak":
        if "일정" in kw and not DATE.search(p1):
            errs.append(f"{tag} '{kw}' 검색자는 접수 날짜를 찾습니다. 첫 문단에 특별공급·1순위·당첨자 발표 날짜를 쓰세요.")
        if "분양가" in kw and not MONEY.search(p1):
            errs.append(f"{tag} '{kw}' 검색자는 금액을 찾습니다. 첫 문단에 분양가(억·만 원)를 쓰세요.")
        if "가점" in kw and not re.search(r"\d+\s*점", p1):
            errs.append(f"{tag} '{kw}' 검색자는 커트라인을 찾습니다. 첫 문단에 당첨 가점(○점)을 쓰세요.")
    elif blog == "jeonse" and re.search(r"(구|시|군|동)\s*아파트\s*전세$|전세\s*(시세|가격)$", kw):
        if not MONEY.search(p1):
            errs.append(f"{tag} '{kw}' 검색자는 전세가가 얼마인지 찾습니다. 첫 문단에 전세 금액(억·만 원)을 쓰세요. 전세가율은 그다음입니다.")
    elif blog == "gwanribi" and kw.endswith("관리비") and not GWANRIBI_TOPIC.search(kw):
        if not re.search(r"세대|한 달|월", p1) or not MONEY.search(p1):
            errs.append(f"{tag} '{kw}' 검색자는 한 달에 얼마 내는지 찾습니다. 첫 문단에 세대당 한 달 관리비(만 원)를 쓰세요. ㎡당 값은 그다음입니다.")
    return errs
