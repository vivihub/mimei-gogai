#!/usr/bin/env python
"""Render frames per line and assemble the MP4 with ffmpeg."""
import json, os, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

ROOT = os.path.dirname(os.path.abspath(__file__))
W, H = 1920, 1080
GAP, TITLE_DUR, END_DUR = 0.18, 1.5, 3.2   # 冒頭タイトルカードは1.5秒（離脱対策で短く）

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
CHANNEL = "聞かせて、怪異放送。"            # YouTube チャンネル名（マストヘッド・エンドカード）
CHANNEL_HANDLE = "@聞かせて怪異放送"
CHANNEL_URL = "https://www.youtube.com/@聞かせて怪異放送"
SLOTS = {"mimei": 250, "yomi": 640, "hasu": 1030}   # x-center of each standing character
PORTRAIT_H = 700

script = json.load(open(os.path.join(ROOT, "script.json"), encoding="utf-8"))
meta = json.load(open(os.path.join(ROOT, "audio", "meta.json"), encoding="utf-8"))

portraits = {}
for k in NAMES:
    im = Image.open(os.path.join(ROOT, "img", f"{IMGFILE[k]}.webp")).convert("RGBA")
    s = PORTRAIT_H / im.height
    portraits[k] = im.resize((int(im.width * s), PORTRAIT_H), Image.LANCZOS)

# ---- 場面絵（scenes/<key>.jpg 1920x1080）。台本の行に "scene": "<key>" を付けると、その行以降の背景になる ----
SCENE_DIR = os.path.join(ROOT, "scenes")
SCENES = {}
if os.path.isdir(SCENE_DIR):
    for fn in sorted(os.listdir(SCENE_DIR)):
        k, ext = os.path.splitext(fn)
        if ext.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            im = Image.open(os.path.join(SCENE_DIR, fn)).convert("RGB")
            if im.size != (W, H):
                s = max(W / im.width, H / im.height)
                im = im.resize((int(im.width * s + 0.5), int(im.height * s + 0.5)), Image.LANCZOS)
                im = im.crop(((im.width - W) // 2, (im.height - H) // 2, (im.width - W) // 2 + W, (im.height - H) // 2 + H))
            SCENES[k] = im
KB_ZOOM = 0.07   # Ken Burns: 場面の最初から最後までで 7% ズーム

# ---- 場面クリップ（scenes/<key>.mp4、Runway image-to-video の10秒）。あれば静止画ズームの代わりに使う ----
CLIP_SLOW = 1.5      # 1.5倍スロー（10秒クリップ → 15秒。2026-10-25 に 2→1.5 で動きを強めた）、端で折り返すピンポン再生でループの継ぎ目を消す
CLIP_FPS = 30
_CLIP_FRAMES = {}    # key -> list of jpg paths
def clip_frames(key):
    """クリップを out/clipframes/<key>/ に 1920x1080 30fps の JPEG 連番で展開（初回のみ）。無ければ None。"""
    if key in _CLIP_FRAMES: return _CLIP_FRAMES[key]
    mp4 = os.path.join(SCENE_DIR, f"{key}.mp4")
    if not os.path.exists(mp4): _CLIP_FRAMES[key] = None; return None
    d = os.path.join(ROOT, "out", "clipframes", key); os.makedirs(d, exist_ok=True)
    if not os.listdir(d):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mp4, "-vf", f"fps={CLIP_FPS},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}",
                        "-q:v", "3", os.path.join(d, "%04d.jpg")], check=True)
    fr = sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".jpg"))
    _CLIP_FRAMES[key] = fr if len(fr) > 2 else None
    return _CLIP_FRAMES[key]

def clip_frame(key, t_rel):
    """場面開始からの経過秒 t_rel に対応するクリップのフレーム（半速・ピンポン）。"""
    fr = clip_frames(key); n = len(fr)
    i = int(t_rel * CLIP_FPS / CLIP_SLOW) % (2 * n - 2)
    if i >= n: i = 2 * n - 2 - i
    return Image.open(fr[i]).convert("RGB")
