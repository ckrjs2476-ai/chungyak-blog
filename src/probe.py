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

# 1) 단지 목록 (강남구 11680)
kapt = None
for svc, op in [("AptListService4", "getSigunguAptList4")]:
    t = show(f"단지목록 {svc}/{op}", B + f"{svc}/{op}", {"sigunguCode": "11680", "numOfRows": 3, "pageNo": 1, "_type": "json"})
    m = re.search(r'"kaptCode"\s*:\s*"([A-Z0-9]+)"|<kaptCode>([A-Z0-9]+)<', t, re.I)
    if m:
        kapt = m.group(1) or m.group(2)
        break
OUT.append(f"찾은 단지코드: {kapt}")
kc = kapt or "A13505003"
# 2) 기본정보
for svc, op in [("AptBasisInfoServiceV5", "getAphusBassInfoV5")]:
    show(f"기본정보 {svc}/{op}", B + f"{svc}/{op}", {"kaptCode": kc, "_type": "json"})
# 3) 월별 비용 — 어느 달부터 값이 있는지
C = "AptCmnuseManageCostServiceV3/"; I = "AptIndvdlzManageCostServiceV3/"; R = "AptRepairsCostServiceV3/"
for ym in ["202608", "202607", "202606", "202605", "202512"]:
    show(f"인건비 {ym}", B + C + "getHsmpLaborCostInfoV3", {"kaptCode": kc, "searchDate": ym, "_type": "json"})
    show(f"전기 {ym}", B + I + "getHsmpElectricityCostInfoV3", {"kaptCode": kc, "searchDate": ym, "_type": "json"})
    show(f"장기수선 월부과 {ym}", B + R + "getHsmpMonthFeeInfoV3", {"kaptCode": kc, "searchDate": ym, "_type": "json"})
ym = "202606"
for op in ["getHsmpReserveBalanceInfoV3", "getHsmpAccumulationTariffInfoV3", "getHsmpMonthRetalFeeInfoV3"]:
    show(f"장기수선 {op} {ym}", B + R + op, {"kaptCode": kc, "searchDate": ym, "_type": "json"})
for op in ["getHsmpCleaningCostInfoV3", "getHsmpGuardCostInfoV3", "getHsmpElevatorMntncCostInfoV3", "getHsmpConsignManageFeeInfoV3"]:
    show(f"공용 {op} {ym}", B + C + op, {"kaptCode": kc, "searchDate": ym, "_type": "json"})
for op in ["getHsmpHeatCostInfoV3", "getHsmpWaterCostInfoV3", "getHsmpHeatCostInfoV2"]:
    show(f"개별 {op} {ym}", B + I + op, {"kaptCode": kc, "searchDate": ym, "_type": "json"})

os.makedirs("data", exist_ok=True)
open("data/probe.txt", "w", encoding="utf-8").write("\n".join(OUT) + "\n")
print("\n".join(OUT))
