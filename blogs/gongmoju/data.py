"""공모주 뜯어보기 데이터: OpenDART 증권신고서(지분증권)로 공모 구조를 정리하고 비교 숫자를 계산한다.

1) 최근 120일 발행공시(C) 중 '증권신고서(지분증권)', 비상장(corp_cls E/N) = 신규 상장 공모 후보
2) 회사마다 증권신고서 주요정보(estkRs): 청약일, 납입일, 공모주식수, 공모가, 공모총액, 인수인, 자금 사용 목적
3) 회사 개황(company): 업종코드, 설립일, 대표자, 홈페이지
4) 비교: 최근 공모들 사이 공모총액 순위·중앙값, 자금 사용 비중
결과: blogs/gongmoju/data/ipos/<corp_code>.json, blogs/gongmoju/data/summary.json
환경변수: OPENDART_KEY
"""
from __future__ import annotations

import json
import os
import statistics
import time
from datetime import date, timedelta
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent / "data"
IPOS = BASE / "ipos"
API = "https://opendart.fss.or.kr/api"
KEY = os.environ.get("OPENDART_KEY", "")
DAYS = 120


def get(path: str, **params) -> dict:
    for wait in (0, 5, 15, 40):
        time.sleep(wait)
        try:
            r = requests.get(f"{API}/{path}", params={"crtfc_key": KEY, **params}, timeout=40)
            return r.json()
        except (requests.RequestException, ValueError) as e:
            last = e
    print(f"::warning::OpenDART {path} 실패: {type(last).__name__}")
    return {}


def num(v):
    try:
        return int(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def candidates() -> list[dict]:
    end, start = date.today(), date.today() - timedelta(days=DAYS)
    out, page = [], 1
    while page <= 30:
        d = get("list.json", bgn_de=start.strftime("%Y%m%d"), end_de=end.strftime("%Y%m%d"),
                pblntf_ty="C", page_no=page, page_count=100)
        if d.get("status") not in ("000",):
            if page == 1:
                print(f"::warning::공시 목록: {d.get('status')} {d.get('message')}")
            break
        for x in d.get("list", []):
            nm = x.get("report_nm", "")
            if "증권신고서" in nm and "지분증권" in nm and x.get("corp_cls") in ("E", "N"):
                out.append(x)
        if page >= int(d.get("total_page", 1)):
            break
        page += 1
    # 회사별 가장 최근 제출본(정정 포함)
    latest: dict[str, dict] = {}
    for x in out:
        c = x["corp_code"]
        if c not in latest or x["rcept_no"] > latest[c]["rcept_no"]:
            latest[c] = x
    print(f"::notice::증권신고서(지분증권) 비상장 {len(out)}건, 회사 {len(latest)}곳")
    return list(latest.values())


def detail(x: dict) -> dict | None:
    corp = x["corp_code"]
    end = date.today()
    d = get("estkRs.json", corp_code=corp, bgn_de=(end - timedelta(days=DAYS)).strftime("%Y%m%d"),
            end_de=end.strftime("%Y%m%d"))
    if d.get("status") != "000":
        print(f"::warning::{x['corp_name']} estkRs: {d.get('status')} {d.get('message')}")
        return None
    groups = {g.get("title", f"g{i}"): g.get("list", []) for i, g in enumerate(d.get("group", []))}
    def pick(title_part):
        for t, rows in groups.items():
            if title_part in t:
                return rows
        return []
    gen = (pick("일반사항") or [{}])[-1]
    kinds = pick("증권의종류")
    stock = next((k for k in kinds if "보통" in str(k.get("stksen", ""))), kinds[-1] if kinds else {})
    underw = pick("인수인정보")
    funds = pick("자금의사용목적")
    sellers = pick("매출인")
    comp = get("company.json", corp_code=corp)
    fund_rows = [{"use": f.get("se", ""), "amount": num(f.get("amt"))} for f in funds if num(f.get("amt"))]
    total_fund = sum(f["amount"] for f in fund_rows) or None
    for f in fund_rows:
        f["share_pct"] = round(f["amount"] * 100 / total_fund, 1) if total_fund else None
    return {
        "corp_code": corp, "corp_name": x["corp_name"], "rcept_no": x["rcept_no"], "rcept_dt": x["rcept_dt"],
        "report_nm": x["report_nm"], "corp_cls": x.get("corp_cls"),
        "dart_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={x['rcept_no']}",
        "subscription": gen.get("sbd"), "payment_date": gen.get("pymd"), "notice_date": gen.get("sband"),
        "allot_date": gen.get("asand"),
        "stock_kind": stock.get("stksen"), "shares": num(stock.get("stkcnt")), "face_value": num(stock.get("fv")),
        "price": num(stock.get("slprc")), "total": num(stock.get("slta")), "method": stock.get("slmthn"),
        "underwriters": [{"name": u.get("actnmn"), "shares": num(u.get("udtcnt")), "amount": num(u.get("udtamt")),
                          "fee": num(u.get("udtprc")), "how": u.get("udtmth")} for u in underw],
        "fund_uses": fund_rows, "fund_total": total_fund,
        "sellers": [{"name": s.get("hdr"), "relation": s.get("rl_cmp"), "shares": num(s.get("slstk"))} for s in sellers],
        "sell_shares": sum(num(s.get("slstk")) or 0 for s in sellers) or None,
        "company": {k: comp.get(k) for k in ("corp_name", "ceo_nm", "induty_code", "est_dt", "hm_url", "adres")}
        if comp.get("status") == "000" else {},
        "raw_groups": list(groups.keys()),
    }


def compare(items: list[dict]) -> None:
    ok = [i for i in items if i.get("total")]
    totals = sorted((i["total"] for i in ok), reverse=True)
    med = int(statistics.median(totals)) if totals else None
    for i in items:
        if i.get("total"):
            i["total_rank"] = totals.index(i["total"]) + 1
            i["total_rank_of"] = len(totals)
            i["total_vs_median_pct"] = round((i["total"] - med) * 100 / med, 1) if med else None
        if i.get("sell_shares") and i.get("shares"):
            i["sell_share_pct"] = round(i["sell_shares"] * 100 / i["shares"], 1)
        top = max(i.get("fund_uses") or [], key=lambda f: f["amount"], default=None)
        i["top_fund_use"] = top
        i["compare_median_total"] = med
        i["compare_count"] = len(totals)
    (BASE / "summary.json").write_text(json.dumps({
        "updated": date.today().isoformat(), "days": DAYS, "count": len(items), "median_total": med,
        "ipos": sorted([{k: i.get(k) for k in ("corp_code", "corp_name", "subscription", "price", "total", "total_rank")}
                        for i in items], key=lambda r: r.get("total") or 0, reverse=True)},
        ensure_ascii=False, indent=1), "utf-8")


def main() -> int:
    if not KEY:
        print("::error::OPENDART_KEY가 없습니다.")
        return 0
    IPOS.mkdir(parents=True, exist_ok=True)
    items = []
    for x in candidates():
        d = detail(x)
        if d:
            items.append(d)
        time.sleep(0.3)
    compare(items)
    for d in items:
        (IPOS / f"{d['corp_code']}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), "utf-8")
    print(f"::notice::공모 {len(items)}곳 저장")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
