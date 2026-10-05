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
1. jobs.json을 위에서부터 보고, published.json과 posts/pending·posts/held에 없는 첫 후보를 고른다.
2. 후보가 없으면 data/queue/에서 가장 오래된 예비 글 1편을 posts/pending/으로 옮기고 3장으로 건너뛴다.
3. 예비 글도 없으면 data/units/ 데이터로 지역 모음 또는 단지 비교 글을 새로 쓴다(type: region).

## 3. 글 쓰기
1. data/units/<HOUSE_MANAGE_NO>.json만을 숫자의 근거로 쓴다. 데이터에 없는 숫자는 쓰지 않는다.
   (주변 시세처럼 데이터에 없는 정보가 필요하면 그 문단을 빼고 다른 선택 요소를 쓴다.)
2. 금액 필드(…AMOUNT)는 만원 단위다. 62000이면 "6억 2,000만 원"으로 쓴다.
3. 규칙 파일대로 쓴다: 해요체·합니다체, 모바일 문단, 직전 글과 다른 시작 방식(opening A~D), 새 소제목.
4. 청약홈 원문 링크는 데이터의 PBLANC_URL을 쓰고, 없으면 https://www.applyhome.co.kr 을 쓴다.
5. 같은 단지의 이전 글(published.json의 url)이 있으면 본문에 설명적인 문구로 링크한다.
6. 파일 형식:

```
---
house_manage_no: "2026000123"
type: notice            # notice | competition | score | remainder | monthly | region
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
기초 가이드(제도 설명)는 자동으로 쓰지 않는다. 사람이 확인한 뒤 넣는다.

## 하지 않는 것
- 규칙 파일 수정, config.json의 mode 변경, 다른 파일 삭제
- 한 번 실행에 본 글 2편 이상 올리기
