"""데이터 API 시험 호출. 결과는 ::notice:: 로만 남긴다(키는 출력하지 않음)."""
import os, re
import requests

key = os.environ.get("DATA_GO_KR_KEY", "")
B = "https://apis.data.go.kr/1613000/"

OUT = []

def show(name, url, params):
    try:
        r = requests.get(url, params={"serviceKey": key, **params}, timeout=40)
        t = re.sub(r"\s+", " ", r.text)[:260]
        OUT.append(f"{name} → {r.status_code} | {t}")
        return r.text
    except Exception as e:
        OUT.append(f"{name} → 실패 {type(e).__name__}")
        return ""

import json
C = "AptCmnuseManageCostServiceV3/"; I = "AptIndvdlzManageCostServiceV3/"; R = "AptRepairsCostServiceV3/"
r = requests.get(B + "AptListService4/getSigunguAptList4", params={"serviceKey": key, "sigunguCode": "11680", "numOfRows": 400, "pageNo": 1, "_type": "json"}, timeout=40)
items = r.json()["response"]["body"]["items"]
OUT.append(f"강남구 단지 수 응답: {len(items)}, totalCount={r.json()['response']['body'].get('totalCount')}")
big = None
for it in items[:60]:
    b = requests.get(B + "AptBasisInfoServiceV5/getAphusBassInfoV5", params={"serviceKey": key, "kaptCode": it["kaptCode"], "_type": "json"}, timeout=40).json()["response"]["body"]["item"]
    if b and (b.get("kaptdaCnt") or 0) >= 500:
        big = it["kaptCode"]; OUT.append(f"큰 단지: {big} {b.get('kaptName')} 세대 {b.get('kaptdaCnt')} | " + json.dumps(b, ensure_ascii=False)[:900]); break
kc = big or "A13505003"
for ym in ["202608", "202607", "202606", "202605", "202604", "202512"]:
    show(f"인건비 {ym}", B + C + "getHsmpLaborCostInfoV3", {"kaptCode": kc, "searchDate": ym, "_type": "json"})
    show(f"전기 {ym}", B + I + "getHsmpElectricityCostInfoV3", {"kaptCode": kc, "searchDate": ym, "_type": "json"})
    show(f"장기수선 월부과 {ym}", B + R + "getHsmpMonthFeeInfoV3", {"kaptCode": kc, "searchDate": ym, "_type": "json"})
ym = "202606"
for op in ["getHsmpReserveBalanceInfoV3", "getHsmpAccumulationTariffInfoV3", "getHsmpMonthRetalFeeInfoV3"]:
    show(f"장기수선 {op} {ym}", B + R + op, {"kaptCode": kc, "searchDate": ym, "_type": "json"})
for op in ["getHsmpCleaningCostInfoV3", "getHsmpGuardCostInfoV3", "getHsmpElevatorMntncCostInfoV3", "getHsmpConsignManageFeeInfoV3"]:
    show(f"공용 {op} {ym}", B + C + op, {"kaptCode": kc, "searchDate": ym, "_type": "json"})
for op in ["getHsmpHeatCostInfoV3", "getHsmpWaterCostInfoV3", "getHsmpHotWaterCostInfoV3"]:
    show(f"개별 {op} {ym}", B + I + op, {"kaptCode": kc, "searchDate": ym, "_type": "json"})

os.makedirs("data", exist_ok=True)
open("data/probe.txt", "w", encoding="utf-8").write("\n".join(OUT) + "\n")
print("\n".join(OUT))
