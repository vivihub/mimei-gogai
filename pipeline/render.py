#!/usr/bin/env python
"""Render frames per line and assemble the MP4 with ffmpeg."""
import json, os, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

ROOT = os.path.dirname(os.path.abspath(__file__))
W, H = 1920, 1080
GAP, TITLE_DUR, END_DUR = 0.18, 2.4, 3.2

SERIF = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
SANS = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
def F(path, size, idx=2):  # idx 2 = JP face inside the .ttc
    return ImageFont.truetype(path, size, index=idx)

PAPER, PAPER2, INK, INK2, MUTED, RULE, ACCENT, SEAL = \
    "#191423", "#211A2E", "#E6DECB", "#C4BAA6", "#8E8577", "#4A3F5C", "#B394DB", "#D0524B"

NAMES = {"mimei": ("ミメイ", "未明新聞・配達員", "#B394DB"),
         "hasu": ("ハス", "黄泉に咲く蓮", "#7FB2D8"),
         "yomi": ("ヨミ", "読み／黄泉", "#E39BC0")}
IMGFILE = {"mimei": "gogai", "hasu": "hogo", "yomi": "yomi"}   # image file stems (unchanged)
SLOTS = {"mimei": 250, "yomi": 640, "hasu": 1030}   # x-center of each standing character
PORTRAIT_H = 700

script = json.load(open(os.path.join(ROOT, "script.json"), encoding="utf-8"))
meta = json.load(open(os.path.join(ROOT, "audio", "meta.json"), encoding="utf-8"))

portraits = {}
for k in NAMES:
    im = Image.open(os.path.join(ROOT, "img", f"{IMGFILE[k]}.webp")).convert("RGBA")
    s = PORTRAIT_H / im.height
    portraits[k] = im.resize((int(im.width * s), PORTRAIT_H), Image.LANCZOS)

def background():
    bg = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(bg)
    # paper grain: faint horizontal rules
    for y in range(0, H, 3):
        d.line([(0, y), (W, y)], fill="#1D1727")
    # vignette glow top-center
    glow = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-300, -500, W + 300, 700], fill=90)
    glow = glow.filter(ImageFilter.GaussianBlur(160))
    tint = Image.new("RGB", (W, H), PAPER2)
    bg = Image.composite(tint, bg, glow)
    return bg

def masthead(d):
    d.line([(60, 56), (W - 60, 56)], fill=INK, width=3)
    d.line([(60, 62), (W - 60, 62)], fill=INK, width=1)
    d.text((80, 72), "未明新聞", font=F(SERIF, 54), fill=INK)
    d.text((330, 92), "未明シアター 非公式配達所", font=F(SANS, 22), fill=INK2)
    # 号外 seal
    d.rounded_rectangle([W - 230, 80, W - 80, 134], radius=4, outline=SEAL, width=3)
    d.text((W - 155, 107), "号　外", font=F(SERIF, 30), fill=SEAL, anchor="mm")
    d.line([(60, 150), (W - 60, 150)], fill=RULE, width=1)

def wrap(text, font, max_w, d):
    lines, cur = [], ""
    NO_HEAD = "、。」』）…―ー"
    for ch in text:
        if d.textlength(cur + ch, font=font) > max_w and ch not in NO_HEAD:
            lines.append(cur); cur = ch
        else:
            cur += ch
    if cur: lines.append(cur)
    return lines

def article_card(d, img):
    x0, y0, x1, y1 = 1260, 200, W - 70, 620
    d.rectangle([x0, y0, x1, y1], fill=PAPER2, outline=INK, width=2)
    d.rectangle([x0 + 8, y0 + 8, x1 - 8, y1 - 8], outline=RULE, width=1)
    d.rounded_rectangle([x0 + 34, y0 + 34, x0 + 34 + 150, y0 + 72], radius=3, outline=SEAL, width=2)
    d.text((x0 + 109, y0 + 53), script["category"], font=F(SANS, 22), fill=SEAL, anchor="mm")
    d.text((x0 + 200, y0 + 40), "本日の一面", font=F(SANS, 22), fill=MUTED)
    tf = F(SERIF, 56)
    y = y0 + 100
    for ln in wrap(script["title"], tf, x1 - x0 - 70, d):
        d.text((x0 + 34, y), ln, font=tf, fill=INK); y += 72
    sf = F(SANS, 26)
    y += 10
    for ln in wrap(script["subtitle"], sf, x1 - x0 - 70, d):
        d.text((x0 + 34, y), ln, font=sf, fill=INK2); y += 38
    d.text((x0 + 34, y1 - 60), "読むと呪われる？", font=F(SERIF, 24), fill=MUTED)

