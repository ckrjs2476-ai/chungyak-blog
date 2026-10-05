"""청약홈 공고·주택형·경쟁률·당첨가점을 받아 data/units/에 저장하고,
오늘 쓸 글 후보(data/jobs.json)를 점수순으로 만든다.

필요: 공공데이터포털 '청약홈 분양정보 조회 서비스'와
'청약홈 청약접수 경쟁률 및 특별공급 신청현황 조회 서비스' 활용신청, DATA_GO_KR_KEY 환경변수.
엔드포인트와 필드 이름은 공개 저장소의 사용 예를 참고했고(공식 명세서 대조 필요),
첫 실행 때 실제 응답으로 확인한다.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
UNITS = DATA / "units"
KST = timezone(timedelta(hours=9))
BASE = "https://api.odcloud.kr/api"

EP = {
    "apt": {
        "detail": f"{BASE}/ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail",
        "models": f"{BASE}/ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancMdl",
        "cmpet": f"{BASE}/ApplyhomeInfoCmpetRtSvc/v1/getAPTLttotPblancCmpet",
        "compact_date": False,
    },
    "remndr": {
        "detail": f"{BASE}/ApplyhomeInfoDetailSvc/v1/getRemndrLttotPblancDetail",
        "models": f"{BASE}/ApplyhomeInfoDetailSvc/v1/getRemndrLttotPblancMdl",
        "cmpet": f"{BASE}/ApplyhomeInfoCmpetRtSvc/v1/getRemndrLttotPblancCmpet",
        "compact_date": False,
    },
}
SCORE = f"{BASE}/ApplyhomeInfoCmpetRtSvc/v1/getAptLttotPblancScore"

METRO = ("서울", "경기", "인천", "부산", "대구", "광주", "대전", "울산", "세종")
BRANDS = ("자이", "래미안", "힐스테이트", "푸르지오", "e편한세상", "롯데캐슬", "더샵",
          "아이파크", "SK뷰", "호반써밋", "디에이치", "아크로", "르엘", "포레나", "위브")


def today_kst() -> date:
    return datetime.now(KST).date()


def call(endpoint: str, cond: dict[str, str], per_page: int = 100, max_pages: int = 10) -> list[dict]:
    key = os.environ.get("DATA_GO_KR_KEY", "")
    if not key:
        raise SystemExit("DATA_GO_KR_KEY 환경변수가 없습니다.")
    service_key = key if "%" in key else urllib.parse.quote(key, safe="")
    rows: list[dict] = []
    for page in range(1, max_pages + 1):
        params = [f"page={page}", f"perPage={per_page}", "returnType=JSON", f"serviceKey={service_key}"]
        params += [f"{urllib.parse.quote(f'cond[{k}]')}={urllib.parse.quote(v)}" for k, v in cond.items()]
        res = requests.get(f"{endpoint}?{'&'.join(params)}", timeout=30)
        res.raise_for_status()
        body = res.json()
        data = body.get("data") or []
        rows.extend(data)
        total = body.get("matchCount") or body.get("totalCount") or 0
        if len(rows) >= total or not data:
            break
    return rows


def ymd(v) -> str:
    s = str(v or "").strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s


def score_unit(d: dict) -> int:
    s = 0
    addr = str(d.get("HSSPLY_ADRES", ""))
    if addr.startswith(METRO[:3]):
        s += 30
    elif addr.startswith(METRO[3:]):
        s += 15
    try:
        s += min(int(d.get("TOT_SUPLY_HSHLDCO") or 0) // 50, 30)
    except ValueError:
        pass
    name = str(d.get("HOUSE_NM", ""))
    if any(b in name for b in BRANDS):
        s += 20
    return s


def load_published() -> set[str]:
    p = DATA / "published.json"
    if not p.exists():
        return set()
    return {f"{x['house_manage_no']}:{x['type']}" for x in json.loads(p.read_text("utf-8")).get("posts", [])}


def main(days: int = 30) -> None:
    UNITS.mkdir(parents=True, exist_ok=True)
    today = today_kst()
    since = (today - timedelta(days=days)).isoformat()
    published = load_published()
    jobs: list[dict] = []

    for kind, ep in EP.items():
        notices = call(ep["detail"], {"RCRIT_PBLANC_DE::GTE": since})
        for d in notices:
            no = str(d.get("HOUSE_MANAGE_NO", ""))
            if not no:
                continue
            unit = {"kind": kind, "detail": d,
                    "models": call(ep["models"], {"HOUSE_MANAGE_NO::EQ": no}, max_pages=2),
                    "competition": [], "score": []}
            rank1 = ymd(d.get("GNRL_RNK1_CRSPAREA_RCPTDE") or d.get("SUBSCRPT_RCEPT_BGNDE"))
            winner = ymd(d.get("PRZWNER_PRESNATN_DE"))
            if rank1 and rank1 < today.isoformat():
                unit["competition"] = call(ep["cmpet"], {"HOUSE_MANAGE_NO::EQ": no}, max_pages=3)
            if kind == "apt" and winner and winner <= today.isoformat():
                unit["score"] = call(SCORE, {"HOUSE_MANAGE_NO::EQ": no}, max_pages=2)
            unit["fetched_at"] = datetime.now(KST).isoformat()
            (UNITS / f"{no}.json").write_text(json.dumps(unit, ensure_ascii=False, indent=1), "utf-8")

            base = score_unit(d)
            notice_day = ymd(d.get("RCRIT_PBLANC_DE"))
            cand = []
            if kind == "remndr":
                cand.append(("remainder", base + 10))
            else:
                age = (today - date.fromisoformat(notice_day)).days if notice_day else 99
                cand.append(("notice", base + max(0, 20 - age * 3)))
                if unit["competition"]:
                    cand.append(("competition", base + 15))
                if unit["score"]:
                    cand.append(("score", base + 10))
            for typ, sc in cand:
                if f"{no}:{typ}" in published:
                    continue
                jobs.append({"house_manage_no": no, "type": typ, "name": d.get("HOUSE_NM"),
                             "address": d.get("HSSPLY_ADRES"), "priority": sc})

    jobs.sort(key=lambda j: j["priority"], reverse=True)
    (DATA / "jobs.json").write_text(json.dumps({"date": today.isoformat(), "jobs": jobs},
                                               ensure_ascii=False, indent=1), "utf-8")
    print(f"후보 {len(jobs)}건 저장. 상위: {[j['name'] + '/' + j['type'] for j in jobs[:5]]}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
