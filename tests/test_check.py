import json, shutil, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import check  # noqa


def setup_module():
    check.UNITS.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "tests/fixtures/unit.json", check.UNITS / "2026999001.json")

def teardown_module():
    (check.UNITS / "2026999001.json").unlink()

META = {"house_manage_no": "2026999001", "type": "notice", "title": "테스트파크 시티 청약 일정·분양가 총정리 (10월 공고)",
        "slug": "test-park-city-cheongyak-2026-10", "description": "1순위 10월 14일, 84㎡ 최고가 6억 2,000만 원, 총 812세대 공급하는 테스트파크 시티 청약 일정을 정리했어요.",
        "labels": ["청약일정", "경기"], "keyword": "테스트파크 시티 청약 일정", "opening": "B"}

GOOD_PARA = ("테스트파크 시티 1순위 접수는 10월 14일에 해요. 특별공급은 하루 앞선 10월 13일이라고 합니다.\n\n"
             "84㎡ 최고 분양가는 6억 2,000만 원으로 나왔어요. 59㎡는 4억 8,500만 원이라고 해요.\n\n")
TABLES = ("| 구분 | 날짜 |\n| --- | --- |\n| 1순위 | 10월 14일 |\n| 발표 | 10월 21일 |\n\n"
          "| 타입 | 최고가 |\n| --- | --- |\n| 59㎡ | 4억 8,500만 원 |\n| 84㎡ | 6억 2,000만 원 |\n\n")
END = ("[청약홈 공고 원문](https://www.applyhome.co.kr/x)에서 확인할 수 있어요.\n\n"
       "> 이 글은 청약홈 공고 데이터를 바탕으로 자동 정리했어요. 신청 전에는 반드시 입주자모집공고 원문을 확인해 주세요.\n")

WORDS = "가 나 다 라 마 바 사 아 자 차 카 타 파 하 거 너 더 러".split()


def body(extra=""):
    filler = "".join(
        f"## 테스트파크 시티 {w} 항목도 확인해요\n\n"
        "총 812세대 가운데 일반공급과 특별공급 비율을 타입별로 나눠서 정리해 봤어요. "
        "계약은 11월 2일부터 11월 4일까지 진행한다고 합니다.\n\n"
        for w in WORDS)
    return GOOD_PARA + TABLES + filler + extra + END


def test_good_post_passes():
    errs = check.check_text(META, body(), [])
    assert errs == [], errs

def test_wrong_number_and_tone_fail():
    errs = check.check_text(META, body("84㎡ 최고 분양가는 7억 3,000만 원이다.\n\n"), [])
    assert any("7" in e or "73000" in e or "3000" in e for e in errs if "숫자" in e), errs
    assert any("딱딱한 말투" in e for e in errs), errs

def test_same_opening_as_previous_fails():
    errs = check.check_text(META, body(), [{"opening": "B", "title": "직전 글"}])
    assert any("시작 방식" in e for e in errs), errs
