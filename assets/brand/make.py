import asyncio
from playwright.async_api import async_playwright
ICONS={
 'cheongyak':'<path d="M14 54V24l18-12 18 12v30" fill="none" stroke="#fff" stroke-width="4" stroke-linejoin="round"/><rect x="22" y="30" width="8" height="8" fill="#fff"/><rect x="34" y="30" width="8" height="8" fill="#fff"/><rect x="22" y="42" width="8" height="12" fill="#fff"/><circle cx="48" cy="46" r="11" fill="#22c55e" stroke="#fff" stroke-width="3"/><path d="M43 46l4 4 7-8" fill="none" stroke="#fff" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>',
 'jeonse':'<rect x="26" y="8" width="12" height="36" rx="6" fill="none" stroke="#fff" stroke-width="4"/><circle cx="32" cy="48" r="10" fill="#fff"/><rect x="30" y="22" width="4" height="24" fill="#fff"/><path d="M42 16h8M42 24h6M42 32h8" stroke="#fff" stroke-width="3" stroke-linecap="round"/>',
 'gongmoju':'<path d="M10 52h44" stroke="#fff" stroke-width="3" stroke-linecap="round"/><rect x="12" y="34" width="7" height="16" fill="#fff"/><rect x="23" y="26" width="7" height="24" fill="#fff"/><rect x="34" y="18" width="7" height="32" fill="#fff" opacity=".55"/><circle cx="38" cy="26" r="12" fill="none" stroke="#fff" stroke-width="4"/><path d="M47 35l9 9" stroke="#fff" stroke-width="5" stroke-linecap="round"/>',
 'gwanribi':'<path d="M14 8h26v44l-4-3-4 3-4-3-4 3-4-3-6 3z" fill="none" stroke="#fff" stroke-width="3.5" stroke-linejoin="round"/><path d="M20 18h14M20 26h10M20 34h8" stroke="#fff" stroke-width="3" stroke-linecap="round"/><circle cx="42" cy="38" r="10" fill="none" stroke="#fff" stroke-width="4"/><path d="M49 45l8 8" stroke="#fff" stroke-width="5" stroke-linecap="round"/>',
 'drone':'<rect x="24" y="26" width="16" height="12" rx="3" fill="#fff"/><path d="M24 29l-10-9M40 29l10-9M24 35l-10 9M40 35l10 9" stroke="#fff" stroke-width="3.5" stroke-linecap="round"/><ellipse cx="12" cy="18" rx="9" ry="3" fill="none" stroke="#fff" stroke-width="2.5"/><ellipse cx="52" cy="18" rx="9" ry="3" fill="none" stroke="#fff" stroke-width="2.5"/><ellipse cx="12" cy="46" rx="9" ry="3" fill="none" stroke="#fff" stroke-width="2.5"/><ellipse cx="52" cy="46" rx="9" ry="3" fill="none" stroke="#fff" stroke-width="2.5"/>',
}
COL={'cheongyak':('#0f2a4a','#1d4ed8'),'jeonse':('#5a1d0c','#d9480f'),'gongmoju':('#1e1b4b','#4338ca'),'gwanribi':('#053b2f','#047857'),'drone':('#083344','#0e7490')}
NAMES={'cheongyak':'청약노트','jeonse':'전세 온도계','gongmoju':'공모주 뜯어보기','gwanribi':'관리비 돋보기','drone':'드론 정보노트'}
def svg(k,size): return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="{size}" height="{size}">{ICONS[k]}</svg>'
def banner(k):
    a,b=COL[k]
    grid=''.join(f'<line x1="{x}" y1="0" x2="{x}" y2="600" stroke="#fff" stroke-opacity=".05"/>' for x in range(0,2000,48))+''.join(f'<line x1="0" y1="{y}" x2="2000" y2="{y}" stroke="#fff" stroke-opacity=".05"/>' for y in range(0,600,48))
    line='<polyline points="0,470 200,430 400,445 600,380 800,400 1000,330 1200,350 1400,280 1600,300 1920,220" fill="none" stroke="#fff" stroke-opacity=".12" stroke-width="3"/>'
    return f'''<div style="width:1920px;height:600px;background:linear-gradient(120deg,{a} 0%,{b} 100%);position:relative;overflow:hidden">
<svg width="1920" height="600" style="position:absolute;left:0;top:0">{grid}{line}</svg>
<div style="position:absolute;right:120px;top:90px;opacity:.13">{svg(k,420)}</div></div>'''
def fav(k,s):
    a,b=COL[k]
    return f'<div style="width:{s}px;height:{s}px;border-radius:{s*0.22}px;background:linear-gradient(135deg,{a},{b});display:flex;align-items:center;justify-content:center">{svg(k,int(s*0.78))}</div>'
def profile():
    return '''<div style="width:400px;height:400px;background:linear-gradient(135deg,#1f2937,#475569);display:flex;align-items:center;justify-content:center">
<svg viewBox="0 0 64 64" width="250" height="250"><rect x="12" y="8" width="34" height="46" rx="4" fill="none" stroke="#fff" stroke-width="3.5"/><path d="M19 40l6-7 5 4 8-10" fill="none" stroke="#38bdf8" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M19 18h18M19 24h12" stroke="#fff" stroke-width="3" stroke-linecap="round"/><circle cx="44" cy="44" r="9" fill="#1f2937" stroke="#fff" stroke-width="3.5"/><path d="M50.5 50.5l7 7" stroke="#fff" stroke-width="4.5" stroke-linecap="round"/></svg></div>'''
async def main():
    async with async_playwright() as p:
        br=await p.chromium.launch(); pg=await br.new_page()
        async def shot(html,w,h,out,omit=False):
            await pg.set_viewport_size({'width':w,'height':h})
            await pg.set_content(f'<html><body style="margin:0;background:transparent">{html}</body></html>')
            await pg.screenshot(path=out,omit_background=omit,clip={'x':0,'y':0,'width':w,'height':h})
        for k in ICONS:
            await shot(banner(k),1920,600,f'{k}-banner.png')
            await shot(fav(k,128),128,128,f'{k}-favicon.png',True)
        await shot(profile(),400,400,'profile.png')
        # preview sheet
        rows=''.join(f'<div style="display:flex;align-items:center;gap:16px;margin:0 0 14px"><div style="position:relative;width:960px;height:300px;background:url(file:///home/claude/brand/{k}-banner.png) center/cover;border-radius:8px;display:flex;align-items:center;justify-content:center"><span style="color:#fff;font:700 54px \'Noto Sans CJK KR\',sans-serif">{NAMES[k]}</span></div><img src="file:///home/claude/brand/{k}-favicon.png" width="96"></div>' for k in ICONS)
        html=f'<div style="padding:20px;background:#f3f4f6;width:1120px">{rows}<div style="display:flex;align-items:center;gap:16px"><img src="file:///home/claude/brand/profile.png" width="160" style="border-radius:50%"><span style="font:500 22px \'Noto Sans CJK KR\',sans-serif">공통 프로필 이미지(5개 블로그 작성자)</span></div></div>'
        await pg.set_viewport_size({'width':1160,'height':1900})
        await pg.goto('file:///home/claude/brand/'); 
        open('/home/claude/brand/preview.html','w').write(f'<html><body style="margin:0">{html}</body></html>')
        await pg.goto('file:///home/claude/brand/preview.html')
        await pg.screenshot(path='preview.png',full_page=True)
        await br.close()
asyncio.run(main())
