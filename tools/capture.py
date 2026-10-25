"""공개 페이지 화면 캡처 (Actions에서 실행). captures/queue.json: [{"name": "...", "url": "...", "clip": "css selector(선택)", "wait": "css selector(선택)", "width": 1280}]
결과: captures/<name>.png, captures/log.json. 로그인·개인정보가 필요한 페이지는 넣지 않는다."""
import json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

Q = Path("captures/queue.json")
items = json.loads(Q.read_text("utf-8")) if Q.exists() else []
log = []
with sync_playwright() as pw:
    b = pw.chromium.launch()
    for it in items:
        page = b.new_page(viewport={"width": it.get("width", 1280), "height": it.get("height", 900)},
                          device_scale_factor=1, locale="ko-KR")
        out = Path("captures") / f"{it['name']}.png"
        try:
            r = page.goto(it["url"], timeout=45000, wait_until="networkidle")
            if it.get("wait"):
                page.wait_for_selector(it["wait"], timeout=20000)
            time.sleep(it.get("sleep", 1))
            if it.get("clip"):
                page.locator(it["clip"]).first.screenshot(path=str(out))
            else:
                page.screenshot(path=str(out), full_page=it.get("full", False))
            log.append({"name": it["name"], "status": r.status if r else None, "ok": True, "title": page.title()})
            print(f"::notice::캡처 {it['name']} {r.status if r else ''} {page.title()[:60]}")
        except Exception as e:  # noqa: BLE001
            log.append({"name": it["name"], "ok": False, "error": str(e)[:300]})
            print(f"::warning::캡처 실패 {it['name']}: {str(e)[:200]}")
        page.close()
    b.close()
Path("captures/log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), "utf-8")
Q.write_text("[]", "utf-8")
