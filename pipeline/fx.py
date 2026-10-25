#!/usr/bin/env python3
"""演出エフェクト（2026-10-25〜）。台本の行に "fx": "fog,flash" のように書くと、その行以降の場面絵／場面クリップの上に重なる。
"fx": "" で解除。場面が舞台（三人）に戻るときも解除。種類:
  fog     … 霧がゆっくり横に流れる（森・峠・海・墓地）
  rain    … 雨の筋が降り続ける（夜道・廃屋・事件現場）
  snow    … 雪がゆっくり舞う（山・冬の事件）
  embers  … 火の粉・塵が舞い上がる（火事・焚き火・儀式）
  flash   … 数秒〜十数秒おきに稲光（クライマックス・雷雨）
  pulse   … 画面の縁が脈打つように暗くなる（緊張・心臓の鼓動）
  red     … 赤い縁取り（血・警告・怒り）
  dark    … 全体を暗く落とす（不穏・夜更け）
  shake   … 行の冒頭1.2秒、画面が揺れる（衝撃・物音・発見）
  zoom    … その行のあいだ、ゆっくり寄る（「先に結論」・決め手の一言）
使い方: fx.apply(img, fxset, t_global, t_line, seed) → 新しい RGB Image。fxset は set/str/None。
"""
import math, random
from PIL import Image, ImageChops, ImageDraw, ImageFilter

W, H = 1920, 1080
_CACHE = {}

def parse(s):
    if not s: return set()
    return {x.strip() for x in str(s).split(",") if x.strip()}

def assign(lines, scenes):
    """各行の fx（継続）を解決。scenes は render.assign_scenes の結果。舞台に戻ったら解除。"""
    cur, out = set(), []
    for ln, sc in zip(lines, scenes):
        if "fx" in ln: cur = parse(ln["fx"])
        if not sc: cur = set()
        out.append(set(cur))
    return out

