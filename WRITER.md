# 예약 작업용 글쓰기 지침 (Claude가 실행할 때마다 이 순서대로)

## 0. 실행할지 판단
1. 한국 시간(Asia/Seoul) 현재 시각을 확인한다.
2. config.json의 start_date가 null이면 아무것도 하지 않고 끝낸다(아직 가동 전).
3. start_date부터 7일이 안 지났고 지금이 오후(12시 이후)면 끝낸다. 첫 주는 오전 1편만.

## 1. 준비
1. 저장소를 최신으로 받는다 (git pull).
2. 아래 파일을 모두 읽는다. 읽지 않고 쓰지 않는다.
   - rules/seo_guide.md, rules/ranking_growth.md, rules/writing_rules.md, rules/keyword_rules.md
3. data/jobs.json(오늘 후보), data/published.json(쓴 글 기록, 특히 마지막 10편의 opening과 소제목)을 읽는다.
   jobs.json의 date가 오늘이 아니어도 그대로 쓴다(데이터 받기가 늦어진 경우).

## 2. 이번에 쓸 글 고르기 (1편)
0. 매달 1일 오전 실행이면 월간 정리 글(type: monthly)을 먼저 쓴다.
   - 이번 달 접수 일정이 있는 단지를 data/units/에서 모아 지역별로 정리하고,
     우리가 이미 쓴 단지 글(published.json의 url)은 모두 링크한다.
   - house_manage_nos에 다룬 단지 번호를 모두 적는다.
   - 이 글이 '허브'가 된다. 그달의 단지 글은 본문 끝에서 이 허브 글로 링크한다.
1. jobs.json을 위에서부터 보고, published.json과 posts/pending·posts/held에 없는 첫 후보를 고른다.
2. 후보가 없으면 data/queue/에서 가장 오래된 예비 글 1편을 posts/pending/으로 옮기고 3장으로 건너뛴다.
3. 예비 글도 없으면 data/units/ 데이터로 지역 모음 또는 단지 비교 글을 새로 쓴다(type: region).

## 3. 글 쓰기
1. data/units/<HOUSE_MANAGE_NO>.json만을 숫자의 근거로 쓴다. 데이터에 없는 숫자는 쓰지 않는다.
   (주변 시세처럼 데이터에 없는 정보가 필요하면 그 문단을 빼고 다른 선택 요소를 쓴다.)
2. 금액 필드(…AMOUNT)는 만원 단위다. 62000이면 "6억 2,000만 원"으로 쓴다.
   데이터 읽는 법 (2026-10-07 실제 응답으로 확인):
   - HOUSE_TY "084.0000A"는 "84A 타입"(전용 84㎡), "084.9500C"는 "84.95C 타입"으로 쓴다.
   - SUPLY_AR는 공급면적(㎡)이다. 전용면적과 헷갈리지 않게 "공급면적"이라고 밝힌다.
   - 주택형별 일반공급은 SUPLY_HSHLDCO, 특별공급은 SPSPLY_HSHLDCO다. 특공 세부(NWBB 신생아, NWWDS 신혼부부,
     LFE_FRST 생애최초, MNYCH 다자녀, OLD_PARNTS_SUPORT 노부모, INSTT_RECOMEND 기관추천)도 쓸 수 있다.
   - CMPET_RATE가 "(△123)"처럼 나오면 경쟁률이 아니라 **미달 123세대**라는 뜻이다. "123세대가 미달됐다고 해요"로 쓴다.
   - 경쟁률 데이터의 RESIDE_SENM은 해당지역/기타경기/기타지역, SUBSCRPT_RANK_CODE는 1순위·2순위다.
   - MVN_PREARNGE_YM "202906"은 2029년 6월 입주 예정이다.
   - 가점(LWET_SCORE 등)이 "-"면 가점제가 아닌 공급(공공분양 등)이다. 숫자를 지어내지 않는다.
   - CNSTRCT_ENTRPS_NM(시공사), BSNS_MBY_NM(시행사), MDHS_TELNO(분양 문의 전화), HMPG_ADRES(분양 홈페이지)도 쓸 수 있다.