TELOP_COL = "#FFD35C"

def assign_scenes(lines):
    """各行に scene（継続）を解決して返す。"scene": "" で舞台（三人）に戻る。無い画像は無視。"""
    cur, out = None, []
    for ln in lines:
        if "scene" in ln:
            k = ln["scene"] or None
            if k and k not in SCENES:
                print(f"warn: scene image missing: {k}", flush=True); k = cur
            cur = k
        out.append(cur)
    return out

def scene_bg(key, progress, idx=0, t_rel=None):
    """場面の背景。クリップがあればそのフレーム、無ければ場面絵をゆっくりズーム（＋わずかな横ドリフト）。progress 0..1。"""
    if t_rel is not None and clip_frames(key):
        return clip_frame(key, t_rel)
    im = SCENES[key]
    z = 1.0 + KB_ZOOM * max(0.0, min(1.0, progress))
    cw, ch = int(W / z), int(H / z)
    drift = (W - cw) * (0.5 + (0.5 if idx % 2 == 0 else -0.5) * (progress - 0.5))
    x0 = int(max(0, min(W - cw, drift))); y0 = (H - ch) // 2
    return im.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.BILINEAR)

def scene_dim(key, amount=0.42):
    im = ImageEnhance.Brightness(SCENES[key]).enhance(amount)
    return im.filter(ImageFilter.GaussianBlur(2))

_GRADIENT = None
def bottom_gradient():
    """場面絵の下側を字幕帯の色へ溶かす RGBA レイヤー（y=620..880）。"""
    global _GRADIENT
    if _GRADIENT is None:
        g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        px = g.load()
        for y in range(600, 880):
            a = int(235 * ((y - 600) / 280) ** 1.4)
            for x in range(W): px[x, y] = (15, 11, 23, a)
        # 上側にもうっすら（マストヘッドの可読性）
        for y in range(0, 170):
            a = int(170 * (1 - y / 170) ** 1.2)
            for x in range(W): px[x, y] = (15, 11, 23, a)
        _GRADIENT = g
    return _GRADIENT

def telop_image(text, size=110):
    """キーワードテロップ（黄色・落ち影）を RGBA で描く。"""
    f = F(SERIF, size)
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    w = int(tmp.textlength(text, font=f)) + 24; h = int(size * 1.35)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.text((10 + 5, 8 + 5), text, font=f, fill=(0, 0, 0, 230))
    d.text((10, 8), text, font=f, fill=TELOP_COL)
    return im

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
    d.text((80, 72), CHANNEL, font=F(SERIF, 54), fill=INK)            # 番組名を主題字に
    cw = d.textlength(CHANNEL, font=F(SERIF, 54))
    d.text((80 + cw + 30, 92), "未明新聞　号外配達", font=F(SANS, 22), fill=INK2)
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

def subtitle_band(d, active, text):
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

def frame_for(active, text, scene=None, progress=0.5, telop=None):
    if scene:
        img = scene_bg(scene, progress); img.paste(bottom_gradient(), (0, 0), bottom_gradient())
        d = ImageDraw.Draw(img); masthead(d)
        if active:
            p = portraits[active]; p = p.resize((int(p.width * 0.6), int(p.height * 0.6)), Image.LANCZOS)
            img.paste(p, (W - p.width - 90, 880 - p.height), p)
        d = ImageDraw.Draw(img); subtitle_band(d, active, text)
        if telop:
            t = telop_image(telop); img.paste(t, (110, 200), t)
        return img
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
    subtitle_band(d, active, text)
    if telop:
        t = telop_image(telop, 72); img.paste(t, (1260, 660), t)
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
    d.text((120, 700), f"YouTube {CHANNEL}  {CHANNEL_HANDLE}", font=F(SANS, 28), fill=MUTED)
    d.text((120, H - 70), "VOICEVOX:雀松朱司／中部つるぎ／小夜SAYO", font=F(SANS, 22), fill=MUTED)
    return img