def frame_for(active, text):
    img = background()
    d = ImageDraw.Draw(img)
    masthead(d)
    article_card(d, img)
    # characters: dim inactive, lift active
    floor = 870
    order = ["hasu", "yomi", "mimei"]  # draw back to front
    if active in order:
        order.remove(active); order.append(active)
    for k in order:
        p = portraits[k]
        if k != active:
            p = ImageEnhance.Brightness(p).enhance(0.38)
            p = ImageEnhance.Color(p).enhance(0.4)
            scale = 0.92
        else:
            scale = 1.0
        p = p.resize((int(p.width * scale), int(p.height * scale)), Image.LANCZOS)
        # drop shadow
        sh = Image.new("RGBA", p.size, (0, 0, 0, 0))
        sh.paste((0, 0, 0, 140), (0, 0), p.split()[3])
        sh = sh.filter(ImageFilter.GaussianBlur(18))
        x = SLOTS[k] - p.width // 2
        y = floor - p.height
        img.paste(sh, (x + 10, y + 22), sh)
        img.paste(p, (x, y), p)
    # subtitle band
    d = ImageDraw.Draw(img)
    d.rectangle([0, 880, W, H], fill="#0F0B17")
    d.line([(0, 880), (W, 880)], fill=RULE, width=1)
    if active:
        name, role, col = NAMES[active]
        d.rounded_rectangle([70, 905, 70 + 170, 905 + 54], radius=6, fill=col)
        d.text((70 + 85, 905 + 27), name, font=F(SERIF, 32), fill="#141018", anchor="mm")
        d.text((70, 968), role, font=F(SANS, 20), fill=MUTED)
        tf = F(SERIF, 40)
        lines = wrap(text, tf, W - 400, d)[:3]
        y = 900 if len(lines) > 2 else 912
        for ln in lines:
            d.text((270, y), ln, font=tf, fill=INK); y += 56
    return img

def title_frame():
    img = background(); d = ImageDraw.Draw(img); masthead(d)
    p = portraits["mimei"].copy()
    s = 0.95
    p = p.resize((int(p.width * s), int(p.height * s)), Image.LANCZOS)
    img.paste(p, (1300, H - p.height - 40), p)
    d = ImageDraw.Draw(img)
    d.text((120, 300), "本日の号外", font=F(SANS, 34), fill=ACCENT)
    tf = F(SERIF, 120)
    y = 360
    for ln in wrap(script["title"], tf, 1100, d):
        d.text((120, y), ln, font=tf, fill=INK); y += 150
    for ln in wrap(script["subtitle"], F(SANS, 36), 1100, d):
        d.text((120, y + 20), ln, font=F(SANS, 36), fill=INK2); y += 50
    d.text((120, H - 110), "読むと呪われる？ ── 新聞をまとった三人が、勝手に届けます。", font=F(SERIF, 28), fill=MUTED)
    return img

def end_frame():
    img = background(); d = ImageDraw.Draw(img); masthead(d)
    p = portraits["pair"] if "pair" in portraits else None
    pair = Image.open(os.path.join(ROOT, "img", "pair.webp")).convert("RGBA")
    s = 760 / pair.height
    pair = pair.resize((int(pair.width * s), 760), Image.LANCZOS)
    img.paste(pair, (W - pair.width - 80, H - 760 - 30), pair)
    d = ImageDraw.Draw(img)
    d.text((120, 330), "配達、完了。", font=F(SERIF, 96), fill=INK)
    d.text((120, 480), "次の号外は、水曜と土曜の夜に。", font=F(SANS, 40), fill=INK2)
    d.rounded_rectangle([120, 580, 620, 660], radius=6, fill=ACCENT)
    d.text((370, 620), "チャンネル登録", font=F(SERIF, 38), fill="#1A1224", anchor="mm")
    d.text((120, 700), "YouTube 未明シアター  @mimei_theater", font=F(SANS, 28), fill=MUTED)
    d.text((120, H - 70), "VOICEVOX:雀松朱司／中部つるぎ／小夜SAYO", font=F(SANS, 22), fill=MUTED)
    return img

def main():
    out = os.path.join(ROOT, "out"); os.makedirs(out, exist_ok=True)
    title_frame().save(os.path.join(out, "f_title.png"))
    end_frame().save(os.path.join(out, "f_end.png"))
    segs = [("f_title.png", TITLE_DUR, None)]
    for m in meta:
        fn = f"f_{m['i']:02d}.png"
        frame_for(m["c"], m["t"]).save(os.path.join(out, fn))
        segs.append((fn, m["dur"] + GAP, m["wav"]))
    segs.append(("f_end.png", END_DUR, None))

    # audio track: concat with silence padding (VOICEVOX: 24kHz mono 16-bit)
    sr = 24000
    chunks = [np.zeros(int(sr * TITLE_DUR), np.int16)]
    for fn, dur, wav in segs[1:-1]:
        with wave.open(wav) as w:
            assert w.getframerate() == sr and w.getnchannels() == 1
            chunks.append(np.frombuffer(w.readframes(w.getnframes()), np.int16))
        chunks.append(np.zeros(int(sr * GAP), np.int16))
    chunks.append(np.zeros(int(sr * END_DUR), np.int16))
    audio = np.concatenate(chunks)
    with wave.open(os.path.join(out, "voice.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(audio.tobytes())

    with open(os.path.join(out, "list.txt"), "w") as f:
        for fn, dur, _ in segs:
            f.write(f"file '{fn}'\nduration {dur:.3f}\n")
        f.write(f"file '{segs[-1][0]}'\n")  # concat demuxer quirk: repeat last
    mp4 = os.path.join(out, "mimei_gogai_merry.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "list.txt",
                    "-i", "voice.wav", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-tune", "stillimage",
                    "-r", "30", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest",
                    "-movflags", "+faststart", mp4], cwd=out, check=True)
    print("wrote", mp4, "total", round(sum(s[1] for s in segs), 1), "s")

if __name__ == "__main__":
    main()
