#!/usr/bin/env python
"""Mix BGM under the voice track by scene tag.

Put tracks in  bgm/normal.*  bgm/ominous.*  bgm/ending.*  (mp3/wav/m4a; any one may be missing).
Scenes come from each line's "bgm" field in script.json; the title card uses the first line's scene,
the end card uses "ending". Tracks loop, cross-fade 1.2 s at scene changes, and duck -8 dB while
the voice is active. Output: out/mix.wav (24 kHz stereo). If bgm/ is empty, out/mix.wav = voice only.
"""
import json, os, glob, subprocess, wave
import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out"); BGM = os.path.join(ROOT, "bgm")
SR = 24000
LEVEL = {"normal": -24, "ominous": -22, "ending": -20}   # dBFS target for the bed
DUCK_DB, XFADE, FADE_OUT = -8, 1.2, 2.0

def load_track(scene):
    files = glob.glob(os.path.join(BGM, f"{scene}.*"))
    if not files: return None
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", files[0], "-f", "s16le", "-ac", "2", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32).reshape(-1, 2) / 32768
    rms = np.sqrt(np.mean(x ** 2)) or 1e-6
    return x * (10 ** (LEVEL[scene] / 20) / rms)

def main():
    import render as R
    script = json.load(open(os.path.join(ROOT, "script.json"), encoding="utf-8"))
    meta = json.load(open(os.path.join(ROOT, "audio", "meta.json"), encoding="utf-8"))
    with wave.open(os.path.join(OUT, "voice.wav")) as w:
        voice = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    n = len(voice)
    tracks = {s: load_track(s) for s in LEVEL}
    if not any(t is not None for t in tracks.values()):
        print("no bgm tracks found; voice only"); mix = np.stack([voice, voice], 1)
    else:
        # scene timeline
        segs = []; t = 0.0
        first = script["lines"][0].get("bgm", "normal")
        segs.append((first, t, t + R.TITLE_DUR)); t += R.TITLE_DUR
        for m, ln in zip(meta, script["lines"]):
            d = m["dur"] + R.GAP; segs.append((ln.get("bgm", "normal"), t, t + d)); t += d
        segs.append(("ending", t, t + R.END_DUR))
        # merge consecutive same-scene segments
        merged = []
        for s, a, b in segs:
            if merged and merged[-1][0] == s: merged[-1] = (s, merged[-1][1], b)
            else: merged.append((s, a, b))
        bed = np.zeros((n, 2), np.float32); pos = {s: 0 for s in LEVEL}
        xf = int(XFADE * SR)
        for s, a, b in merged:
            tr = tracks[s]
            if tr is None: continue
            i0, i1 = int(a * SR), min(n, int(b * SR) + xf)
            L = i1 - i0
            start = pos[s]; idx = (np.arange(L) + start) % len(tr); pos[s] = (start + L) % len(tr)
            chunk = tr[idx].copy()
            ramp_in = np.minimum(1, np.arange(L) / xf)[:, None] if i0 > 0 else np.ones((L, 1))
            ramp_out = np.minimum(1, (L - np.arange(L)) / xf)[:, None]
            bed[i0:i1] += chunk * ramp_in * ramp_out
        # ducking from voice envelope (50 ms RMS, 300 ms release)
        hop = int(0.05 * SR)
        env = np.array([np.sqrt(np.mean(voice[i:i + hop] ** 2)) for i in range(0, n, hop)])
        gate = (env > 0.01).astype(np.float32)
        rel = int(0.3 / 0.05)
        for i in range(1, len(gate)): gate[i] = max(gate[i], gate[i - 1] - 1 / rel)
        g = np.repeat(gate, hop)[:n]
        duck = 10 ** (DUCK_DB / 20)
        gain = 1 - g * (1 - duck)
        bed *= gain[:, None]
        bed[-int(FADE_OUT * SR):] *= np.linspace(1, 0, int(FADE_OUT * SR))[:, None]
        mix = bed + np.stack([voice, voice], 1)
        peak = np.abs(mix).max()
        if peak > 0.98: mix *= 0.98 / peak
    out = (mix * 32767).astype(np.int16)
    with wave.open(os.path.join(OUT, "mix.wav"), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(out.tobytes())
    print("wrote out/mix.wav")

if __name__ == "__main__":
    main()
