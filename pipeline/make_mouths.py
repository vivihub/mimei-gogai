#!/usr/bin/env python
"""Generate mouth variants for 号外 (closed / half / open) and eyelid (blink) variants for ホゴ・ヨミ."""
import os
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(ROOT, "img")
S = 4  # supersampling for anti-aliased drawing

def supersample_draw(base, draw_fn):
    """Draw onto a transparent layer at S x resolution, then composite down."""
    layer = Image.new("RGBA", (base.width * S, base.height * S), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer))
    layer = layer.resize(base.size, Image.LANCZOS)
    out = base.copy(); out.alpha_composite(layer); return out

# ---------- 号外: mouth ----------
def gogai():
    base = Image.open(os.path.join(IMG, "gogai.webp")).convert("RGBA")
    base.save(os.path.join(IMG, "gogai_m0.webp"), lossless=True)   # closed = original
    # patch to hide the drawn frown: copy skin from just above and blur the seam
    cx, top_y = 270, 258
    patch = base.crop((228, 240, 312, 256)).resize((84, 22), Image.LANCZOS)
    def hide(im):
        im = im.copy()
        m = Image.new("L", patch.size, 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, 83, 21], radius=8, fill=255)
        m = m.filter(ImageFilter.GaussianBlur(2))
        im.paste(patch, (228, top_y), m); return im

    LINE = (22, 0, 6, 255); INNER = (46, 10, 22, 255); TONGUE = (128, 46, 62, 255); LIP = (150, 100, 112, 255)
    def mouth(half):
        im = hide(base)
        w, h = (34, 9) if half else (46, 22)
        def fn(d):
            x0, x1 = (cx - w // 2) * S, (cx + w // 2) * S
            y0, y1 = (263 - h // 2) * S, (263 + h // 2) * S
            d.ellipse([x0, y0, x1, y1], fill=INNER)
            if not half:  # tongue at the bottom
                d.ellipse([x0 + 10 * S, y1 - 10 * S, x1 - 10 * S, y1 - 1 * S], fill=TONGUE)
            # upper lip: keep the character's frown arc
            d.arc([(cx - 32) * S, (256) * S, (cx + 32) * S, (270) * S], 200, 340, fill=LINE, width=int(2.2 * S))
            # lower lip highlight line
            d.arc([x0, y0, x1, y1 + 2 * S], 20, 160, fill=LIP, width=int(1.2 * S))
        return supersample_draw(im, fn)
    mouth(True).save(os.path.join(IMG, "gogai_m1.webp"), lossless=True)
    mouth(False).save(os.path.join(IMG, "gogai_m2.webp"), lossless=True)

# ---------- ホゴ・ヨミ: eyelids (blink) ----------
def eyelid(name, polys, is_eye, lid, shade, lash):
    """polys: hand-traced eyeball polygons; is_eye(r,g,b) optionally restricts to eye-coloured pixels
    (used where paper overlaps the eye). A skin-coloured eyelid slides down from the top of each eyeball."""
    import numpy as np
    base = Image.open(os.path.join(IMG, f"{name}.webp")).convert("RGBA")
    base.save(os.path.join(IMG, f"{name}_e0.webp"), lossless=True)  # open = original
    arr = np.array(base)
    lid, shade, lash = np.array(lid, float), np.array(shade, float), np.array(lash, float)
    r, g, b = [arr[..., i].astype(int) for i in range(3)]
    for level, tag in [(0.55, "e1"), (1.0, "e2")]:
        out = arr.copy().astype(float)
        reg = Image.new("L", base.size, 0)
        for poly in polys:
            em = Image.new("L", base.size, 0); ImageDraw.Draw(em).polygon(poly, fill=255)
            ImageDraw.Draw(reg).polygon(poly, fill=255)
            mask = np.array(em.filter(ImageFilter.MaxFilter(5))) > 0
            if is_eye is not None:
                mask &= is_eye(r, g, b)
            rows = np.where(mask.any(axis=1))[0]; cols = np.where(mask.any(axis=0))[0]
            top, bot = rows[0], rows[-1]; cx, hw = (cols[0] + cols[-1]) / 2, (cols[-1] - cols[0]) / 2
            base_cut = top + (bot - top) * level
            bulge = (bot - top) * (0.10 if level < 1 else 0.0)   # half-closed lid bows down at the centre
            for x in cols:
                col_mask = mask[:, x]
                ys = np.where(col_mask)[0]
                if len(ys) == 0: continue
                cut = int(min(ys[-1], base_cut + bulge * (1 - ((x - cx) / hw) ** 2)))
                for y in range(ys[0], cut + 1):
                    if not col_mask[y]: continue
                    t = (y - ys[0]) / max(1, (cut - ys[0]))
                    out[y, x, :3] = lid * (1 - 0.45 * t) + shade * (0.45 * t)
                for y in range(max(ys[0], cut - 2), min(ys[-1], cut + 1) + 1):
                    if col_mask[y]: out[y, x, :3] = lash
        img = Image.fromarray(out.astype("uint8"))
        img = Image.composite(img.filter(ImageFilter.GaussianBlur(0.9)), img, reg.filter(ImageFilter.MaxFilter(3)))
        img.save(os.path.join(IMG, f"{name}_{tag}.webp"), lossless=True)

if __name__ == "__main__":
    gogai()
    YOMI_L = [(163,184),(168,167),(182,160),(206,160),(224,172),(230,190),(226,210),(206,219),(180,218),(167,210)]
    YOMI_R = [(274,184),(280,166),(300,158),(328,160),(344,180),(342,198),(322,216),(294,218),(278,206)]
    eyelid("yomi", [YOMI_L, YOMI_R], None, lid=(238, 206, 198), shade=(160, 105, 118), lash=(40, 20, 26))
    HOGO = [(209,227),(212,222),(232,218),(250,222),(260,228),(273,233),(277,240),(275,248),(268,257),(252,262),(232,260),(217,252),(210,240)]
    eyelid("hogo", [HOGO], lambda r, g, b: (b - r > 10) | (r + g + b < 130) | ((r > 200) & (g > 200) & (b > 200)), lid=(142, 122, 136), shade=(92, 78, 96), lash=(30, 26, 40))
    print("done")
