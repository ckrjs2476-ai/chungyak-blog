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
# 3) 공용관리비 (인건비 항목 예)
for svc, op in [("AptCmnuseManageCostServiceV3", "getHsmpLaborCostInfoV3"), ("AptCmnuseManageCostServiceV4", "getHsmpLaborCostInfoV4"), ("AptCmnuseManageCostService4", "getHsmpLaborCostInfo4")]:
    show(f"공용관리비 {svc}/{op}", B + f"{svc}/{op}", {"kaptCode": kc, "searchDate": "202608", "_type": "json"})
# 4) 개별사용료 (전기료 예)
for svc, op in [("AptIndvdlzManageCostServiceV3", "getHsmpElectricityCostInfoV3"), ("AptIndvdlzManageCostServiceV4", "getHsmpElectricityCostInfoV4"), ("AptIndvdlzManageCostService4", "getHsmpElectricityCostInfo4")]:
    show(f"개별사용료 {svc}/{op}", B + f"{svc}/{op}", {"kaptCode": kc, "searchDate": "202608", "_type": "json"})
# 5) 장기수선충당금
for svc, op in [("AptLtsmRepairsServiceV5", "getHsmpLtsmRepairsInfoV5"), ("AptLongtermRepairsServiceV3", "getHsmpLongtermRepairsInfoV3"), ("AptCmnuseManageCostServiceV3", "getHsmpLtsmRepairsInfoV3")]:
    show(f"장기수선 {svc}/{op}", B + f"{svc}/{op}", {"kaptCode": kc, "searchDate": "202608", "_type": "json"})

os.makedirs("data", exist_ok=True)
open("data/probe.txt", "w", encoding="utf-8").write("\n".join(OUT) + "\n")
print("\n".join(OUT))
