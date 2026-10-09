# 예약 작업용 글쓰기 지침 (Claude가 실행할 때마다 이 순서대로)

목표: 애드센스 승인과 검색 상위노출. 그래서 **모든 글에 청약홈에 없는 정보(분석 숫자)**가 들어가야 한다.
공고를 옮겨 적기만 한 글은 구글이 '가치 낮은 대량 생성 글'로 볼 수 있다(구글 스팸 정책, 애드센스 거절 사유 1순위).

## 0. 실행할지 판단
1. 한국 시간(Asia/Seoul) 현재 시각을 확인한다.
2. config.json의 start_date가 null이면 아무것도 하지 않고 끝낸다(아직 가동 전).
3. 지금이 오후(12시 이후)이고 오늘 날짜가 config.json의 two_per_day_from보다 앞이면 끝낸다(그 전에는 오전 1편만).
   two_per_day_from이 없으면 start_date부터 7일이 지난 뒤부터 저녁에도 쓴다.

## 1. 준비
1. 저장소를 최신으로 받는다 (git pull).
2. 아래 파일을 모두 읽는다. 읽지 않고 쓰지 않는다.
   - rules/seo_guide.md, rules/ranking_growth.md, rules/writing_rules.md, rules/keyword_rules.md
3. data/jobs.json(오늘 후보), data/published.json(쓴 글 기록, 특히 마지막 10편의 opening과 소제목),
   data/stats/latest.json(통계)을 읽는다. jobs.json의 date가 오늘이 아니어도 그대로 쓴다.

## 2. 이번에 쓸 글 고르기 (1편)
아래 순서로 먼저 해당하는 것 하나를 쓴다.
1. 매달 1일 오전: 월간 정리(type: monthly). 이번 달 공고 단지를 지역별로 모으고, 우리가 쓴 단지 글을 모두 링크한다.
   stats의 this_month(평당가 순위, 특공 합계)를 쓴다. 이 글이 그달의 허브다.
2. 매달 2일 저녁: 지난달 결산 통계(type: stats). stats의 last_month, monthly_region_pyeong.
3. 월요일 저녁: 지난주 경쟁률 순위(type: stats). stats의 weekly_competition. 2곳 미만이면 건너뛴다.
4. 목요일 저녁: 이번 주 무순위·줍줍 모음(type: remainder). stats의 weekly_remainder. 1곳도 없으면 건너뛴다.
5. 그 밖: jobs.json을 위에서부터 보고 published.json과 posts/(pending|held|review)에 없는 첫 후보.
6. 후보가 없으면 data/queue/의 가장 오래된 예비 글을 posts/pending/으로 옮긴다
   (옮기기 전에 check.py를 다시 돌려 통과하는지 본다. 분석 데이터가 바뀌었을 수 있다).
7. 예비 글도 없으면 지역 비교 글(type: region) 또는 통계 글(type: stats)을 새로 쓴다.

## 3. 글 쓰기
### 3-1. 숫자의 근거 (이 두 곳 말고는 숫자를 쓰지 않는다)
- 원본: data/units/<HOUSE_MANAGE_NO>.json
- 분석: data/analysis/<HOUSE_MANAGE_NO>.json, data/stats/latest.json (코드가 원본으로 계산한 값)
- 주변 시세·실거래가·전매 제한·거주 의무처럼 데이터에 없는 건 쓰지 않는다. 필요하면 "공고문에서 확인해 주세요"로 안내한다.
- 분석 파일에 없는 계산(두 값의 차이, 비율 등)을 직접 하지 않는다. 필요하면 "천만 원도 안 나요"처럼 숫자 없이 표현한다.

### 3-2. 분석 숫자 (필수, 2개 이상. check.py가 확인한다)
| 글 유형 | 꼭 넣을 분석 (data/analysis 필드) |
| --- | --- |
| notice | 공급면적 3.3㎡당 분양가(types[].pyeong_price, pyeong_avg), 비슷한 단지 비교(region_price = 같은 시, region_price_wide = 같은 시·도: scope·peer_avg_pyeong·diff_pct·rank/of), 특공 비중(special_share_pct) |
| competition | 1순위 평균 경쟁률(competition.rank1_avg_rate), 마감 단계(types[].closed_at), 최종 미달(final_shortfall), 비슷한 단지 비교(region_competition) |
| score | 타입별 최저 가점(score.type_min), 비슷한 단지 커트라인 비교(region_score: peer_avg_min·diff) |
| remainder | stats.weekly_remainder의 단지별 세대수·가격·3.3㎡당 가격 비교 |
| region | 단지별 pyeong_avg 비교표, 지역 평균 |
| monthly / stats | stats의 순위·평균·합계 |
| guide | 제도 설명 + 우리 데이터 예시(최근 커트라인, 특공 물량 등) |

표현 규칙:
- pyeong_price는 "최고가 기준, 공급면적 3.3㎡당 ○만 원"으로 쓴다(만원 단위 정수).
- region_price.scope가 시·구 이름이면 "최근 6개월 ○○시 민영 단지 ○곳 평균", 시·도 이름이면 "최근 6개월 경기 ○곳 평균"처럼
  **무엇과 비교했는지**를 꼭 밝힌다. peers에 비교한 단지 이름이 있다.
- diff_pct가 음수면 "○% 낮아요", 양수면 "○% 높아요".
- 비교 대상 수(peer_count)가 적으면(2~3곳) "비교 단지가 적어 참고용"이라고 덧붙인다.

