# 공모주 뜯어보기 글쓰기 지침 (예약 작업이 실행할 때마다 이 순서대로)

블로그: https://gongmoju-breakdown.blogspot.com/ · 하루 1편 · 말투는 **해요체** 중심(가끔 합니다체)

## 0. 먼저 읽을 것
1. `rules/adsense_approval.md` 2장, `rules/writing_rules.md`의 말투 규칙, `rules/blog_portfolio.md`(아파트 청약 이야기 금지, 매수·매도 권유 금지).
2. `blogs/gongmoju/data/published.json`, `blogs/gongmoju/data/summary.json`, `blogs/gongmoju/data/ipos/*.json`.

## 1. 글감 고르기
1. 월요일이면 → **이번 주·다음 주 공모 일정 모음**(type: weekly, corp_codes에 다룬 회사들). 스팩은 따로 한 줄로만.
2. 그 외 → **공모 구조 글**(type: ipo). 스팩이 아니고(is_spac false), 청약 시작일이 오늘 이후인 회사 중 청약이 가장 빠른 곳. 이미 쓴 corp_code는 다시 쓰지 않는다. 단, 그 회사에 [발행조건확정] 신고서가 새로 들어와 공모가가 바뀌었으면 '확정 공모가' 글 1편 허용.
3. 쓸 회사가 없으면 쓰지 않고 이유만 남긴다.

> **애드센스 점검(매번 필수)**: 글감을 고른 직후 `rules/precheck.md`의 A(1~5)를 하나씩 확인한다. 하나라도 걸리면 다른 글감으로 바꾸거나 쓰지 않고 이유만 남긴다. 통과하면 이 글이 더하는 가치를 한 문장으로 머리말 `value:`에 적는다.

## 2. 글의 중심(angle): 그 회사에서 가장 두드러진 점 하나
| angle | 고르는 경우 |
| --- | --- |
| 규모 | total_rank가 상위·하위 20% 안이거나 total_vs_median_pct 절댓값이 30 이상 |
| 자금용도 | 한 항목 share_pct가 60 이상이거나 운영자금·채무상환 비중이 큼 |
| 공모가 | price_confirmed 여부, 정정 신고서 등 가격 관련 변화가 있음 |
| 주관사 | underwriting_fee_pct가 median_fee_pct와 크게 다름, 인수단 구성이 특이 |
| 회사 | 설립 연수(company_age_years), 업종이 다른 공모와 뚜렷이 다름 |
같은 종류 직전 2편과 같은 중심 세 번 연속 금지(검수가 막음).

## 3. 쓰는 법
- 제목에 **'공모주'**를 꼭 넣고, 키워드(예: "유캐스트 공모주")를 앞 25자 안에.
- 첫 문장은 그 회사의 가장 구체적인 숫자나 날짜로.
- **계산 숫자 2개 이상**: total_rank/total_rank_of, total_vs_median_pct, share_pct, underwriting_fee_pct, median_fee_pct 등. 숫자는 ipos/<corp_code>.json, summary.json에 있는 값만(검수가 막음).
- 금액은 원 단위 데이터를 억으로 바꿔 쓴다(예: 16800000000 → 168억 원). fund_matches_total이 false면 자금 금액 대신 비중(share_pct)만 쓴다.
- price_confirmed가 false면 "신고서 기준 공모가"라고 쓰고 수요예측 뒤 바뀔 수 있다고 밝힌다. report_nm에 '정정제출요구'가 있으면 일정·가격이 바뀔 수 있다고 반드시 쓴다.
- **해설 문단 1개 이상**: 숫자가 청약하려는 사람에게 무슨 뜻인지 조건을 나눠서. 권유·단정은 금지("사세요", "추천", "대박", "따상", "무조건").
- 수요예측·청약 경쟁률은 데이터에 없으므로 쓰지 않는다.
- 표 2개 이상(4열 이하). 예: 공모 개요 표, 자금 사용 표, 인수단 표, 최근 공모 규모 비교 표.
- 끝: DART 원문 링크(dart_url) + 출처 문구("공모 숫자는 DART 증권신고서에서 가져왔어요" 등, 표현은 바꿔도 됨) + "투자 판단은 투자설명서 원문을 보고 직접 하셔야 해요" 취지 문장.
- 본문 1,500자 이상, 문단 4문장 이하, 굵은 글씨 2곳 이하, 같은 어미 3문장 연속 금지.

## 4. 머리말
```
---
type: ipo
corp_code: "01705573"
title: "유캐스트 공모주 168억 원, 최근 공모 26곳 중 24번째 규모"
slug: "ucast-ipo-2026-10"
description: "50~160자"
labels: [공모 구조, 일반 기업]   # 공모 구조|공모 일정 + 일반 기업|스팩
keyword: "유캐스트 공모주"
opening: A        # A 규모 / B 청약일 / C 자금용도 / D 회사 (직전 글과 다르게)
angle: 규모
---
```

> **애드센스 점검(매번 필수)**: 검수(check)를 통과한 뒤 올리기 전에 `rules/precheck.md`의 B(6~12)를 하나씩 확인하고, 걸리는 것은 고친 뒤 검수를 다시 돌린다. 커밋 메시지 끝에 `점검: A1~5, B6~12 확인`과 value 문장을 적는다.

## 5. 검수와 올리기
1. `blogs/gongmoju/posts/pending/<오늘날짜>-<corp_code>-<type>.md`로 저장.
2. `python blogs/gongmoju/check_cli.py <파일>` 통과까지 고친다(최대 5번). 실패하면 `blogs/gongmoju/posts/held/`로 옮기고 사유를 남긴다.
3. 통과하면 commit·push → GitHub Actions(gongmoju-publish)가 발행.
4. 규칙·코드·데이터 파일은 고치지 않는다. 한 번에 1편만.
