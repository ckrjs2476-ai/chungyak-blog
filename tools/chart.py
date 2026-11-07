"""데이터 파일에 있는 값만으로 그리는 원본 차트 (rules/unique_value.md 7장).

글쓴이는 차트 '종류'와 '대상'만 고른다. 숫자는 이 도구가 데이터 파일에서 직접 읽는다(옮겨 적기·직접 계산 금지 규칙 유지).
차트에 찍히는 값은 모두 데이터 파일에 이미 있는 값이라, 본문에 그 숫자를 써도 검수가 데이터와 대조할 수 있다.

captures/queue.json 항목에 "chart"를 넣으면 capture 워크플로가 이 도구로 그린다:
  {"name": "jeonse-11200-dong", "chart": {"type": "jeonse_dong", "lawd": "11200", "highlight": "성수동1가"}}
결과: captures/<name>.webp (가로 760px) — 글에는 다른 캡처와 똑같이 ![캡션](captures/<name>.webp)

종류(type)와 필요한 값:
  jeonse_dong      lawd, highlight(동 이름, 선택)  시군구 안 동별 전세가율(거래 10건 이상 동), 시군구 전세가율 선
  jeonse_sido      lawd                           같은 시도 시군구들의 전세가율, 대상 강조, 전국 평균 선
  gwanribi_complex lawd, code                     시군구 안 단지별 ㎡당 관리비(정렬 막대), 대상 강조, 중앙값 선
  gwanribi_sido    lawd                           같은 시도 시군구들의 ㎡당 관리비 중앙값, 대상 강조
  cheongyak_region region, no(선택)               이번 달·지난달 같은 지역 분양 단지 3.3㎡당 분양가, 대상 강조, 평균 선
  gongmoju_size    corp_code                      최근 공모 기업 공모 규모(억 원), 대상 강조, 중앙값 선
  history          blog, entity, metric           우리 기록(data/history)의 날짜별 값(기록 3개 이상일 때)
로컬 시험: python tools/chart.py '<chart json>' out.webp
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# 블로그 색(assets/brand와 맞춤): 강조 1색 + 회색
ACCENT = {"jeonse": "#c2410c", "gwanribi": "#0f766e", "cheongyak": "#1d4ed8", "gongmoju": "#7c3aed", "drone": "#0e7490"}
GREY = "#cbd5e1"
INK = "#1f2937"
SUB = "#64748b"


def _font():
    for name in ("Noto Sans CJK KR", "Noto Sans CJK JP", "Noto Sans CJK SC", "NanumGothic"):
        try:
            font_manager.findfont(name, fallback_to_default=False)
            plt.rcParams["font.family"] = name
            return
        except Exception:  # noqa: BLE001
            continue
    for f in font_manager.findSystemFonts():
        if "NotoSansCJK" in f or "Nanum" in f:
            font_manager.fontManager.addfont(f)
            plt.rcParams["font.family"] = font_manager.FontProperties(fname=f).get_name()
            return


_font()
plt.rcParams["axes.unicode_minus"] = False


def _load(p):
    p = ROOT / p
    if not p.exists():
        raise ValueError(f"데이터 파일 없음: {p.relative_to(ROOT)}")
    return json.loads(p.read_text("utf-8"))


def _short(name: str) -> str:
    """'서울특별시 성동구' → '성동구', '경상남도 창원시 마산회원구' → '창원시 마산회원구'"""
    parts = name.split()
    return " ".join(parts[1:]) if len(parts) > 1 else name


def _sido(name: str) -> str:
    return name.split()[0] if name else ""


def _bars(items, key_label, key_val, hl, accent, title, unit, ref=None, ref_label="", note="", fmt="{:,.0f}", horizontal=True):
    """items 정렬된 막대. hl=강조할 라벨. ref=기준선 값."""
    n = len(items)
    labels = [key_label(x) for x in items]
    vals = [key_val(x) for x in items]
    colors = [accent if hl is not None and lab == hl else GREY for lab in labels]
    if horizontal:
        h = max(3.2, 0.32 * n + 1.4)
        fig, ax = plt.subplots(figsize=(7.6, h), dpi=100)
        ax.barh(range(n), vals, color=colors, height=0.7, zorder=2)
        ax.set_yticks(range(n), labels, fontsize=10)
        ax.invert_yaxis()
        for i, v in enumerate(vals):
            ax.text(v, i, " " + fmt.format(v), va="center", fontsize=9, zorder=4,
                    bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.6, "alpha": 0.85},
                    color=INK if colors[i] == accent else SUB, fontweight="bold" if colors[i] == accent else "normal")
        if ref is not None:
            ax.axvline(ref, color=INK, lw=1, ls="--", zorder=1)
            ax.text(ref, -0.9, f" {ref_label} {fmt.format(ref)}", fontsize=9, color=INK, va="bottom")
        ax.set_xlim(0, max(vals + ([ref] if ref else [])) * 1.18)
        ax.xaxis.set_visible(False)
    else:
        fig, ax = plt.subplots(figsize=(7.6, 4.2), dpi=100)
        ax.bar(range(n), vals, color=colors, width=0.8)
        ax.set_xticks([])
        if ref is not None:
            ax.axhline(ref, color=INK, lw=1, ls="--")
            ax.text(n - 0.5, ref, f"{ref_label} {fmt.format(ref)} ", fontsize=9, color=INK, ha="right", va="bottom")
        if hl is not None and hl in labels:
            i = labels.index(hl)
            ax.annotate(f"{hl}\n{fmt.format(vals[i])}", (i, vals[i]), xytext=(0, 14), textcoords="offset points",
                        ha="center", fontsize=10, color=accent, fontweight="bold",
                        arrowprops={"arrowstyle": "-", "color": accent})
        ax.set_ylim(0, max(vals) * 1.25)
        ax.tick_params(axis="y", labelsize=9, colors=SUB)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left" if horizontal else "bottom"].set_color(GREY)
    if horizontal:
        ax.spines["bottom"].set_visible(False)
    fig.suptitle(title, x=0.02, ha="left", fontsize=13, fontweight="bold", color=INK)
    fig.text(0.02, 0.005, f"단위: {unit}   {note}", fontsize=8.5, color=SUB, ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    return fig


def jeonse_dong(c):
    d = _load(f"blogs/jeonse/data/regions/{c['lawd']}.json")
    ums = [(k, u) for k, u in (d.get("umd") or {}).items() if (u.get("jeonse_n") or 0) >= 10 and u.get("ratio") is not None]
    if len(ums) < 3:
        raise ValueError("거래 10건 이상 동이 3곳 미만")
    ums.sort(key=lambda x: -x[1]["ratio"])
    ums = ums[:20]
    return _bars(ums, lambda x: x[0], lambda x: x[1]["ratio"], c.get("highlight"), ACCENT["jeonse"],
                 f"{d['name']} 동별 전세가율", "% (84㎡ 전세 중앙값 ÷ 매매 중앙값)", ref=d.get("ratio84"),
                 ref_label=_short(d["name"]), note=f"국토교통부 실거래가 {d.get('months', '')}개월, 거래 10건 이상 동, {d.get('updated', '')} 집계",
                 fmt="{:.1f}")


def jeonse_sido(c):
    r = _load("blogs/jeonse/data/ranking.json")
    me = next((x for x in r["regions"] if x["lawd"] == c["lawd"]), None)
    if not me:
        raise ValueError("ranking.json에 없는 시군구")
    same = [x for x in r["regions"] if _sido(x["name"]) == _sido(me["name"]) and x.get("ratio84") is not None]
    same.sort(key=lambda x: -x["ratio84"])
    if len(same) > 25:  # 많으면 대상 주변 25곳
        i = same.index(me)
        lo = max(0, min(i - 12, len(same) - 25))
        same = same[lo:lo + 25]
    return _bars(same, lambda x: _short(x["name"]), lambda x: x["ratio84"], _short(me["name"]), ACCENT["jeonse"],
                 f"{_sido(me['name'])} 시군구 전세가율", "% (84㎡ 기준)", ref=r.get("avg_ratio84"), ref_label="전국 평균",
                 note=f"국토교통부 실거래가, {r.get('updated', '')} 집계", fmt="{:.1f}")


def gwanribi_complex(c):
    d = _load(f"blogs/gwanribi/data/regions/{c['lawd']}.json")
    cs = [x for x in d.get("complexes") or [] if x.get("total_m2")]
    if len(cs) < 3:
        raise ValueError("단지 3곳 미만")
    me = next((x for x in cs if x["code"] == c["code"]), None)
    if not me:
        raise ValueError("그 시군구에 없는 단지 코드")
    cs.sort(key=lambda x: -x["total_m2"])
    med = (d.get("median") or {}).get("total_m2")
    if len(cs) <= 22:
        return _bars(cs, lambda x: x["name"], lambda x: x["total_m2"], me["name"], ACCENT["gwanribi"],
                     f"{d['name']} 단지별 ㎡당 관리비", "원/㎡ (공용+개별+장기수선충당금)", ref=med, ref_label="중앙값",
                     note=f"K-apt {d.get('ym_label', '')} 부과분, {len(cs)}개 단지")
    return _bars(cs, lambda x: x["name"], lambda x: x["total_m2"], me["name"], ACCENT["gwanribi"],
                 f"{d['name']} {len(cs)}개 단지 중 {me['name']} 위치", "원/㎡ (공용+개별+장기수선충당금)", ref=med,
                 ref_label="중앙값", note=f"K-apt {d.get('ym_label', '')} 부과분, 높은 순 정렬", horizontal=False)


def gwanribi_sido(c):
    s = _load("blogs/gwanribi/data/summary.json")
    me = next((x for x in s["regions"] if x["lawd"] == c["lawd"]), None)
    if not me:
        raise ValueError("summary.json에 없는 시군구")
    same = [x for x in s["regions"] if _sido(x["name"]) == _sido(me["name"]) and x.get("median_total_m2")]
    same.sort(key=lambda x: -x["median_total_m2"])
    if len(same) > 25:
        i = same.index(me)
        lo = max(0, min(i - 12, len(same) - 25))
        same = same[lo:lo + 25]
    return _bars(same, lambda x: _short(x["name"]), lambda x: x["median_total_m2"], _short(me["name"]), ACCENT["gwanribi"],
                 f"{_sido(me['name'])} 시군구별 ㎡당 관리비 중앙값", "원/㎡", note=f"K-apt {me.get('ym', '')} 부과분, {s.get('updated', '')} 집계")


def _cut(name: str, n: int = 18) -> str:
    base = name.split("(")[0].strip() or name
    return base if len(base) <= n else base[:n - 1] + "…"


def cheongyak_region(c):
    st = _load("data/stats/latest.json")
    units = [u for m in ("this_month", "last_month") for u in (st.get(m) or {}).get("units", [])
             if u.get("region") == c["region"] and u.get("pyeong_avg")]
    seen, uniq = set(), []
    for u in units:
        if u["no"] not in seen:
            seen.add(u["no"])
            uniq.append(u)
    if len(uniq) < 3:
        raise ValueError("같은 지역 분양 단지 3곳 미만")
    uniq.sort(key=lambda x: -x["pyeong_avg"])
    names = [_cut(u["name"]) for u in uniq]
    dup = {nm for nm in names if names.count(nm) > 1}
    for i, nm in enumerate(list(names)):  # 같은 이름이 둘 이상이면 공고번호 끝 3자리로 구분
        if nm in dup:
            names[i] = f"{nm} ({uniq[i]['no'][-3:]})"
    for u, nm in zip(uniq, names):
        u["_label"] = nm
    hl = next((u["_label"] for u in uniq if u["no"] == c.get("no")), None)
    tm = (st.get("this_month") or {}).get("month", "")
    ref = ((st.get("monthly_region_pyeong") or {}).get(tm) or {}).get(c["region"], {}).get("avg_pyeong")
    months = f"{(st.get('last_month') or {}).get('month', '')}~{tm}"
    return _bars(uniq[:20], lambda x: x["_label"], lambda x: x["pyeong_avg"], hl, ACCENT["cheongyak"],
                 f"{c['region']} 분양 단지 3.3㎡당 분양가", "만 원/3.3㎡", ref=ref, ref_label=f"{tm[5:].lstrip('0')}월 {c['region']} 평균",
                 note=f"청약홈 입주자모집공고 {months} {len(uniq)}곳, {st.get('date', '')} 집계")


def gongmoju_size(c):
    s = _load("blogs/gongmoju/data/summary.json")
    ipos = [x for x in s["ipos"] if x.get("total") and x.get("total_rank")]  # 스팩(순위 없음) 제외
    me = next((x for x in ipos if x["corp_code"] == c["corp_code"]), None)
    if not me:
        raise ValueError("summary.json에 없는 기업")
    ipos.sort(key=lambda x: -x["total"])
    return _bars(ipos[:22], lambda x: _cut(x["corp_name"], 14), lambda x: round(x["total"] / 1e8, 1), _cut(me["corp_name"], 14),
                 ACCENT["gongmoju"], f"최근 {s.get('days', '')}일 공모 기업 공모 규모", "억 원 (공모가 × 공모주식수)",
                 ref=s.get("median_total_eok"), ref_label="중앙값",
                 note=f"DART 증권신고서, {s.get('count', '')}곳(스팩 제외), {s.get('updated', '')} 집계")


def history(c):
    h = _load(f"data/history/{c['blog']}.json")
    s = (h["series"].get(c["entity"]) or {}).get(c["metric"]) or []
    if len(s) < 3:
        raise ValueError("기록이 3개 미만이라 선 그래프를 그리지 않음")
    xs = [d[5:].replace("-", "/") for d, _ in s]
    ys = [v for _, v in s]
    acc = ACCENT.get(c["blog"], INK)
    fig, ax = plt.subplots(figsize=(7.6, 3.8), dpi=100)
    ax.plot(range(len(ys)), ys, color=acc, lw=2.2, marker="o", ms=4)
    ax.set_xticks(range(len(xs)), xs, fontsize=9, color=SUB, rotation=0 if len(xs) <= 10 else 45)
    for i in (0, len(ys) - 1):
        ax.annotate(f"{ys[i]:,.1f}".rstrip("0").rstrip("."), (i, ys[i]), xytext=(0, 8), textcoords="offset points",
                    ha="center", fontsize=10, color=acc, fontweight="bold")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(axis="y", labelsize=9, colors=SUB)
    fig.suptitle(c.get("title") or f"{c['entity']} {c['metric']} 기록", x=0.02, ha="left", fontsize=13, fontweight="bold", color=INK)
    fig.text(0.02, 0.005, f"단위: {c.get('unit', '')}   이 블로그가 {h.get('started', '')}부터 매일 쌓은 기록(값이 바뀐 날만 점)",
             fontsize=8.5, color=SUB)
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    return fig


TYPES = {f.__name__: f for f in (jeonse_dong, jeonse_sido, gwanribi_complex, gwanribi_sido, cheongyak_region, gongmoju_size, history)}


def render(spec: dict) -> Image.Image:
    t = spec.get("type")
    if t not in TYPES:
        raise ValueError(f"모르는 차트 종류: {t}")
    fig = TYPES[t](spec)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor="white")
    plt.close(fig)
    im = Image.open(buf).convert("RGB")
    if im.width > 760:
        im = im.resize((760, round(im.height * 760 / im.width)), Image.LANCZOS)
    return im


if __name__ == "__main__":
    render(json.loads(sys.argv[1])).save(sys.argv[2], "WEBP", quality=88)
    print("ok", sys.argv[2])
