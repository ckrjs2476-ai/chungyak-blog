"""공개 페이지 화면 캡처 (Actions에서 실행). 로그인·개인정보가 필요한 페이지는 넣지 않는다.
captures/queue.json: [{"name": "...", "url": "...",
   "crop": {"from": "시작 글자", "to": "끝 글자(선택)"},   # 화면에서 그 글자 사이만 잘라 캡처
   "full": false, "width": 1100, "pad": 12}]
결과: captures/<name>.webp (가로 최대 760px, 블로그 글에 그대로 넣는 크기), captures/log.json"""
import io, json, time
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

Q = Path("captures/queue.json")
items = json.loads(Q.read_text("utf-8")) if Q.exists() else []
log = []


def top_of(page, text):
    loc = page.get_by_text(text, exact=False)
    loc.first.wait_for(state="attached", timeout=15000)
    vis = [l for l in loc.all() if l.is_visible()]
    if not vis:
        raise RuntimeError(f"보이는 '{text}' 없음")
    loc = vis[0]
    loc.scroll_into_view_if_needed()
    box = loc.bounding_box()
    y = page.evaluate("window.scrollY")
    return box["y"] + y, box


with sync_playwright() as pw:
    b = pw.chromium.launch()
    for it in items:
        page = b.new_page(viewport={"width": it.get("width", 1100), "height": 900}, device_scale_factor=1, locale="ko-KR")
        try:
            r = page.goto(it["url"], timeout=45000, wait_until="networkidle")
            time.sleep(it.get("sleep", 1.5))
            for st in it.get("steps", []):  # 검색 조작: {"click": "글자"} / {"click_css": "선택자"} / {"fill": ["선택자", "값"]}
                if "click" in st:          # {"select": ["선택자", "보이는 글자"]} / {"wait": 초} / {"press": ["선택자", "Enter"]}
                    page.get_by_text(st["click"], exact=st.get("exact", False)).first.click(timeout=15000)
                elif "click_css" in st:
                    page.locator(st["click_css"]).first.click(timeout=15000)
                elif "fill" in st:
                    page.locator(st["fill"][0]).first.fill(st["fill"][1], timeout=15000)
                elif "select" in st:
                    page.locator(st["select"][0]).first.select_option(label=st["select"][1], timeout=15000)
                elif "press" in st:
                    page.locator(st["press"][0]).first.press(st["press"][1], timeout=15000)
                elif "pick" in st:  # 숨은 select도: 보이는 글자로 고르고 change 이벤트(jQuery 포함)
                    page.evaluate("""([sel, txt]) => { const e = document.querySelector(sel); if (!e) return;
                        const o = [...e.options].find(o => o.text.trim().includes(txt)); if (!o) return;
                        e.value = o.value; e.dispatchEvent(new Event('change', {bubbles: true}));
                        if (window.jQuery) window.jQuery(e).trigger('change'); }""", st["pick"])
                elif "js" in st:
                    page.evaluate(st["js"])
                elif "goto" in st:
                    page.goto(st["goto"], timeout=45000, wait_until="networkidle")
                time.sleep(st.get("wait", 1.2))
            if it.get("dump"):  # 레시피 만들 때만: 화면 구조를 저장
                Path("captures/probe").mkdir(exist_ok=True)
                Path(f"captures/probe/{it['name']}.html").write_text(page.content(), "utf-8")
                for i, fr in enumerate(page.frames[1:4]):
                    try:
                        Path(f"captures/probe/{it['name']}_frame{i}.html").write_text(fr.content(), "utf-8")
                    except Exception:  # noqa: BLE001
                        pass
            crop = it.get("crop")
            if crop:
                pad = it.get("pad", 12)
                y0, _ = top_of(page, crop["from"])
                if crop.get("to"):
                    y1, _ = top_of(page, crop["to"])
                else:
                    y1 = y0 + it.get("height", 600)
                page.evaluate("window.scrollTo(0,0)")
                full = page.evaluate("document.documentElement.scrollWidth")
                png = page.screenshot(full_page=True, clip={"x": 0, "y": max(0, y0 - pad), "width": min(full, it.get("width", 1100)),
                                                            "height": max(80, y1 - y0)})
            else:
                png = page.screenshot(full_page=it.get("full", False))
            im = Image.open(io.BytesIO(png)).convert("RGB")
            if im.width > 760:
                im = im.resize((760, round(im.height * 760 / im.width)), Image.LANCZOS)
            out = Path("captures") / f"{it['name']}.webp"
            im.save(out, "WEBP", quality=72, method=6)
            log.append({"name": it["name"], "ok": True, "status": r.status if r else None, "title": page.title(),
                        "size": [im.width, im.height], "bytes": out.stat().st_size, "url": it["url"],
                        "at": time.strftime("%Y-%m-%d %H:%M", time.gmtime(time.time() + 9 * 3600))})
            print(f"::notice::캡처 {it['name']} {im.width}x{im.height} {out.stat().st_size // 1024}KB")
        except Exception as e:  # noqa: BLE001
            log.append({"name": it["name"], "ok": False, "error": str(e)[:300], "url": it["url"]})
            print(f"::warning::캡처 실패 {it['name']}: {str(e)[:200]}")
        page.close()
    b.close()
old = json.loads(Path("captures/log.json").read_text("utf-8")) if Path("captures/log.json").exists() else []
Path("captures/log.json").write_text(json.dumps((old + log)[-200:], ensure_ascii=False, indent=1), "utf-8")
Q.write_text("[]", "utf-8")
