#!/usr/bin/env python
"""Animated render: lip-sync (号外) from the audio envelope, blinks + talking bob (ホゴ・ヨミ), breathing for all.
Frames are streamed to ffmpeg as raw RGB; nothing hits the disk except the final MP4."""
import json, os, subprocess, wave, math, random
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
import render as R  # reuse layout, fonts, colours, title/end cards

ROOT, W, H, FPS = R.ROOT, R.W, R.H, 30
GAP, TITLE_DUR, END_DUR = R.GAP, R.TITLE_DUR, R.END_DUR
OUT = os.path.join(ROOT, "out")

def load(name):
    im = Image.open(os.path.join(ROOT, "img", f"{name}.webp")).convert("RGBA")
    s = R.PORTRAIT_H / im.height
    return im.resize((int(im.width * s), R.PORTRAIT_H), Image.LANCZOS)

VARIANTS = {"mimei": {"m0": load("gogai_m0"), "m1": load("gogai_m1"), "m2": load("gogai_m2")},
            "hasu":  {"e0": load("hogo_e0"), "e1": load("hogo_e1"), "e2": load("hogo_e2")},
            "yomi":  {"e0": load("yomi_e0"), "e1": load("yomi_e1"), "e2": load("yomi_e2")}}

def dim(im):
    im = ImageEnhance.Brightness(im).enhance(0.38)
    return ImageEnhance.Color(im).enhance(0.4)
DIMMED = {k: {v: dim(im) for v, im in d.items()} for k, d in VARIANTS.items()}

def shadow_for(im):
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sh.paste((0, 0, 0, 140), (0, 0), im.split()[3])
    return sh.filter(ImageFilter.GaussianBlur(18))
SHADOW = {k: shadow_for(d[next(iter(d))]) for k, d in VARIANTS.items()}
# 場面絵モード用: 話者を小さく（0.6倍）右下に
SMALL_SCALE = 0.6
SMALL = {k: {v: im.resize((int(im.width * SMALL_SCALE), int(im.height * SMALL_SCALE)), Image.LANCZOS) for v, im in d.items()}
         for k, d in VARIANTS.items()}
SMALL_SHADOW = {k: shadow_for(d[next(iter(d))]) for k, d in SMALL.items()}
TELOP_POP = 8   # テロップのポップイン フレーム数

def envelope(wav_path, n_frames):
    """RMS per video frame, normalised 0..1."""
    with wave.open(wav_path) as w:
        sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float) / 32768
    per = sr / FPS
    env = np.array([np.sqrt(np.mean(x[int(i * per):int((i + 1) * per)] ** 2) or 0) if int(i * per) < len(x) else 0
                    for i in range(n_frames)])
    if env.max() > 0: env = env / env.max()
    # light smoothing so the mouth doesn't flicker
    k = np.array([0.25, 0.5, 0.25]); env = np.convolve(env, k, mode="same")
    return env

def mouth_state(e):
    return "m2" if e > 0.45 else "m1" if e > 0.15 else "m0"

class Blinker:
    """Random blinks every 2.5–5 s; a blink is e1,e2,e2,e1 over 4 frames."""
    def __init__(self, seed):
        self.rng = random.Random(seed); self.next_t = self.rng.uniform(1.0, 3.0); self.seq = []
    def state(self, t):
        if not self.seq and t >= self.next_t:
            self.seq = ["e1", "e2", "e2", "e1"]; self.next_t = t + self.rng.uniform(2.5, 5.0)
        return self.seq.pop(0) if self.seq else "e0"

def static_base(active, text):
    """Everything except the characters: background, masthead, article, subtitle band."""
    img = R.background(); d = ImageDraw.Draw(img); R.masthead(d); R.article_card(d, img)
    R.subtitle_band(d, active, text)
    return img

def scene_overlay(active, text):
    """場面絵モードの前景（RGBA）: 下グラデーション・マストヘッド・字幕帯。背景は毎フレーム動くので分けて持つ。"""
    ov = R.bottom_gradient().copy(); d = ImageDraw.Draw(ov)
    R.masthead(d)
    R.subtitle_band(d, active, text)
    return ov

