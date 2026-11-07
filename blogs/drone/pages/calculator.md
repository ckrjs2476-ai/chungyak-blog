---
title: "드론 신고·승인·보험 확인 계산기"
slug: "calculator"
publish: true
---
기체 무게와 쓰는 곳, 날리는 장소를 고르면 기체 신고, 비행 승인, 보험 가입 의무가 있는지 법령 기준으로 바로 보여 줘요. 기준은 항공안전법·같은 법 시행령·시행규칙과 항공사업법 현행 조문이에요.

<div id="calc" style="border:1px solid #d0d7de;border-radius:8px;padding:16px;margin:1em 0;"><p><label>최대이륙중량(kg)<br><input id="w" type="number" inputmode="decimal" min="0" step="0.01" value="0.9" style="width:100%;padding:6px;box-sizing:border-box;"></label></p><p><label>어디에 쓰나요<br><select id="use" style="width:100%;padding:6px;box-sizing:border-box;"><option value="hobby">개인 취미·여가</option><option value="biz">사업(촬영·방제·측량 등 초경량비행장치사용사업)</option><option value="public">국가·지자체·공공기관 소유</option></select></label></p><p><label>어디서 날리나요<br><select id="where" style="width:100%;padding:6px;box-sizing:border-box;"><option value="open">관제권·비행금지구역 밖, 150m 미만</option><option value="ctr">관제권(공항 주변) 안</option><option value="pz">비행금지구역 안</option><option value="high">고도 150m 이상</option></select></label></p><div id="out" style="margin:.6em 0;line-height:1.8;"></div></div>

<script>(function(){var D={};function f(){var w=parseFloat(document.getElementById("w").value)||0,u=document.getElementById("use").value,p=document.getElementById("where").value;var reg=(u!="hobby")?"필요해요. 사업·공공 용도는 무게와 관계없이 신고 대상이에요.":(w>2?"필요해요. 최대이륙중량 2kg 초과예요.":"신고 대상이 아니에요. 사업에 쓰지 않는 2kg 이하 기체예요.");var apv=(p!="open")?"필요해요. 관제권·비행금지구역이나 150m 이상 고도는 무게와 관계없이 승인 대상이에요.":(w>25?"필요해요. 최대이륙중량 25kg 초과예요.":"승인 대상이 아니에요. 25kg 이하이고 관제권·비행금지구역 밖, 150m 미만이에요.");var ins=(u=="hobby")?"법으로 정한 가입 의무는 없어요.":"가입 의무가 있어요(항공사업법 제70조 제4항).";document.getElementById("out").innerHTML="<b>기체 신고</b>: "+reg+"<br><b>비행 승인</b>: "+apv+"<br><b>보험</b>: "+ins}["w","use","where"].forEach(function(i){var e=document.getElementById(i);e.addEventListener("input",f);e.addEventListener("change",f)});f()})();</script>

## 이 기준으로 판단해요

| 항목 | 기준 | 근거 |
| --- | --- | --- |
| 기체 신고 | 사업에 쓰지 않는 최대이륙중량 2kg 이하 무인동력비행장치는 신고 제외, 사업용은 무게 무관 | 항공안전법 제122조, 시행령 제24조 |
| 비행 승인 | 최대이륙중량 25kg 초과, 또는 관제권·비행금지구역·150m 이상 고도 비행 | 항공안전법 시행규칙 제308조 |
| 보험 | 초경량비행장치사용사업·대여업·레저스포츠사업, 국가·지자체·공공기관 소유 | 항공사업법 제70조 제4항 |

비행제한구역, 야간 비행, 항공 촬영 허가는 이 계산기에 넣지 않았어요. 각각 따로 정리한 글을 참고해 주세요.

신고와 승인 신청은 드론원스톱 민원서비스(drone.onestop.go.kr)에서 해요. 법령이 바뀌면 이 페이지의 기준도 고쳐요.
