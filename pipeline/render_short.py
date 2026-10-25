#!/usr/bin/env python
"""Vertical Shorts cut (1080x1920, <=60 s) from the same script.json + audio/ as the long video.

Uses the hook (opening lines) through the 「先に結論」 line, then a 3 s end card that points to the long video.
Static frames + voice + ominous BGM bed. Output: out/<name>_short.mp4   (pipeline.py calls this after the long render)

  python render_short.py --out out/mimei_x/mimei_x_short.mp4
"""
import argparse, json, os, subprocess, wave, glob
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
import render as R
import fx as FX

ROOT = R.ROOT
SW, SH = 1080, 1920
MAX_S, GAP, END_DUR = 57.0, 0.18, 3.0
PUNCH_DUR = 1.6          # 冒頭テロップ（thumb_text を画面中央に大きく）を重ねる秒数。スワイプを止めるため
HOOK_COL = "#FFD35C"
SR = 24000
FPS = 30

def pick_lines(script, meta):
    """hook … 先に結論 (inclusive); drop the self-intro line if too long; hard cap MAX_S."""
    lines = script["lines"]
    k = next((i for i, l in enumerate(lines) if l["t"].startswith("先に結論") or "結論" in l["t"][:6]), min(4, len(lines) - 1))
    sel = list(range(0, k + 1))
    def total(ix): return sum(meta[i]["dur"] + GAP for i in ix)
    if total(sel) > MAX_S:
        intro = [i for i in sel if "未明新聞のミメイです" in lines[i]["t"]]
        for i in intro: sel.remove(i)
    while total(sel) > MAX_S and len(sel) > 1:
        sel.pop()
    return sel

_BG = None
def background():
    global _BG
    if _BG is not None: return _BG.copy()
    bg = Image.new("RGB", (SW, SH), R.PAPER)
    d = ImageDraw.Draw(bg)
    for y in range(0, SH, 3): d.line([(0, y), (SW, y)], fill="#1D1727")
    glow = Image.new("L", (SW, SH), 0); gd = ImageDraw.Draw(glow)
    gd.ellipse([-200, -400, SW + 200, 900], fill=90)
    glow = glow.filter(ImageFilter.GaussianBlur(140))
    _BG = Image.composite(Image.new("RGB", (SW, SH), R.PAPER2), bg, glow)
    return _BG.copy()

def header(d, script):
    d.line([(50, 70), (SW - 50, 70)], fill=R.INK, width=3)
    d.line([(50, 76), (SW - 50, 76)], fill=R.INK, width=1)
    d.text((60, 88), R.CHANNEL, font=R.F(R.SERIF, 46), fill=R.INK)
    d.rounded_rectangle([SW - 190, 92, SW - 60, 142], radius=4, outline=R.SEAL, width=3)
    d.text((SW - 125, 117), "号 外", font=R.F(R.SERIF, 28), fill=R.SEAL, anchor="mm")
    d.line([(50, 160), (SW - 50, 160)], fill=R.RULE, width=1)
    d.text((60, 190), script.get("category", "未明ダイブ"), font=R.F(R.SANS, 30), fill=R.SEAL)
    tf = R.F(R.SERIF, 92); y = 240
    for ln in R.wrap(script["title"], tf, SW - 120, d)[:2]:
        d.text((60, y), ln, font=tf, fill=R.INK); y += 108
    hf = R.F(R.SERIF, 36)
    for ln in R.wrap((script.get("thumb_text") or script.get("subtitle", "")).replace("／", ""), hf, SW - 120, d)[:2]:
        d.text((60, y + 6), ln, font=hf, fill=R.ACCENT); y += 50
    return y

_SMALL = {}
def _small(k, s=0.72):
    if k not in _SMALL:
        p = R.portraits[k]; _SMALL[k] = p.resize((int(p.width * s), int(p.height * s)), Image.LANCZOS)
    return _SMALL[k]

