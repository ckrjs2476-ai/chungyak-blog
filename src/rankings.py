"""블로그마다 매달 갱신하는 '순위표' 고정 페이지(허브)를 데이터로 만든다 → <블로그>/pages/ranking.md.
모든 글 끝에서 이 페이지로 링크한다(publish.method_link). 숫자는 데이터 파일 값 그대로 옮긴다.
4주·12주 변화 칸은 우리 시간 기록(src/history.py)이 그만큼 쌓이면 자동으로 생긴다.
실행: python src/rankings.py → 그다음 블로그별 python src/publish.py --pages
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KST = timezone(timedelta(hours=9))


def _load(p: Path):
    return json.loads(p.read_text("utf-8")) if p.exists() else {}


def won(manwon) -> str:
    """만 원 → '2억 9,000만 원'."""
    v = int(round(float(manwon)))
    eok, man = divmod(v, 10000)
    if eok and man:
        return f"{eok}억 {man:,}만 원"
    return f"{eok}억 원" if eok else f"{man:,}만 원"


def chg(changes: dict, ent: str, metric: str, unit: str = "", digits: int = 1) -> str:
    c = ((changes.get(ent) or {}).get(metric) or {}).get("4주")
    if not c:
        return "-"
    d = c["diff"]
    sign = "+" if d > 0 else ""
    return f"{sign}{d:,.{digits}f}{unit}" if digits else f"{sign}{int(d):,}{unit}"


def page(title: str, intro: list[str], tables: list[str], outro: list[str]) -> str:
    return "\n".join(["---", f'title: "{title}"', 'slug: "ranking"', "publish: true", "---",
                      *intro, "", *tables, "", *outro, ""])


def jeonse(now: str) -> str:
    r = _load(ROOT / "blogs/jeonse/data/ranking.json")
    ch = _load(ROOT / "data/history/jeonse_changes.json")
    has_hist = bool(ch)
    head = "| 순위 | 시군구 | 84㎡ 전세가율 | 전세 중앙값 | 매매 중앙값 | 최근 3개월 전세 변화 |" + (" 4주 전 대비 전세가율 |" if has_hist else "")
    sep = "| --- | --- | --- | --- | --- | --- |" + (" --- |" if has_hist else "")
    rows = [head, sep]
    for x in r.get("regions", []):
        row = (f"| {x['rank']} | {x['name']} | {x['ratio84']}% | {won(x['jeonse_median84'])} | {won(x['sale_median84'])} | "
               f"{x['jeonse_change_pct']:+}% |")
        if has_hist:
            row += f" {chg(ch, x['lawd'], 'ratio84', '%p')} |"
        rows.append(row)
    return page("전국 시군구 아파트 전세가율 순위표", [
        f"국토교통부 아파트 전월세·매매 실거래 자료를 기준으로 전용 84㎡ 전세 중앙값을 매매 중앙값으로 나눈 전세가율 순위입니다. "
        f"{r.get('updated', now)} 기준 {r.get('count', len(r.get('regions', [])))}개 시군구를 높은 순서로 세웠고, 전체 평균은 {r.get('avg_ratio84')}%입니다.",
        "", "매달 다시 계산해 이 페이지를 갱신합니다. 지역마다 자세한 해설은 블로그 글에 있습니다.", "",
        "## 시군구별 전세가율 순위"], rows,
        ["전세가율이 높을수록 매매가에 비해 전세 보증금이 크다는 뜻입니다. 계약 전에는 해당 단지의 실거래와 등기부를 직접 확인해 주세요.",
         "", "계산 방법은 '전세가율은 이렇게 계산합니다' 페이지에 있습니다."])


def gwanribi(now: str) -> str:
    s = _load(ROOT / "blogs/gwanribi/data/summary.json")
    ch = _load(ROOT / "data/history/gwanribi_changes.json")
    has_hist = bool(ch)
    head = "| 순위 | 시군구 | 기준 월 | 단지 수 | ㎡당 관리비 중앙값 | ㎡당 공용관리비 중앙값 |" + (" 4주 전 대비 |" if has_hist else "")
    sep = "| --- | --- | --- | --- | --- | --- |" + (" --- |" if has_hist else "")
    rows = [head, sep]
    for x in s.get("regions", []):
        ym = str(x.get("ym", ""))
        row = (f"| {x['rank_median_total_m2']} | {x['name']} | {ym[:4]}년 {int(ym[4:6])}월 | {x['n_complex']}곳 | "
               f"{x['median_total_m2']:,}원 | {x['median_common_m2']:,}원 |")
        if has_hist:
            row += f" {chg(ch, x['lawd'], 'median_total_m2', '원', 0)} |"
        rows.append(row)
    return page("시군구 아파트 관리비 순위표", [
        f"공동주택관리정보시스템(K-apt)에 단지가 공개한 관리비를 관리면적 1㎡당으로 나눠, 시군구마다 중앙값을 비교한 표예요. "
        f"{s.get('updated', now)} 기준 {len(s.get('regions', []))}개 시군구를 ㎡당 관리비가 높은 순서로 세웠어요.",
        "", "매달 K-apt 새 자료가 나오면 다시 계산해서 갱신해요. 단지별 자세한 비교는 지역 글에 있어요.", "",
        "## 시군구별 ㎡당 관리비 순위"], rows,
        ["㎡당 값이라 집 크기가 달라도 비교할 수 있어요. 우리 집 관리비는 고지서의 관리면적으로 나눠 보면 이 표와 바로 견줄 수 있어요.",
         "", "자료를 모으는 중인 시군구는 차례로 표에 더해져요."])


def gongmoju(now: str) -> str:
    s = _load(ROOT / "blogs/gongmoju/data/summary.json")
    rows = ["| 순위 | 회사 | 청약일 | 공모가 | 공모 규모 |", "| --- | --- | --- | --- | --- |"]
    for x in s.get("ipos", []):
        eok = round(x["total"] / 1e8, 1)
        rows.append(f"| {x['total_rank']} | {x['corp_name']} | {x['subscription']} | {x['price']:,}원 | {eok:,}억 원 |")
    return page("최근 공모주 규모 순위표", [
        f"DART에 증권신고서가 들어온 최근 {s.get('days')}일 공모 {s.get('count')}곳(스팩 제외)을 공모 규모 순서로 세운 표예요. "
        f"{s.get('updated', now)} 기준이고, 공모 규모 중앙값은 {s.get('median_total_eok')}억 원이에요.",
        "", "새 증권신고서가 들어오면 다시 계산해서 갱신해요. 회사마다 자금 사용 계획과 구조는 개별 글에 정리했어요.", "",
        "## 공모 규모 순위"], rows,
        ["공모 규모는 공모가에 공모 주식 수를 곱한 금액이에요. 청약 전에는 투자설명서 원문을 꼭 확인해 주세요."])


def cheongyak(now: str) -> str:
    st = _load(ROOT / "data/stats/latest.json")
    mp = st.get("monthly_region_pyeong") or {}
    months = sorted(mp)[-3:]
    last = months[-1] if months else ""
    regions = sorted({r for m in months for r in mp[m]},
                     key=lambda r: -((mp.get(last, {}).get(r) or {}).get("avg_pyeong") or 0))  # 이번 달 평균이 높은 순
    rows = ["| 지역 | " + " | ".join(f"{m[:4]}년 {int(m[5:])}월 평균 (단지 수)" for m in months) + " |",
            "| --- |" + " --- |" * len(months)]
    for reg in regions:
        cells = []
        for m in months:
            v = mp[m].get(reg)
            cells.append(f"{v['avg_pyeong']:,}만 원 ({v['count']}곳)" if v else "-")
        rows.append(f"| {reg} | " + " | ".join(cells) + " |")
    cut = ["", "## 최근 90일 당첨 가점 최고점", "", "| 단지 | 지역 | 최고 가점 (주택형) |", "| --- | --- | --- |"]
    for c in st.get("score_cutoffs_90d", []):
        mx = c.get("max") or {}
        if mx.get("score"):
            cut.append(f"| {c['name']} | {c['region']} | {mx['score']}점 ({mx.get('ty', '')}) |")
    return page("지역별 분양가 순위표", [
        f"청약홈 입주자모집공고의 분양가를 공급면적 3.3㎡당으로 바꿔, 지역마다 달마다 평균을 낸 표예요. {st.get('date', now)} 기준이에요.",
        "", "새 공고가 올라오면 다시 계산해서 갱신해요. 단지별 자세한 비교는 공고 글에 있어요.", "",
        "## 지역별 3.3㎡당 평균 분양가 (이번 달 높은 순)"], rows + cut,
        ["", "같은 지역이라도 단지마다 입지와 브랜드가 달라 평균과 차이가 커요. 신청 전에는 입주자모집공고 원문을 꼭 확인해 주세요."])


def _cutoffs(days: int = 120) -> list[dict]:
    """최근 공고 단지의 해당지역 당첨 최저 가점(data/units 원본 그대로, 0·'-'은 뺌)."""
    from datetime import date
    cut = datetime.now(KST).date() - timedelta(days=days)
    out = []
    for f in sorted((ROOT / "data/units").glob("*.json")):
        u = _load(f)
        lows = []
        for x in u.get("score") or []:
            try:
                v = float(x.get("LWET_SCORE"))
            except (TypeError, ValueError):
                continue
            if x.get("RESIDE_SECD") == "01" and v > 0:
                lows.append(v)
        a = _load(ROOT / "data/analysis" / f.name)
        nd = a.get("notice_date")
        if lows and nd and date.fromisoformat(nd) >= cut:
            out.append({"name": a.get("name"), "region": a.get("region"), "date": nd, "low": int(min(lows))})
    return sorted(out, key=lambda r: r["date"], reverse=True)


def cheongyak_calc(now: str) -> str:
    rows = _cutoffs()
    data = json.dumps([[r["name"], r["region"], r["low"]] for r in rows], ensure_ascii=False)
    opt_home = "".join(f'<option value="{2 + 2 * i if i else 2}">{"1년 미만" if i == 0 else (f"{i}년 이상 {i + 1}년 미만" if i < 15 else "15년 이상")}</option>'
                       for i in range(16))
    opt_home = '<option value="0">해당 없음(유주택, 만 30세 미만 미혼)</option>' + opt_home
    opt_fam = "".join(f'<option value="{5 + 5 * i}">{i}명{" 이상" if i == 6 else ""}</option>' for i in range(7))
    acc = [("6개월 미만", 1), ("6개월 이상 1년 미만", 2)] + [(f"{i}년 이상 {i + 1}년 미만", i + 2) for i in range(1, 15)] + [("15년 이상", 17)]
    opt_acc = "".join(f'<option value="{v}">{t}</option>' for t, v in acc)
    table = ["| 지역 | 단지 | 공고일 | 해당지역 당첨 최저 가점 |", "| --- | --- | --- | --- |"]
    table += [f"| {r['region']} | {r['name']} | {r['date']} | {r['low']}점 |" for r in rows]
    form = (
        '<div id="calc" style="border:1px solid #d0d7de;border-radius:8px;padding:16px;margin:1em 0;">'
        '<p><label>무주택기간<br><select id="h" style="width:100%;padding:6px;">' + opt_home + '</select></label></p>'
        '<p><label>부양가족 수(본인 제외)<br><select id="f" style="width:100%;padding:6px;">' + opt_fam + '</select></label></p>'
        '<p><label>청약통장 가입기간<br><select id="a" style="width:100%;padding:6px;">' + opt_acc + '</select></label></p>'
        '<p id="out" style="font-size:18px;font-weight:bold;margin:.6em 0;"></p><p id="cmp" style="margin:0;"></p></div>')
    script = (
        '<script>(function(){var D=' + data + ';'
        'function g(i){return parseInt(document.getElementById(i).value,10)||0}'
        'function r(){var s=g("h")+g("f")+g("a");document.getElementById("out").textContent="내 청약 가점: "+s+"점 / 84점";'
        'var n=D.filter(function(x){return s>=x[2]}).length;'
        'document.getElementById("cmp").textContent=D.length?("최근 공고 "+D.length+"개 단지 가운데 "+n+"곳은 해당지역 당첨 최저 가점이 "+s+"점 이하였어요."):""}'
        '["h","f","a"].forEach(function(i){document.getElementById(i).addEventListener("change",r)});r()})();</script>')
    return "\n".join(["---", 'title: "청약 가점 계산기"', 'slug: "calculator"', "publish: true", "---",
        "무주택기간, 부양가족 수, 청약통장 가입기간을 고르면 청약 가점(84점 만점)을 바로 계산해요. "
        "계산한 점수를 최근 공고 단지들의 실제 당첨 최저 가점과 바로 견줘 볼 수 있게 했어요.", "",
        form, "", script, "",
        "## 점수는 이렇게 매겨요",
        "",
        "주택공급에 관한 규칙(별표 1)의 가점 기준을 따라요. 무주택기간 최대 32점, 부양가족 최대 35점, 청약통장 가입기간 최대 17점이에요.",
        "",
        "| 항목 | 점수 매기는 법 | 최대 |", "| --- | --- | --- |",
        "| 무주택기간 | 1년 미만 2점, 이후 1년마다 2점씩 | 32점(15년 이상) |",
        "| 부양가족 수 | 0명 5점, 1명마다 5점씩 | 35점(6명 이상) |",
        "| 청약통장 가입기간 | 6개월 미만 1점, 6개월~1년 2점, 이후 1년마다 1점씩 | 17점(15년 이상) |",
        "",
        "무주택기간은 만 30세부터 세고, 그 전에 혼인했다면 혼인신고일부터 세요. 본인과 배우자가 모두 무주택이어야 해요. "
        "부양가족은 같은 주민등록표에 있는 직계존속(3년 이상)과 미혼 자녀 등이 기준이라, 정확한 인정 여부는 입주자모집공고와 청약홈에서 확인해 주세요.",
        "",
        f"## 최근 공고 단지의 당첨 최저 가점 ({now} 기준)",
        "",
        "청약홈이 발표한 해당지역 당첨자 가운데 가장 낮은 가점이에요. 위 계산기의 비교 문장은 이 표로 계산해요. 매주 새 발표가 나오면 갱신해요.",
        "", *table, "",
        "같은 단지라도 주택형마다 커트라인이 다르고, 여기 적은 값은 그 단지에서 가장 낮았던 주택형 기준이에요. "
        "실제 당첨 가능성은 공급 물량과 경쟁률에 따라 달라요.", ""])


def main() -> int:
    now = datetime.now(KST).date().isoformat()
    for key, fn, base in (("cheongyak", cheongyak, ROOT), ("jeonse", jeonse, ROOT / "blogs/jeonse"),
                          ("gongmoju", gongmoju, ROOT / "blogs/gongmoju"), ("gwanribi", gwanribi, ROOT / "blogs/gwanribi")):
        text = fn(now)
        (base / "pages" / "ranking.md").write_text(text, "utf-8")
        print(f"{key}: ranking.md {len(text):,}자")
    (ROOT / "pages" / "calculator.md").write_text(cheongyak_calc(now), "utf-8")
    print("cheongyak: calculator.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
