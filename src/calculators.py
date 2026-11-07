"""블로그별 계산기 고정 페이지(slug calculator)를 데이터로 만든다 (rules/unique_value.md 8장).

- 독자가 직접 넣어 보는 도구라 원자료 사이트에 없는 쓸모가 생긴다.
- 글쓴이는 capture로 이 페이지에 조건을 바꿔 넣고 결과 화면을 찍어 "제가 계산기에 ~을 넣어 봤어요"를 쓴다(capture_guide 3장).
- 비교 기준값은 모두 데이터 파일에 있는 값을 그대로 넣는다(판정·권유 문구 없음).
실행: python src/rankings.py 가 함께 부른다(매주 월요일). 페이지 올리기는 publish.py --pages.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOX = 'style="border:1px solid #d0d7de;border-radius:8px;padding:16px;margin:1em 0;"'
FLD = 'style="width:100%;padding:6px;box-sizing:border-box;"'


def _load(p: Path):
    return json.loads(p.read_text("utf-8")) if p.exists() else {}


def _front(title: str) -> list[str]:
    return ["---", f'title: "{title}"', 'slug: "calculator"', "publish: true", "---"]


def _js(data, body: str) -> str:
    return "<script>(function(){var D=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";" + body + "})();</script>"


def jeonse() -> str:
    r = _load(ROOT / "blogs/jeonse/data/ranking.json")
    regs = sorted(r.get("regions", []), key=lambda x: x["name"])
    data = {"avg": r.get("avg_ratio84"), "n": len(regs), "r": [[x["lawd"], x["name"], x["ratio84"], x["rank"]] for x in regs]}
    opts = "".join(f'<option value="{x["lawd"]}">{x["name"]}</option>' for x in regs)
    form = (f'<div id="calc" {BOX}>'
            f'<p><label>매매가(만 원)<br><input id="sale" type="number" inputmode="numeric" min="0" placeholder="예: 50000" {FLD}></label></p>'
            f'<p><label>전세 보증금(만 원)<br><input id="dep" type="number" inputmode="numeric" min="0" placeholder="예: 35000" {FLD}></label></p>'
            f'<p><label>비교할 시군구<br><select id="reg" {FLD}>{opts}</select></label></p>'
            '<p id="out" style="font-size:18px;font-weight:bold;margin:.6em 0;"></p><p id="cmp" style="margin:0;line-height:1.7;"></p></div>')
    js = _js(data, (
        'function v(i){return parseFloat(document.getElementById(i).value)||0}'
        'function f(){var s=v("sale"),d=v("dep"),o=document.getElementById("out"),c=document.getElementById("cmp");'
        'if(!s||!d){o.textContent="매매가와 전세 보증금을 넣으면 전세가율이 나옵니다.";c.textContent="";return}'
        'var p=Math.round(d/s*1000)/10;o.textContent="전세가율: "+p+"%";'
        'var g=document.getElementById("reg").value,x=D.r.filter(function(a){return a[0]==g})[0];'
        'var t=x?(x[1]+" 84㎡ 전세가율은 "+x[2]+"%("+D.n+"개 시군구 중 높은 순 "+x[3]+"위)로, 입력한 값이 "+Math.abs(Math.round((p-x[2])*10)/10)+"%p "+(p>=x[2]?"높습니다":"낮습니다")+". "):"";'
        'var b=D.r.filter(function(a){return a[2]<=p}).length;'
        'c.textContent=t+"전국 평균 "+D.avg+"%와 비교하면 "+(p>=D.avg?"높고":"낮고")+", "+D.n+"개 시군구 가운데 "+b+"곳의 전세가율이 이 값 이하입니다."}'
        '["sale","dep","reg"].forEach(function(i){var e=document.getElementById(i);e.addEventListener("input",f);e.addEventListener("change",f)});f()'))
    return "\n".join(_front("전세가율 계산기") + [
        "매매가와 전세 보증금을 넣으면 전세가율을 계산하고, 고른 시군구의 84㎡ 전세가율과 전국 시군구 분포에 바로 견줘 봅니다. "
        f"비교 기준은 {r.get('updated', '')} 집계 국토교통부 실거래가입니다.", "", form, "", js, "",
        "## 전세가율은 이렇게 계산합니다", "",
        "전세가율은 전세 보증금을 매매가로 나눈 비율입니다. 같은 단지·같은 면적의 최근 매매 실거래가를 넣어야 의미 있는 값이 나옵니다.",
        "", "비교 기준인 시군구 전세가율은 전용 84㎡ 전세 실거래 중앙값을 매매 실거래 중앙값으로 나눈 값입니다. "
        "단지마다 차이가 커서, 시군구 값은 동네 전체의 흐름으로만 보시는 게 맞습니다.", "",
        "계약 전에는 등기부등본의 선순위 채권, 해당 단지 최근 실거래를 함께 확인해 주세요. 시군구별 전체 순위는 순위표 페이지에 있습니다.", ""])


def gwanribi() -> str:
    s = _load(ROOT / "blogs/gwanribi/data/summary.json")
    regs = sorted(s.get("regions", []), key=lambda x: x["name"])
    data = {"n": len(regs), "r": [[x["lawd"], x["name"], x["median_total_m2"], x["rank_median_total_m2"], str(x.get("ym", ""))] for x in regs]}
    opts = "".join(f'<option value="{x["lawd"]}">{x["name"]}</option>' for x in regs)
    form = (f'<div id="calc" {BOX}>'
            f'<p><label>이번 달 관리비 합계(원)<br><input id="fee" type="number" inputmode="numeric" min="0" placeholder="예: 250000" {FLD}></label></p>'
            f'<p><label>관리면적(㎡, 고지서에 적힌 면적)<br><input id="area" type="number" inputmode="decimal" min="0" placeholder="예: 84" {FLD}></label></p>'
            f'<p><label>비교할 시군구<br><select id="reg" {FLD}>{opts}</select></label></p>'
            '<p id="out" style="font-size:18px;font-weight:bold;margin:.6em 0;"></p><p id="cmp" style="margin:0;line-height:1.7;"></p></div>')
    js = _js(data, (
        'function v(i){return parseFloat(document.getElementById(i).value)||0}'
        'function f(){var a=v("fee"),m=v("area"),o=document.getElementById("out"),c=document.getElementById("cmp");'
        'if(!a||!m){o.textContent="관리비 합계와 관리면적을 넣으면 ㎡당 관리비가 나와요.";c.textContent="";return}'
        'var p=Math.round(a/m);o.textContent="우리 집 ㎡당 관리비: "+p.toLocaleString()+"원";'
        'var g=document.getElementById("reg").value,x=D.r.filter(function(z){return z[0]==g})[0];'
        'var t=x?(x[1]+" 단지들의 ㎡당 관리비 중앙값은 "+x[2].toLocaleString()+"원("+x[4].slice(0,4)+"년 "+parseInt(x[4].slice(4,6),10)+"월 부과분, "+D.n+"개 시군구 중 높은 순 "+x[3]+"위)이고, 입력한 값은 그보다 "+Math.abs(p-x[2]).toLocaleString()+"원 "+(p>=x[2]?"높아요":"낮아요")+". "):"";'
        'var b=D.r.filter(function(z){return z[2]<=p}).length;'
        'c.textContent=t+D.n+"개 시군구 가운데 "+b+"곳의 중앙값이 이 값 이하예요."}'
        '["fee","area","reg"].forEach(function(i){var e=document.getElementById(i);e.addEventListener("input",f);e.addEventListener("change",f)});f()'))
    return "\n".join(_front("우리 집 ㎡당 관리비 계산기") + [
        "고지서의 관리비 합계와 관리면적을 넣으면 ㎡당 관리비를 계산하고, 고른 시군구 단지들의 중앙값과 전국 시군구 분포에 바로 견줘 봐요. "
        f"비교 기준은 K-apt 공개 관리비를 {s.get('updated', '')}에 집계한 값이에요.", "", form, "", js, "",
        "## 비교 기준은 이렇게 만들었어요", "",
        "시군구 중앙값은 K-apt에 관리비를 공개한 단지마다 공용관리비, 개별사용료, 장기수선충당금을 더해 관리면적 1㎡당으로 나눈 뒤, 가운데 값을 고른 거예요.",
        "", "고지서 합계에 주차비나 커뮤니티 이용료 같은 항목이 따로 들어 있으면 값이 커질 수 있어요. 겨울철 난방비가 들어간 달은 다른 달보다 높게 나와요.",
        "", "시군구별 전체 순위는 순위표 페이지에, 단지별 자세한 비교는 지역 글에 있어요.", ""])


def gongmoju() -> str:
    s = _load(ROOT / "blogs/gongmoju/data/summary.json")
    ipos = [x for x in s.get("ipos", []) if x.get("price")]
    data = {"n": sum(1 for x in ipos if x.get("total_rank")), "med": s.get("median_total_eok"),
            "r": [[x["corp_code"], x["corp_name"], x["price"], x["subscription"], x.get("total_rank"), round(x["total"] / 1e8, 1)] for x in ipos]}
    opts = "".join(f'<option value="{x["corp_code"]}">{x["corp_name"]} ({x["subscription"]})</option>' for x in ipos)
    form = (f'<div id="calc" {BOX}>'
            f'<p><label>공모 기업<br><select id="co" {FLD}>{opts}</select></label></p>'
            f'<p><label>청약할 주식 수(주)<br><input id="qty" type="number" inputmode="numeric" min="0" value="10" {FLD}></label></p>'
            f'<p><label>증거금률(%, 증권사 공고 확인)<br><input id="rate" type="number" inputmode="numeric" min="0" max="100" value="50" {FLD}></label></p>'
            '<p id="out" style="font-size:18px;font-weight:bold;margin:.6em 0;"></p><p id="cmp" style="margin:0;line-height:1.7;"></p></div>')
    js = _js(data, (
        'function v(i){return parseFloat(document.getElementById(i).value)||0}'
        'function f(){var g=document.getElementById("co").value,x=D.r.filter(function(z){return z[0]==g})[0];if(!x)return;'
        'var q=v("qty"),r=v("rate"),w=Math.round(x[2]*q*r/100);'
        'document.getElementById("out").textContent="필요한 증거금: "+w.toLocaleString()+"원";'
        'document.getElementById("cmp").textContent=x[1]+" 공모가 "+x[2].toLocaleString()+"원 × "+q+"주 × 증거금률 "+r+"%로 계산했어요. 청약 금액 전체는 "+(x[2]*q).toLocaleString()+"원이에요. "'
        '+(x[4]?"공모 규모는 "+x[5].toLocaleString()+"억 원으로 최근 스팩을 뺀 "+D.n+"곳 가운데 큰 순서로 "+x[4]+"위(중앙값 "+D.med+"억 원)예요.":"기업인수목적회사(스팩)라 공모 규모 순위에서는 뺐어요.")}'
        '["co","qty","rate"].forEach(function(i){var e=document.getElementById(i);e.addEventListener("input",f);e.addEventListener("change",f)});f()'))
    return "\n".join(_front("공모주 청약 증거금 계산기") + [
        "기업과 청약할 주식 수를 고르면 넣어야 할 청약 증거금을 계산하고, 그 기업의 공모 규모가 최근 공모 기업 가운데 몇 위인지 함께 보여 줘요. "
        f"공모가는 DART 증권신고서 기준이고 {s.get('updated', '')}에 집계했어요.", "", form, "", js, "",
        "## 증거금은 이렇게 계산해요", "",
        "청약 증거금은 공모가에 청약 주식 수를 곱한 금액에 증거금률을 곱한 돈이에요. 증거금률과 최소 청약 주식 수는 주관 증권사 공고에서 정하니, 청약 전에 꼭 확인해 주세요.",
        "", "공모가가 아직 희망 범위로만 나와 있는 기업은 확정 공모가가 나오면 다시 계산해서 갱신해요. 배정 주식 수는 경쟁률에 따라 정해져서 이 계산기로는 알 수 없어요.",
        "", "기업마다 자금 사용 계획과 구조는 개별 글에, 공모 규모 전체 순위는 순위표 페이지에 정리했어요.", ""])


def drone() -> str:
    form = (f'<div id="calc" {BOX}>'
            f'<p><label>최대이륙중량(kg)<br><input id="w" type="number" inputmode="decimal" min="0" step="0.01" value="0.9" {FLD}></label></p>'
            f'<p><label>어디에 쓰나요<br><select id="use" {FLD}><option value="hobby">개인 취미·여가</option>'
            '<option value="biz">사업(촬영·방제·측량 등 초경량비행장치사용사업)</option>'
            '<option value="public">국가·지자체·공공기관 소유</option></select></label></p>'
            f'<p><label>어디서 날리나요<br><select id="where" {FLD}><option value="open">관제권·비행금지구역 밖, 150m 미만</option>'
            '<option value="ctr">관제권(공항 주변) 안</option><option value="pz">비행금지구역 안</option>'
            '<option value="high">고도 150m 이상</option></select></label></p>'
            '<div id="out" style="margin:.6em 0;line-height:1.8;"></div></div>')
    js = _js({}, (
        'function f(){var w=parseFloat(document.getElementById("w").value)||0,u=document.getElementById("use").value,p=document.getElementById("where").value;'
        'var reg=(u!="hobby")?"필요해요. 사업·공공 용도는 무게와 관계없이 신고 대상이에요.":(w>2?"필요해요. 최대이륙중량 2kg 초과예요.":"신고 대상이 아니에요. 사업에 쓰지 않는 2kg 이하 기체예요.");'
        'var apv=(p!="open")?"필요해요. 관제권·비행금지구역이나 150m 이상 고도는 무게와 관계없이 승인 대상이에요.":(w>25?"필요해요. 최대이륙중량 25kg 초과예요.":"승인 대상이 아니에요. 25kg 이하이고 관제권·비행금지구역 밖, 150m 미만이에요.");'
        'var ins=(u=="hobby")?"법으로 정한 가입 의무는 없어요.":"가입 의무가 있어요(항공사업법 제70조 제4항).";'
        'document.getElementById("out").innerHTML="<b>기체 신고</b>: "+reg+"<br><b>비행 승인</b>: "+apv+"<br><b>보험</b>: "+ins}'
        '["w","use","where"].forEach(function(i){var e=document.getElementById(i);e.addEventListener("input",f);e.addEventListener("change",f)});f()'))
    return "\n".join(_front("드론 신고·승인·보험 확인 계산기") + [
        "기체 무게와 쓰는 곳, 날리는 장소를 고르면 기체 신고, 비행 승인, 보험 가입 의무가 있는지 법령 기준으로 바로 보여 줘요. "
        "기준은 항공안전법·같은 법 시행령·시행규칙과 항공사업법 현행 조문이에요.", "", form, "", js, "",
        "## 이 기준으로 판단해요", "",
        "| 항목 | 기준 | 근거 |", "| --- | --- | --- |",
        "| 기체 신고 | 사업에 쓰지 않는 최대이륙중량 2kg 이하 무인동력비행장치는 신고 제외, 사업용은 무게 무관 | 항공안전법 제122조, 시행령 제24조 |",
        "| 비행 승인 | 최대이륙중량 25kg 초과, 또는 관제권·비행금지구역·150m 이상 고도 비행 | 항공안전법 시행규칙 제308조 |",
        "| 보험 | 초경량비행장치사용사업·대여업·레저스포츠사업, 국가·지자체·공공기관 소유 | 항공사업법 제70조 제4항 |",
        "", "비행제한구역, 야간 비행, 항공 촬영 허가는 이 계산기에 넣지 않았어요. 각각 따로 정리한 글을 참고해 주세요.",
        "", "신고와 승인 신청은 드론원스톱 민원서비스(drone.onestop.go.kr)에서 해요. 법령이 바뀌면 이 페이지의 기준도 고쳐요.", ""])


def write_all() -> list[str]:
    out = []
    for key, fn in (("jeonse", jeonse), ("gwanribi", gwanribi), ("gongmoju", gongmoju), ("drone", drone)):
        p = ROOT / "blogs" / key / "pages" / "calculator.md"
        p.write_text(fn(), "utf-8")
        out.append(f"{key}: calculator.md")
    return out


if __name__ == "__main__":
    print("\n".join(write_all()))