_GRADS = {}
def _grad(area_h):
    """場面絵の下端を字幕帯へ溶かすグラデーション（高さごとにキャッシュ）。"""
    if area_h not in _GRADS:
        col = Image.new("RGBA", (SW, area_h), (15, 11, 23, 0))
        a = Image.new("L", (1, area_h), 0)
        for yy in range(area_h - 260, area_h): a.putpixel((0, yy), int(230 * ((yy - (area_h - 260)) / 260) ** 1.3))
        col.putalpha(a.resize((SW, area_h))); _GRADS[area_h] = col
    return _GRADS[area_h]

def frame(script, active, text, scene=None, scene_img=None):
    img = background(); d = ImageDraw.Draw(img)
    top = header(d, script)
    band_y = 1420
    if scene_img is None and scene and scene in R.SCENES: scene_img = R.SCENES[scene]
    if scene_img is not None:
        # 場面絵（またはクリップのフレーム）を中央領域に（16:9 を縦に切り出し）、話者は右下に小さく
        area_h = band_y - top - 30; sc = scene_img
        s = area_h / sc.height; cw = int(SW / s)            # 先に中央を切り出してから縮小（毎フレームの縮小コストを1/2以下に）
        sc = sc.crop(((sc.width - cw) // 2, 0, (sc.width - cw) // 2 + cw, sc.height))
        im = sc.resize((SW, area_h), Image.BILINEAR if scene_img is not None and sc.width > 1200 else Image.LANCZOS)
        img.paste(im, (0, top + 20))
        g = _grad(area_h); img.paste(g, (0, top + 20), g)
        p = _small(active)
        img.paste(p, (SW - p.width - 40, band_y - p.height + 4), p)
        d = ImageDraw.Draw(img)
    else:
        # character: active one, large, centered between header and subtitle band
        p = R.portraits[active]
        s = (band_y - top - 40) / p.height
        p = p.resize((int(p.width * s), int(p.height * s)), Image.LANCZOS)
        sh = Image.new("RGBA", p.size, (0, 0, 0, 0)); sh.paste((0, 0, 0, 140), (0, 0), p.split()[3])
        sh = sh.filter(ImageFilter.GaussianBlur(18))
        x = SW // 2 - p.width // 2; y = band_y - p.height - 10
        img.paste(sh, (x + 10, y + 22), sh); img.paste(p, (x, y), p)
    d = ImageDraw.Draw(img)
    d.rectangle([0, band_y, SW, SH], fill="#0F0B17"); d.line([(0, band_y), (SW, band_y)], fill=R.RULE, width=1)
    name, role, col = R.NAMES[active]
    d.rounded_rectangle([60, band_y + 30, 60 + 150, band_y + 30 + 50], radius=6, fill=col)
    d.text((60 + 75, band_y + 55), name, font=R.F(R.SERIF, 30), fill="#141018", anchor="mm")
    tf = R.F(R.SERIF, 44); yy = band_y + 100
    for ln in R.wrap(text, tf, SW - 120, d)[:6]:
        d.text((60, yy), ln, font=tf, fill=R.INK); yy += 62
    return img

def punch(img, script):
    """冒頭 PUNCH_DUR 秒だけ、画面中央に「問い」(thumb_text) を大きく重ねる。"""
    hook = script.get("thumb_text") or script.get("subtitle", "")
    d = ImageDraw.Draw(img, "RGBA")
    hf = R.F(R.SERIF, 104)
    import pipeline as P
    lines = P.hook_lines(hook, hf, SW - 140, d)
    lh = int(hf.size * 1.2); h = lh * len(lines) + 90
    y0 = 760 - h // 2
    d.rectangle([0, y0, SW, y0 + h], fill=(10, 6, 16, 215))
    d.line([(0, y0), (SW, y0)], fill=HOOK_COL, width=4); d.line([(0, y0 + h), (SW, y0 + h)], fill=HOOK_COL, width=4)
    y = y0 + 45
    for ln in lines:
        d.text((SW // 2 + 4, y + 4), ln, font=hf, fill="#000000", anchor="ma")
        d.text((SW // 2, y), ln, font=hf, fill=HOOK_COL, anchor="ma"); y += lh
    return img

def end_frame(script):
    img = background(); d = ImageDraw.Draw(img); header(d, script)
    p = R.portraits["mimei"]; s = 820 / p.height
    p = p.resize((int(p.width * s), 820), Image.LANCZOS)
    img.paste(p, (SW // 2 - p.width // 2, 560), p)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([90, 1440, SW - 90, 1540], radius=8, fill=R.ACCENT)
    d.text((SW // 2, 1490), "本編（約10分）はチャンネルで", font=R.F(R.SERIF, 40), fill="#1A1224", anchor="mm")
    d.text((SW // 2, 1600), f"YouTube {R.CHANNEL}", font=R.F(R.SANS, 32), fill=R.INK2, anchor="mm")
    d.text((SW // 2, 1660), "チャンネル登録、お願いします。", font=R.F(R.SERIF, 34), fill=R.INK, anchor="mm")
    d.text((60, SH - 70), "VOICEVOX:雀松朱司／中部つるぎ／小夜SAYO", font=R.F(R.SANS, 22), fill=R.MUTED)
    return img

def load_bgm(n):
    files = glob.glob(os.path.join(ROOT, "bgm", "ominous.*"))
    if not files: return np.zeros(n, np.float32)
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", files[0], "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    x = x * (10 ** (-26 / 20) / (np.sqrt(np.mean(x ** 2)) or 1e-6))
    x = np.resize(x, n).copy()
    f = int(2.0 * SR); x[-f:] *= np.linspace(1, 0, f)
    return x

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); a = ap.parse_args()
    script, meta = R.script, R.meta
    sel = pick_lines(script, meta)
    work = os.path.join(ROOT, "out", "short_frames"); os.makedirs(work, exist_ok=True)
    for f in glob.glob(os.path.join(work, "*")): os.remove(f)
    scenes = R.assign_scenes(script["lines"])
    fxs = FX.assign(script["lines"], scenes)
    # 音声
    chunks = []; gap = np.zeros(int(GAP * SR), np.int16)
    for i in sel:
        with wave.open(meta[i]["wav"]) as w: chunks.append(np.frombuffer(w.readframes(w.getnframes()), np.int16))
        chunks.append(gap)
    chunks.append(np.zeros(int(END_DUR * SR), np.int16))
    voice = np.concatenate(chunks).astype(np.float32) / 32768
    mix = voice + load_bgm(len(voice))
    peak = np.abs(mix).max();  mix = mix * (0.98 / peak) if peak > 0.98 else mix
    wavp = os.path.join(work, "short.wav")
    with wave.open(wavp, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes())
    # 映像: フレームを ffmpeg にストリーム（場面クリップがあれば毎フレーム差し替え、無ければ静止）
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{SW}x{SH}", "-r", str(FPS),
                           "-i", "-", "-i", wavp, "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", a.out], stdin=subprocess.PIPE)
    t = 0.0; total = 0.0
    for n, i in enumerate(sel):
        ln = script["lines"][i]; sc = scenes[i]
        dur = meta[i]["dur"] + GAP; nf = int(round(dur * FPS))
        clip = R.clip_frames(sc) if sc else None
        still = frame(script, ln["c"], ln["t"], sc)
        for f in range(nf):
            tt = t + f / FPS
            if clip or fxs[i]:
                bg = R.clip_frame(sc, tt) if clip else R.SCENES[sc]
                if fxs[i]: bg = FX.apply(bg, fxs[i], tt, tt - t, n)
                fr = frame(script, ln["c"], ln["t"], sc, bg)
            else: fr = still
            if n == 0 and tt < PUNCH_DUR and dur > PUNCH_DUR + 0.5: fr = punch(fr.copy(), script)
            ff.stdin.write(fr.convert("RGB").tobytes())
        t += nf / FPS; total += dur
    end = end_frame(script).convert("RGB").tobytes()
    for _ in range(int(END_DUR * FPS)): ff.stdin.write(end)
    ff.stdin.close(); ff.wait(); total += END_DUR
    print(json.dumps({"short": a.out, "lines": sel, "duration_s": round(total, 1)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