CHAPTER_DUR = 2.0

def chapter_frame(num, text, scene=None):
    img = scene_dim(scene) if scene else background()
    d = ImageDraw.Draw(img); masthead(d)
    d.line([(120, 420), (420, 420)], fill=ACCENT, width=4)
    d.text((120, 300), f"第{num}面", font=F(SANS, 40), fill=ACCENT)
    tf = F(SERIF, 100); y = 450
    for ln in wrap(text, tf, W - 240, d)[:2]:
        d.text((120, y), ln, font=tf, fill=INK); y += 130
    return img

def timeline():
    """Shared segment list: (kind, dur, payload). kind = title|chapter|line|end.
    line payload = meta dict に scene / scene_t0 / scene_t1 / scene_idx / telop を足したもの。"""
    segs = [("title", TITLE_DUR, None)]
    n = 0
    scenes = assign_scenes(script["lines"])
    import fx as FX
    fxs = FX.assign(script["lines"], scenes)
    t = TITLE_DUR
    for m, ln, sc, fxset in zip(meta, script["lines"], scenes, fxs):
        if ln.get("chapter"):
            n += 1; segs.append(("chapter", CHAPTER_DUR, (n, ln["chapter"], sc))); t += CHAPTER_DUR
        m = dict(m); m["scene"] = sc; m["telop"] = ln.get("telop"); m["fx"] = fxset; m["t0"] = t
        segs.append(("line", m["dur"] + GAP, m)); t += m["dur"] + GAP
    segs.append(("end", END_DUR, None))
    # 場面ごとの開始・終了時刻（Ken Burns を場面全体で連続させる）
    spans, cur, idx = {}, None, -1
    for kind, dur, p in segs:
        if kind != "line": continue
        if p["scene"] != cur:
            cur = p["scene"]; idx += 1
            if cur: spans[idx] = [p["t0"], p["t0"] + dur]
        elif cur: spans[idx][1] = p["t0"] + dur
        p["scene_idx"] = idx
        p["scene_t0"], p["scene_t1"] = (spans[idx] if cur else (p["t0"], p["t0"] + dur))
    for kind, dur, p in segs:
        if kind == "line" and p["scene"]:
            p["scene_t1"] = spans[p["scene_idx"]][1]
    return segs

def main():
    out = os.path.join(ROOT, "out"); os.makedirs(out, exist_ok=True)
    title_frame().save(os.path.join(out, "f_title.png"))
    end_frame().save(os.path.join(out, "f_end.png"))
    segs = []
    for kind, dur, p in timeline():
        if kind == "title": segs.append(("f_title.png", dur, None))
        elif kind == "end": segs.append(("f_end.png", dur, None))
        elif kind == "chapter":
            fn = f"f_ch{p[0]:02d}.png"; chapter_frame(*p).save(os.path.join(out, fn)); segs.append((fn, dur, None))
        else:
            prog = (p["t0"] - p["scene_t0"]) / max(0.1, p["scene_t1"] - p["scene_t0"])
            fn = f"f_{p['i']:02d}.png"; frame_for(p["c"], p["t"], p["scene"], prog, p["telop"]).save(os.path.join(out, fn)); segs.append((fn, dur, p["wav"]))

    # audio track: concat with silence padding (VOICEVOX: 24kHz mono 16-bit)
    sr = 24000
    chunks = []
    for fn, dur, wav in segs:
        if wav is None:
            chunks.append(np.zeros(int(sr * dur), np.int16)); continue
        with wave.open(wav) as w:
            assert w.getframerate() == sr and w.getnchannels() == 1
            chunks.append(np.frombuffer(w.readframes(w.getnframes()), np.int16))
        chunks.append(np.zeros(int(sr * GAP), np.int16))
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
