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

ROOT = R.ROOT
SW, SH = 1080, 1920
MAX_S, GAP, END_DUR = 57.0, 0.18, 3.0
PUNCH_DUR = 1.6          # 冒頭テロップ（thumb_text を画面中央に大きく）を重ねる秒数。スワイプを止めるため
HOOK_COL = "#FFD35C"
SR = 24000

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

def background():
    bg = Image.new("RGB", (SW, SH), R.PAPER)
    d = ImageDraw.Draw(bg)
    for y in range(0, SH, 3): d.line([(0, y), (SW, y)], fill="#1D1727")
    glow = Image.new("L", (SW, SH), 0); gd = ImageDraw.Draw(glow)
    gd.ellipse([-200, -400, SW + 200, 900], fill=90)
    glow = glow.filter(ImageFilter.GaussianBlur(140))
    return Image.composite(Image.new("RGB", (SW, SH), R.PAPER2), bg, glow)

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

def frame(script, active, text):
    img = background(); d = ImageDraw.Draw(img)
    top = header(d, script)
    # character: active one, large, centered between header and subtitle band
    band_y = 1420
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
    segs, chunks = [], []
    gap = np.zeros(int(GAP * SR), np.int16)
    for n, i in enumerate(sel):
        ln = script["lines"][i]
        fn = f"s_{n:02d}.png"; fr = frame(script, ln["c"], ln["t"]); fr.save(os.path.join(work, fn))
        dur = meta[i]["dur"] + GAP
        if n == 0 and dur > PUNCH_DUR + 0.5:   # 最初の行の頭にだけ大テロップを重ねる（音声はそのまま流す）
            punch(fr.copy(), script).save(os.path.join(work, "s_00p.png"))
            segs.append(("s_00p.png", PUNCH_DUR)); dur -= PUNCH_DUR
        segs.append((fn, dur))
        with wave.open(meta[i]["wav"]) as w: chunks.append(np.frombuffer(w.readframes(w.getnframes()), np.int16))
        chunks.append(gap)
    end_frame(script).save(os.path.join(work, "s_end.png")); segs.append(("s_end.png", END_DUR))
    chunks.append(np.zeros(int(END_DUR * SR), np.int16))
    voice = np.concatenate(chunks).astype(np.float32) / 32768
    mix = voice + load_bgm(len(voice))
    peak = np.abs(mix).max();  mix = mix * (0.98 / peak) if peak > 0.98 else mix
    wavp = os.path.join(work, "short.wav")
    with wave.open(wavp, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype(np.int16).tobytes())
    lst = os.path.join(work, "list.txt")
    with open(lst, "w") as f:
        for fn, dur in segs: f.write(f"file '{fn}'\nduration {dur:.3f}\n")
        f.write(f"file '{segs[-1][0]}'\n")
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-i", wavp,
                    "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-tune", "stillimage", "-r", "30",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", a.out], check=True)
    total = sum(d for _, d in segs)
    print(json.dumps({"short": a.out, "lines": sel, "duration_s": round(total, 1)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
