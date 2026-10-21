#!/usr/bin/env python
"""Synthesize one WAV per script line with VOICEVOX core. Run with the vvenv python."""
import json, os, sys, wave
from voicevox_core import VoicevoxCore

ROOT = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = "/home/claude/vv/voicevox_core-linux-x64-cpu-0.15.7"
DIC = open("/home/claude/vv/dic_path.txt").read().strip()

VOICE = {  # style id, speed, pitch, intonation  (あまり使われていない話者を選定)
    "mimei": dict(sid=52, speed=1.08, pitch=-0.02, intonation=1.0),   # 雀松朱司: 落ち着いた語り・MC
    "hasu":  dict(sid=96, speed=0.90, pitch=-0.06, intonation=0.7),   # 中部つるぎ ヒソヒソ: 囁き
    "yomi":  dict(sid=46, speed=1.12, pitch=0.0,   intonation=1.1),   # 小夜/SAYO: 控えめ・丁寧
}

def main():
    os.chdir(CORE_DIR)  # models are resolved relative to cwd
    script = json.load(open(os.path.join(ROOT, "script.json"), encoding="utf-8"))
    os.makedirs(os.path.join(ROOT, "audio"), exist_ok=True)  # not tracked in git (empty dir) → create on a fresh clone
    core = VoicevoxCore(open_jtalk_dict_dir=DIC)
    for v in VOICE.values():
        core.load_model(v["sid"])
    meta = []
    for i, ln in enumerate(script["lines"]):
        v = VOICE[ln["c"]]
        q = core.audio_query(ln["t"], v["sid"])
        q.speed_scale = v["speed"]; q.pitch_scale = v["pitch"]; q.intonation_scale = v["intonation"]
        q.pre_phoneme_length = 0.08; q.post_phoneme_length = 0.18
        wav = core.synthesis(q, v["sid"])
        path = os.path.join(ROOT, "audio", f"{i:02d}.wav")
        open(path, "wb").write(wav)
        with wave.open(path) as w:
            dur = w.getnframes() / w.getframerate()
        meta.append({"i": i, "c": ln["c"], "t": ln["t"], "wav": path, "dur": round(dur, 3)})
        print(i, ln["c"], f"{dur:.2f}s", ln["t"][:20])
    json.dump(meta, open(os.path.join(ROOT, "audio", "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("total", round(sum(m["dur"] for m in meta), 1), "s")

if __name__ == "__main__":
    main()
