import json,urllib.parse,re
exec(open('make.py').read().split('def svg')[0])  # ICONS, COL, NAMES
def enc(s): return "data:image/svg+xml,"+urllib.parse.quote(s,safe=" =:/,;'")
out={}
for k in ICONS:
    a,b=COL[k]
    icon=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" opacity="0.13">{ICONS[k]}</svg>'
    grid='<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48"><path d="M48 0H0V48" fill="none" stroke="white" stroke-opacity="0.06"/></svg>'
    css=f"""
/* brand-css start ({NAMES[k]}, 2026-10-31) */
.bg-photo{{background-color:{a}!important;background-image:url("{enc(icon)}"),url("{enc(grid)}"),linear-gradient(120deg,{a} 0%,{b} 100%)!important;background-repeat:no-repeat,repeat,no-repeat!important;background-position:right 8% top 60px,0 0,0 0!important;background-size:260px 260px,48px 48px,100% 100%!important}}
@media (max-width:800px){{.bg-photo{{background-size:150px 150px,48px 48px,100% 100%!important;background-position:right 4% top 70px,0 0,0 0!important}}}}
.centered-top-container .blog-name a,.centered-top-container .blog-name{{letter-spacing:-0.5px}}
.post-body a,.post-body a:visited{{color:{b}}}
.post-title a:hover,.post-body a:hover{{color:{a}}}
.post-body h2,.post-body h3{{border-left:4px solid {b};padding-left:10px}}
/* brand-css end */
"""
    out[k]=css
json.dump(out,open('css.json','w'),ensure_ascii=False)
print(len(out['gwanribi']), '$(' in ''.join(out.values()))
