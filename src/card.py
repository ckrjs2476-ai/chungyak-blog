"""글 맨 위에 넣는 요약 카드 (이미지 파일 없이 HTML로).

숫자는 모두 data/units/의 원본 데이터에서 바로 가져오므로 글 본문과 달리 검수 대상이 아니다.
Blogger는 글 안의 <style> 태그를 지우는 경우가 있어 모든 꾸밈을 style 속성으로 넣는다.
"""
from __future__ import annotations

import re

import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNITS = ROOT / "data" / "units"

BOX = ("border:1px solid #d9dee7;border-radius:12px;padding:16px 18px;margin:0 0 24px;"
       "background:#f7f9fc;font-size:15px;line-height:1.6;color:#1f2933;")
TITLE = "font-size:17px;font-weight:700;margin:0 0 4px;"
SUB = "font-size:13px;color:#52606d;margin:0 0 12px;"
ROW_L = "padding:6px 12px 6px 0;color:#52606d;white-space:nowrap;vertical-align:top;border:0;"
ROW_R = "padding:6px 0;font-weight:600;border:0;color:#111111;"
NOTE = "font-size:12px;color:#7b8794;margin:10px 0 0;"


def _date(v) -> str:
    s = str(v or "").strip().replace("-", "")
    if len(s) == 8 and s.isdigit():
        return f"{int(s[4:6])}월 {int(s[6:])}일"
    return ""


def _won(manwon: int) -> str:
    eok, rest = divmod(manwon, 10000)
    if eok and rest:
        return f"{eok}억 {rest:,}만 원"
    if eok:
        return f"{eok}억 원"
    return f"{rest:,}만 원"


def _int(v) -> int:
    try:
        return int(float(str(v).replace(",", "")))
    except (TypeError, ValueError):
        return 0


def house_ty(v) -> str:
    """'084.0000A' -> '84A', '084.9500C' -> '84.95C'"""
    m = re.match(r"0*(\d+)(?:\.(\d+))?([A-Za-z]*)", str(v or ""))
    if not m:
        return str(v or "")
    frac = (m.group(2) or "").rstrip("0")
    return m.group(1) + (f".{frac}" if frac else "") + m.group(3)


def _rows_notice(unit: dict) -> list[tuple[str, str]]:
    d = unit.get("detail", {})
    rows = []
    if _int(d.get("TOT_SUPLY_HSHLDCO")):
        rows.append(("공급", f"{_int(d['TOT_SUPLY_HSHLDCO']):,}세대"))
    for label, key in (("특별공급", "SPSPLY_RCEPT_BGNDE"), ("1순위", "GNRL_RNK1_CRSPAREA_RCPTDE"),
                       ("접수", "SUBSCRPT_RCEPT_BGNDE"), ("당첨 발표", "PRZWNER_PRESNATN_DE")):
        if _date(d.get(key)) and not (label == "접수" and any(r[0] == "1순위" for r in rows)):
            rows.append((label, _date(d.get(key))))
    if _date(d.get("CNTRCT_CNCLS_BGNDE")):
        end = _date(d.get("CNTRCT_CNCLS_ENDDE"))
        rows.append(("계약", _date(d["CNTRCT_CNCLS_BGNDE"]) + (f" ~ {end}" if end else "")))
    prices = [_int(m.get("LTTOT_TOP_AMOUNT")) for m in unit.get("models", []) if _int(m.get("LTTOT_TOP_AMOUNT"))]
    if prices:
        lo, hi = min(prices), max(prices)
        rows.append(("최고 분양가", _won(hi) if lo == hi else f"{_won(lo)} ~ {_won(hi)}"))
    return rows


def _rows_competition(unit: dict) -> list[tuple[str, str]]:
    rates = []
    for r in unit.get("competition", []):
        try:
            rates.append((float(str(r.get("CMPET_RATE", "")).replace(",", "")), r))
        except ValueError:
            continue
    if not rates:
        return _rows_notice(unit)
    best_rate, best = max(rates, key=lambda x: x[0])
    req = sum(_int(r.get("REQ_CNT")) for _, r in rates)
    rows = [("최고 경쟁률", f"{best.get('CMPET_RATE')} 대 1 ({house_ty(best.get('HOUSE_TY'))})")]
    if req:
        rows.append(("총 접수", f"{req:,}건"))
    d = unit.get("detail", {})
    if _date(d.get("PRZWNER_PRESNATN_DE")):
        rows.append(("당첨 발표", _date(d["PRZWNER_PRESNATN_DE"])))
    return rows


def _rows_score(unit: dict) -> list[tuple[str, str]]:
    lows = [(_int(s.get("LWET_SCORE")), s) for s in unit.get("score", []) if _int(s.get("LWET_SCORE"))]
    if not lows:
        return _rows_notice(unit)
    lo, lo_row = min(lows, key=lambda x: x[0])
    hi = max(_int(s.get("TOP_SCORE")) for s in unit.get("score", []))
    rows = [("최저 당첨 가점", f"{lo}점 ({house_ty(lo_row.get('HOUSE_TY'))})")]
    if hi:
        rows.append(("최고 당첨 가점", f"{hi}점"))
    d = unit.get("detail", {})
    if _date(d.get("CNTRCT_CNCLS_BGNDE")):
        rows.append(("계약 시작", _date(d["CNTRCT_CNCLS_BGNDE"])))
    return rows


def build_card(meta: dict) -> str:
    """머리말(meta)의 house_manage_no와 type으로 카드 HTML을 만든다. 데이터가 없으면 빈 문자열."""
    no = str(meta.get("house_manage_no") or "")
    p = UNITS / f"{no}.json"
    if not no or not p.exists():
        return ""
    unit = json.loads(p.read_text("utf-8"))
    d = unit.get("detail", {})
    typ = meta.get("type")
    rows = {"competition": _rows_competition, "score": _rows_score}.get(typ, _rows_notice)(unit)
    if not rows:
        return ""
    trs = "".join(f'<tr><td style="{ROW_L}">{escape(k)}</td><td style="{ROW_R}">{escape(v)}</td></tr>'
                  for k, v in rows)
    link = str(d.get("PBLANC_URL") or "https://www.applyhome.co.kr")
    return (f'<div style="{BOX}">'
            f'<p style="{TITLE}">{escape(str(d.get("HOUSE_NM", "")))}</p>'
            f'<p style="{SUB}">{escape(str(d.get("HSSPLY_ADRES", "")))}</p>'
            f'<table style="border-collapse:collapse;border:0;width:100%;">{trs}</table>'
            f'<p style="{NOTE}">한눈에 보기 · 출처: <a href="{escape(link)}" rel="noopener">청약홈 공고</a></p>'
            f'</div>')
