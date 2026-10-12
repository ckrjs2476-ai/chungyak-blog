from PIL import Image, ImageDraw, ImageFont
S = 2048  # 4x 그린 뒤 줄임
FB = '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'
FR = '/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc'

def base(bg):
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, S - 1, S - 1], radius=S // 5, fill=bg)
    return im, d

def gwanribi():  # 관리비 돋보기: 영수증 + 돋보기
    im, d = base('#0F766E'); W = 'white'
    x0, y0, x1, y1 = 470, 330, 1330, 1640
    pts = [(x0, y0), (x1, y0), (x1, y1)]
    n = 7; step = (x1 - x0) / n
    for i in range(n, 0, -1):
        pts.append((x0 + step * (i - 0.5), y1 - 70)); pts.append((x0 + step * (i - 1), y1))
    d.polygon(pts, fill=W)
    for k, w in enumerate([560, 420, 620, 360, 500]):
        y = 520 + k * 190
        d.rounded_rectangle([x0 + 110, y, x0 + 110 + w, y + 70], 35, fill='#99D5CC')
    cx, cy, r = 1330, 1270, 360
    d.line([cx + 230, cy + 230, cx + 520, cy + 520], fill='#F59E0B', width=170)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill='#F59E0B')
    d.ellipse([cx - r + 95, cy - r + 95, cx + r - 95, cy + r - 95], fill='#FEF3C7')
    return im

def jeonse():  # 전세 온도계: 집 + 온도계
    im, d = base('#1E3A8A'); W = 'white'
    d.polygon([(1024, 330), (1720, 960), (328, 960)], fill=W)
    d.rectangle([470, 900, 1578, 1700], fill=W)
    tx = 1024
    d.rounded_rectangle([tx - 130, 760, tx + 130, 1480], 130, fill='#1E3A8A')
    d.rounded_rectangle([tx - 70, 820, tx + 70, 1480], 70, fill='#DBEAFE')
    d.rectangle([tx - 70, 1120, tx + 70, 1480], fill='#EF4444')
    d.ellipse([tx - 230, 1330, tx + 230, 1790], fill='#1E3A8A')
    d.ellipse([tx - 170, 1390, tx + 170, 1730], fill='#EF4444')
    for k in range(4):
        y = 880 + k * 140
        d.rectangle([tx + 160, y, tx + 300, y + 36], fill='#1E3A8A')
    return im

def gongmoju():  # 공모주 뜯어보기: 열린 상자 + 막대그래프
    im, d = base('#3F2A78'); W = 'white'
    d.polygon([(380, 1020), (1024, 1300), (1024, 1800), (380, 1520)], fill='#E9E3FA')
    d.polygon([(1668, 1020), (1024, 1300), (1024, 1800), (1668, 1520)], fill=W)
    d.polygon([(380, 1020), (150, 760), (790, 650), (1024, 1020)], fill='#C9BCF2')
    d.polygon([(1668, 1020), (1898, 760), (1258, 650), (1024, 1020)], fill='#C9BCF2')
    for k, (h, c) in enumerate([(380, '#FBBF24'), (620, '#34D399'), (860, '#60A5FA')]):
        x = 700 + k * 240
        d.rounded_rectangle([x, 1130 - h, x + 170, 1180], 40, fill=c)
    d.polygon([(380, 1020), (1024, 1300), (1668, 1020), (1024, 1150)], fill=W)
    return im

def banner(icon, name, tag, color, out):
    B = Image.new('RGB', (2400, 600), 'white'); d = ImageDraw.Draw(B)
    ic = icon.resize((440, 440), Image.LANCZOS); B.paste(ic, (80, 80), ic)
    d.text((600, 120), name, font=ImageFont.truetype(FB, 150, index=1), fill=color)
    d.text((606, 340), tag, font=ImageFont.truetype(FR, 72, index=1), fill='#374151')
    B.resize((1200, 300), Image.LANCZOS).save(out, optimize=True)

for key, fn, name, tag, color in [
    ('gwanribi', gwanribi, '관리비 돋보기', '우리 단지 관리비, 비슷한 단지와 나란히', '#0F766E'),
    ('jeonse', jeonse, '전세 온도계', '전세가율로 읽는 동네 전세 흐름', '#1E3A8A'),
    ('gongmoju', gongmoju, '공모주 뜯어보기', '증권신고서 숫자로 보는 공모 구조', '#3F2A78'),
]:
    im = fn()
    im.resize((512, 512), Image.LANCZOS).save(f'{key}-icon-512.png', optimize=True)
    im.resize((96, 96), Image.LANCZOS).save(f'{key}-favicon.png', optimize=True)
    banner(im, name, tag, color, f'{key}-logo.png')
