"""새 블로그용 데이터 API 시험 호출. 결과는 ::notice::/::error:: 로만 남긴다(키는 출력하지 않음)."""
import os
import requests

def show(name, res):
    body = res.text[:300].replace("\n", " ")
    print(f"::notice::{name} → HTTP {res.status_code} | {body}")

key = os.environ.get("DATA_GO_KR_KEY", "")
try:
    r = requests.get("https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent",
                     params={"serviceKey": key, "LAWD_CD": "11680", "DEAL_YMD": "202609", "numOfRows": 3, "pageNo": 1}, timeout=60)
    show("전월세 실거래가", r)
except Exception as e:
    print(f"::error::전월세 실거래가 호출 실패: {type(e).__name__}")

dk = os.environ.get("OPENDART_KEY", "")
if not dk:
    print("::error::OPENDART_KEY 시크릿이 없습니다.")
else:
    try:
        r = requests.get("https://opendart.fss.or.kr/api/list.json",
                         params={"crtfc_key": dk, "bgn_de": "20260901", "end_de": "20261013", "pblntf_ty": "C", "page_count": 3}, timeout=60)
        show("OpenDART 발행공시 목록", r)
    except Exception as e:
        print(f"::error::OpenDART 호출 실패: {type(e).__name__}")