### 3-3. 데이터 읽는 법 (2026-10-07 실제 응답으로 확인)
- 금액 필드(…AMOUNT)는 만원 단위다. 62000이면 "6억 2,000만 원". LTTOT_TOP_AMOUNT는 타입별 **최고가**다.
- HOUSE_TY "084.9592A"는 "84A 타입"(전용 84㎡대)으로 쓴다. 분석 파일의 ty 값("84.9592A")은 소수점을 빼고 써도 된다.
- SUPLY_AR는 공급면적(㎡)이다. 전용면적과 헷갈리지 않게 "공급면적"이라고 밝힌다.
- 주택형별 일반공급 SUPLY_HSHLDCO, 특별공급 SPSPLY_HSHLDCO. 특공 세부는 analysis의 special_kinds.
- 경쟁률 행은 1순위 해당지역 → 1순위 기타지역 → 2순위 해당지역 → 2순위 기타지역 순서다.
  CMPET_RATE가 숫자면 그 단계에서 마감, "(△N)"이면 그 단계까지 N세대가 남음, "-"면 앞 단계에서 이미 마감.
  그래서 analysis의 closed_at(마감 단계)과 final_shortfall(2순위까지 남은 세대)을 쓰면 된다.
- 경쟁률 데이터의 SUPLY_HSHLDCO는 특공 미달분이 넘어온 뒤의 일반공급 세대수라 공고 때 숫자보다 클 수 있다.
- MVN_PREARNGE_YM "202906"은 2029년 6월 입주 예정이다.
- 가점(LWET_SCORE 등)이 "-"면 가점제가 아닌 공급(공공분양 등)이다. 숫자를 지어내지 않는다.
- CNSTRCT_ENTRPS_NM(시공사), BSNS_MBY_NM(시행사), HMPG_ADRES(분양 홈페이지)도 쓸 수 있다.
  전화번호는 쓰지 않는다(검수기가 숫자로 오인).

### 3-4. 쓰는 법
1. 규칙 파일대로 쓴다: 해요체·합니다체, 모바일 문단, 직전 글과 다른 시작 방식(opening A~D), 새 소제목.
2. 청약홈 원문 링크는 PBLANC_URL, 없으면 https://www.applyhome.co.kr.
3. 같은 단지의 이전 글(published.json의 url)이 있으면 본문에서 설명하는 문구로 링크한다.
   이번 달 월간 정리 글, 관련 통계 글이 있으면 본문 끝에서 링크한다.
   ('이 단지 다른 글' 목록과 맨 위 요약 카드는 발행 단계에서 코드가 붙인다. 카드와 같은 표를 본문에 반복하지 않는다.)
4. 이미지는 넣지 않는다. 다른 사이트 이미지(조감도·평면도)는 저작권 때문에 절대 가져오지 않는다.
5. 파일 형식:

```
---
house_manage_no: "2026000123"      # 단지 1곳 글(notice, competition, score)
# house_manage_nos: ["...", "..."]  # 여러 단지 글(remainder, region, monthly, stats, guide). stats·guide는 없어도 됨
type: notice            # notice | competition | score | remainder | region | monthly | stats | guide
title: "OO단지 청약 일정·분양가 총정리 (10월 공고)"
slug: "oo-danji-cheongyak-schedule-2026-10"   # 영문 소문자·숫자·하이픈
description: "검색 결과에 보일 설명 50~160자. 날짜·가격·분석 숫자를 모아서. 한 줄로."
labels: [청약일정, 경기]   # 허용 목록에서 2~3개
keyword: "OO단지 청약 일정"
opening: B              # A 분양가 / B 접수일 / C 비슷한 단지와의 차이 / D 신청 자격
---
본문(마크다운)
```

## 4. 검수
1. `python src/check.py posts/pending/<파일>` 을 실행한다.
2. 실패 사유를 모두 고치고 다시 실행한다. 통과할 때까지 반복한다(최대 5번).
3. 5번 안에 못 고치면 그 글을 posts/held/로 옮기고 사유를 적는다.
4. 사람말투-글쓰기 규칙도 스스로 한 번 더 점검한다.

## 5. 올리기
1. 파일 이름: posts/pending/YYYY-MM-DD-<HOUSE_MANAGE_NO 또는 주제>-<type>.md
2. git add, commit("post: 제목"), push. push되면 GitHub Actions가 다시 검수한 뒤 Blogger에 올린다.

## 6. 예비 글 채우기 (저녁 실행에서만)
data/queue/의 예비 글이 14편보다 적으면 1편을 더 써서 data/queue/에 넣는다. 같은 검수를 통과해야 한다.
- 우선순위: 지역 비교(region) → 통계(stats) → 청약 가이드(guide).
- 분량을 채우려는 글은 쓰지 않는다. 분석 숫자가 2개 이상 나오지 않는 주제면 쓰지 않는다.

청약 가이드(type: guide)는 자동 발행하지 않는다.
- 주 1편까지. posts/pending/에 올리면 발행 단계에서 posts/review/로 옮겨져 사용자 검토를 기다린다.
  사용자가 확인하면 머리말에 `approved: true`를 붙여 posts/pending/으로 다시 옮긴다.
- 제도 설명만 하지 말고 우리 데이터 예시(최근 커트라인, 특공 물량 등)를 엮는다.
- 제도 숫자(가점 항목 점수, 소득·자산 기준 등)는 확실하지 않으면 쓰지 않는다.
- 본문 첫 부분과 끝에 청약홈(https://www.applyhome.co.kr) 링크와 아래 문구를 넣는다:
  > 제도 기준은 바뀔 수 있어요. 정확한 내용은 청약홈 홈페이지를 참고해 주세요.

## 하지 않는 것
- 규칙 파일·검수 코드 수정, config.json의 mode 변경, 다른 파일 삭제
- 한 번 실행에 본 글 2편 이상 올리기