# ---------- レイヤー生成（初回だけ） ----------
def _noise_layer(seed, scale=160, blur=40, alpha=40, tint=(200, 196, 225)):
    key = ("noise", seed, scale, blur, alpha, tint)
    if key in _CACHE: return _CACHE[key]
    rng = random.Random(seed)
    small = Image.new("L", (W // scale + 2, H // scale + 2))
    small.putdata([rng.randint(0, 255) for _ in range(small.width * small.height)])
    big = small.resize((W * 2, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(blur))
    # コントラストを少し持ち上げて「塊」感を出す
    big = big.point(lambda v: max(0, min(255, int((v - 118) * 1.7))))
    a = big.point(lambda v: v * alpha // 255)
    layer = Image.new("RGBA", (W * 2, H), tint + (0,)); layer.putalpha(a)
    _CACHE[key] = layer; return layer

def _rain_frames(n=6, count=420, seed=7):
    key = ("rain", n, count, seed)
    if key in _CACHE: return _CACHE[key]
    rng = random.Random(seed); frames = []
    for f in range(n):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        for _ in range(count):
            x = rng.randint(-40, W); y = rng.randint(-60, H); L = rng.randint(28, 70)
            a = rng.randint(70, 150); d.line((x, y, x - 6, y + L), fill=(205, 215, 235, a), width=1)
        frames.append(im)
    _CACHE[key] = frames; return frames

def _dots_layer(seed, count, rmin, rmax, color, alpha):
    key = ("dots", seed, count, rmin, rmax, color, alpha)
    if key in _CACHE: return _CACHE[key]
    rng = random.Random(seed)
    im = Image.new("RGBA", (W, H * 2), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    for _ in range(count):
        x = rng.randint(0, W); y = rng.randint(0, H * 2); r = rng.uniform(rmin, rmax)
        d.ellipse((x - r, y - r, x + r, y + r), fill=color + (rng.randint(alpha // 2, alpha),))
    im = im.filter(ImageFilter.GaussianBlur(1.2))
    _CACHE[key] = im; return im

def _vignette(color=(0, 0, 0), strength=255):
    key = ("vig", color, strength)
    if key in _CACHE: return _CACHE[key]
    m = Image.new("L", (W // 8, H // 8), 0); d = ImageDraw.Draw(m)
    d.ellipse((-W // 32, -H // 32, W // 8 + W // 32, H // 8 + H // 32), fill=255)
    m = m.resize((W, H), Image.BILINEAR).filter(ImageFilter.GaussianBlur(120))
    m = m.point(lambda v: (255 - v) * strength // 255)
    layer = Image.new("RGBA", (W, H), color + (0,)); layer.putalpha(m)
    _CACHE[key] = layer; return layer

def _white():
    if "white" not in _CACHE: _CACHE["white"] = Image.new("RGB", (W, H), (240, 240, 255))
    return _CACHE["white"]

# ---------- 適用 ----------
def _flash_amount(t, seed):
    """稲光: 擬似乱数で 5〜13 秒おきに 2 連の閃光。0..1。"""
    rng = random.Random(seed); tt = 0.0; events = []
    while tt < 1200:
        tt += rng.uniform(5.0, 13.0); events.append(tt)
    for e in events:
        if e <= t < e + 0.45:
            d = t - e
            if d < 0.08: return 1.0
            if d < 0.20: return max(0.0, 0.6 - (d - 0.08) * 5)
            if 0.22 <= d < 0.30: return 0.8
            if d < 0.45: return max(0.0, 0.8 - (d - 0.30) * 5.5)
    return 0.0

def apply(img, fxset, t_global, t_line, seed=0):
    """img: RGB (W,H) の背景（場面絵／クリップ）。fxset: set。"""
    if not fxset: return img
    fx = fxset if isinstance(fxset, set) else parse(fxset)
    im = img
    # --- 変形系 ---
    if "zoom" in fx:
        z = 1.0 + 0.10 * max(0.0, min(1.0, t_line / 9.0))
        cw, ch = int(W / z), int(H / z)
        im = im.crop(((W - cw) // 2, (H - ch) // 2, (W - cw) // 2 + cw, (H - ch) // 2 + ch)).resize((W, H), Image.BILINEAR)
    if "shake" in fx and t_line < 1.2:
        amp = 12 * (1 - t_line / 1.2); rng = random.Random(int(t_global * 1000))
        dx, dy = int(rng.uniform(-amp, amp)), int(rng.uniform(-amp, amp))
        im = ImageChops.offset(im, dx, dy)
    # --- 粒子・天候（RGBA で一括合成） ---
    im = im.convert("RGBA")
    if "fog" in fx:
        for n, (speed, alpha) in enumerate(((22, 42), (38, 30))):
            layer = _noise_layer(seed * 10 + n, alpha=alpha)
            x = int(t_global * speed) % W
            im.alpha_composite(layer.crop((x, 0, x + W, H)))
    if "rain" in fx:
        fr = _rain_frames(); f = fr[int(t_global * 30) % len(fr)]
        f = ImageChops.offset(f, 0, int(t_global * 900) % H)
        im.alpha_composite(f)
    if "snow" in fx:
        for n, (speed, drift, count) in enumerate(((60, 18, 260), (110, 30, 160))):
            layer = _dots_layer(seed * 10 + 3 + n, count, 1.5, 3.5 if n == 0 else 5.0, (235, 238, 250), 200)
            y = int(t_global * speed) % H; x = int(math.sin(t_global * 0.6 + n) * drift)
            im.alpha_composite(ImageChops.offset(layer, x, y).crop((0, 0, W, H)))
    if "embers" in fx:
        for n, (speed, drift, count, col) in enumerate(((90, 26, 220, (255, 185, 90)), (150, 40, 120, (255, 130, 60)))):
            layer = _dots_layer(seed * 10 + 5 + n, count, 1.8, 4.5, col, 255)
            y = int(t_global * speed) % H; x = int(math.sin(t_global * 0.9 + n * 2) * drift)
            im.alpha_composite(ImageChops.offset(layer, x, -y).crop((0, 0, W, H)))
    # --- 色・縁 ---
    if "dark" in fx:
        im.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, 90)))
    if "red" in fx:
        im.alpha_composite(_vignette((170, 10, 25), 200))
    if "pulse" in fx:
        k = 0.30 + 0.25 * (0.5 + 0.5 * math.sin(2 * math.pi * 0.22 * t_global))
        v = _vignette((0, 0, 0), 255).copy(); v.putalpha(v.split()[3].point(lambda a: int(a * k)))
        im.alpha_composite(v)
    im = im.convert("RGB")
    if "flash" in fx:
        a = _flash_amount(t_global, seed)
        if a > 0: im = Image.blend(im, _white(), min(0.85, a * 0.85))
    return im
