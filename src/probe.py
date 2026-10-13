"""데이터 API 시험 호출. 결과는 ::notice:: 로만 남긴다(키는 출력하지 않음)."""
import os, re
import requests

key = os.environ.get("DATA_GO_KR_KEY", "")
B = "https://apis.data.go.kr/1613000/"

def show(name, url, params):
    try:
        r = requests.get(url, params={"serviceKey": key, **params}, timeout=40)
        t = re.sub(r"\s+", " ", r.text)[:260]
        print(f"::notice::{name} → {r.status_code} | {t}")
        return r.text
    except Exception as e:
        print(f"::notice::{name} → 실패 {type(e).__name__}")
        return ""

# 1) 단지 목록 (강남구 11680)
kapt = None
for svc, op in [("AptListService3", "getSigunguAptList3"), ("AptListService2", "getSigunguAptList2"), ("AptListService2", "getSigunguAptList")]:
    t = show(f"단지목록 {svc}/{op}", B + f"{svc}/{op}", {"sigunguCode": "11680", "numOfRows": 3, "pageNo": 1, "_type": "json"})
    m = re.search(r'"kaptCode"\s*:\s*"([A-Z0-9]+)"|<kaptCode>([A-Z0-9]+)<', t)
    if m:
        kapt = m.group(1) or m.group(2)
        break
print(f"::notice::찾은 단지코드: {kapt}")
kc = kapt or "A13505003"
# 2) 기본정보
for svc, op in [("AptBasisInfoServiceV4", "getAphusBassInfoV4"), ("AptBasisInfoServiceV3", "getAphusBassInfoV3"), ("AptBasisInfoService1", "getAphusBassInfo")]:
    show(f"기본정보 {svc}/{op}", B + f"{svc}/{op}", {"kaptCode": kc, "_type": "json"})
# 3) 공용관리비 (인건비 항목 예)
for svc, op in [("AptCmnuseManageCostServiceV2", "getHsmpLaborCostInfoV2"), ("AptCmnuseManageCostService", "getHsmpLaborCostInfo")]:
    show(f"공용관리비 {svc}/{op}", B + f"{svc}/{op}", {"kaptCode": kc, "searchDate": "202608", "_type": "json"})
# 4) 개별사용료 (전기료 예)
for svc, op in [("AptIndvdlzManageCostServiceV2", "getHsmpElectricityCostInfoV2"), ("AptIndvdlzManageCostService", "getHsmpElectricityCostInfo")]:
    show(f"개별사용료 {svc}/{op}", B + f"{svc}/{op}", {"kaptCode": kc, "searchDate": "202608", "_type": "json"})
# 5) 장기수선충당금
for svc, op in [("AptLtsmRepairsServiceV2", "getHsmpLtsmRepairsInfoV2"), ("AptLtsmRepairsService", "getHsmpLtsmRepairsInfo")]:
    show(f"장기수선 {svc}/{op}", B + f"{svc}/{op}", {"kaptCode": kc, "searchDate": "202608", "_type": "json"})