def paste_telop(img, telop_im, pos, i):
    """ポップイン: 最初の TELOP_POP フレームで 1.25→1.0 倍・透明→不透明。"""
    if i < TELOP_POP:
        k = i / TELOP_POP; sc = 1.0 + 0.25 * (1 - k)
        t = telop_im.resize((int(telop_im.width * sc), int(telop_im.height * sc)), Image.BILINEAR)
        a = t.split()[3].point(lambda v: int(v * k))
        img.paste(t, (pos[0] - (t.width - telop_im.width) // 2, pos[1] - (t.height - telop_im.height) // 2), a)
    else:
        img.paste(telop_im, pos, telop_im)

def compose_scene(m, overlay, active, states, t_global, talk_env, i):
    prog = (t_global - m["scene_t0"]) / max(0.1, m["scene_t1"] - m["scene_t0"])
    img = R.scene_bg(m["scene"], prog, m["scene_idx"])
    img.paste(overlay, (0, 0), overlay)
    if active:
        src = SMALL[active][states[active]]
        bob = 1.5 * math.sin(2 * math.pi * 0.25 * t_global)
        if active != "mimei": bob += 4.0 * talk_env * math.sin(2 * math.pi * 3.5 * t_global)
        x = W - src.width - 90; y = 880 - src.height + int(round(bob))
        img.paste(SMALL_SHADOW[active], (x + 8, y + 18 - int(round(bob))), SMALL_SHADOW[active])
        img.paste(src, (x, y), src)
        band = overlay.crop((0, 880, W, H)); img.paste(band, (0, 880), band)
    return img

def compose(base, active, states, t_global, talk_env, blinkers):
    """Paste the three characters onto a copy of base. states: variant per character."""
    img = base.copy()
    floor = 870
    order = ["hasu", "yomi", "mimei"]
    if active in order: order.remove(active); order.append(active)
    for k in order:
        is_active = (k == active)
        variant = states[k]
        src = (VARIANTS if is_active else DIMMED)[k][variant]
        scale = 1.0 if is_active else 0.92
        # breathing: 1.5 px slow bob; talking bob for the two without a mouth
        bob = 1.5 * math.sin(2 * math.pi * 0.25 * t_global + hash(k) % 7)
        if is_active and k != "mimei":
            bob += 4.0 * talk_env * math.sin(2 * math.pi * 3.5 * t_global)
        p = src if scale == 1.0 else src.resize((int(src.width * scale), int(src.height * scale)), Image.LANCZOS)
        sh = SHADOW[k] if scale == 1.0 else SHADOW[k].resize(p.size, Image.BILINEAR)
        x = R.SLOTS[k] - p.width // 2
        y = floor - p.height + int(round(bob))
        img.paste(sh, (x + 10, y + 22 - int(round(bob))), sh)   # shadow stays on the floor
        img.paste(p, (x, y), p)
        # subtitle band must stay on top of the characters' feet
    band = base.crop((0, 880, W, H)); img.paste(band, (0, 880))
    return img

def main():
    script = json.load(open(os.path.join(ROOT, "script.json"), encoding="utf-8"))
    meta = json.load(open(os.path.join(ROOT, "audio", "meta.json"), encoding="utf-8"))
    mp4 = os.path.join(OUT, "mimei_merry_v2.mp4")
    voice = os.path.join(OUT, "voice.wav")
    R.main()  # rebuilds voice.wav (and the static version) from the current script/audio
    import mix_bgm; mix_bgm.main()
    voice = os.path.join(OUT, "mix.wav")
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", voice,
                           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                           "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", mp4],
                          stdin=subprocess.PIPE)
    def emit(img): ff.stdin.write(img.convert("RGB").tobytes())

    t = 0.0
    blinkers = {k: Blinker(i) for i, k in enumerate(["mimei", "hasu", "yomi"])}
    for kind, dur, p in R.timeline():
        if kind == "title":
            fr = R.title_frame().convert("RGB").tobytes()
            for _ in range(int(dur * FPS)): ff.stdin.write(fr)
            t += dur; continue
        if kind == "chapter":
            fr = R.chapter_frame(*p).convert("RGB").tobytes()
            for _ in range(int(dur * FPS)): ff.stdin.write(fr)
            t += dur; continue
        if kind == "end": break
        m = p
        scene = m.get("scene")
        base = scene_overlay(m["c"], m["t"]) if scene else static_base(m["c"], m["t"])
        telop = R.telop_image(m["telop"], 110 if scene else 72) if m.get("telop") else None
        telop_pos = (110, 200) if scene else (1260, 660)
        n = int(round(dur * FPS))
        env = envelope(m["wav"], n)
        for i in range(n):
            tt = t + i / FPS
            states = {}
            for k in ["mimei", "hasu", "yomi"]:
                if k == "mimei":
                    states[k] = mouth_state(env[i]) if m["c"] == "mimei" else "m0"
                else:
                    states[k] = blinkers[k].state(tt)
            if scene: fr = compose_scene(m, base, m["c"], states, tt, float(env[i]), i)
            else: fr = compose(base, m["c"], states, tt, float(env[i]), blinkers)
            if telop is not None: paste_telop(fr, telop, telop_pos, i)
            emit(fr)
        t += n / FPS
        print(f"line {m['i']:02d} done  t={t:.1f}s", flush=True)
    end = R.end_frame().convert("RGB").tobytes()
    for _ in range(int(END_DUR * FPS)): ff.stdin.write(end)
    ff.stdin.close(); ff.wait()
    print("wrote", mp4)

if __name__ == "__main__":
    main()