3. 규칙 파일대로 쓴다: 해요체·합니다체, 모바일 문단, 직전 글과 다른 시작 방식(opening A~D), 새 소제목.
4. 청약홈 원문 링크는 데이터의 PBLANC_URL을 쓰고, 없으면 https://www.applyhome.co.kr 을 쓴다.
5. 같은 단지의 이전 글(published.json의 url)이 있으면 본문에 설명적인 문구로 링크한다.
   이번 달 월간 정리 글이 있으면 본문 끝에서 그 글로 링크한다.
   ('이 단지 다른 글' 목록과 맨 위 요약 카드는 발행 단계에서 코드가 자동으로 붙이니 본문에 따로 쓰지 않는다.
   요약 카드에 일정·분양가가 이미 있으므로, 본문 첫 부분은 카드와 같은 표를 반복하지 말고 문장으로 풀어 쓴다.)
6. 이미지는 넣지 않는다. 다른 사이트 이미지(조감도·평면도)는 저작권 때문에 절대 가져오지 않는다.
7. 파일 형식:

```
---
house_manage_no: "2026000123"
type: notice            # notice | competition | score | remainder | monthly | region | guide
title: "OO단지 청약 일정·분양가 총정리 (10월 공고)"
slug: "oo-danji-cheongyak-schedule-2026-10"   # 영문 소문자·숫자·하이픈
description: "검색 결과에 보일 설명 50~160자. 날짜와 가격을 모아서."
labels: [청약일정, 경기]   # 허용 목록에서 2~3개
keyword: "OO단지 청약 일정"
opening: B              # A 분양가 / B 접수일 / C 시세 차이 / D 신청 자격
# 여러 단지를 다루는 글(monthly, region)은 house_manage_no 대신 아래처럼 목록으로 적는다 (숫자 검수용)
# house_manage_nos: ["2026000123", "2026000124"]
---
본문(마크다운)
```

## 4. 검수
1. `python src/check.py posts/pending/<파일>` 을 실행한다.
2. 실패 사유를 모두 고치고 다시 실행한다. 통과할 때까지 반복한다(최대 5번).
3. 5번 안에 못 고치면 그 글을 posts/held/로 옮기고 사유를 적는다.
4. 사람말투-글쓰기 24개 항목도 스스로 한 번 더 점검한다.

## 5. 올리기
1. 파일 이름: posts/pending/YYYY-MM-DD-<HOUSE_MANAGE_NO 또는 지역>-<type>.md
2. git add, commit("post: 제목"), push. push되면 GitHub Actions가 검수 후 Blogger에 올린다.

## 6. 예비 글 채우기 (저녁 실행에서만)
data/queue/의 예비 글이 14편보다 적으면, 데이터로 만들 수 있는 예비 글 1편을 더 써서
data/queue/에 넣는다(지역 모음, 단지 비교, 지난달 결산). 같은 검수를 통과해야 한다.
기초 가이드(type: guide, 제도 설명)도 자동으로 쓴다. 단, 다음을 지킨다.
- 주 1편 정도. 이미 쓴 가이드 주제(published.json)는 다시 쓰지 않는다.
- 제도 숫자(가점 항목, 소득·자산 기준 등)는 바뀔 수 있으니 확실하지 않은 숫자는 쓰지 않고
  "정확한 기준은 청약홈 홈페이지에서 확인해 주세요"로 안내한다.
- 본문 첫 부분과 끝에 청약홈(https://www.applyhome.co.kr) 링크와 아래 문구를 넣는다:
  > 제도 기준은 바뀔 수 있어요. 정확한 내용은 청약홈 홈페이지를 참고해 주세요.

## 하지 않는 것
- 규칙 파일 수정, config.json의 mode 변경, 다른 파일 삭제
- 한 번 실행에 본 글 2편 이상 올리기
