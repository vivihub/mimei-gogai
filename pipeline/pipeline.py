#!/usr/bin/env python
"""One-shot build: script.json -> voices -> animated MP4 + thumbnail + description.

    python pipeline.py [--script path/to/script.json] [--out-name NAME]

Outputs to out/<NAME>/ : NAME.mp4, NAME_thumb.jpg, NAME_description.txt, script.json (copy).
The script must already exist (written by the Claude session from research). Fails loudly.
"""
import argparse, json, os, shutil, subprocess, sys, datetime
ROOT = os.path.dirname(os.path.abspath(__file__))
VVPY = "/home/claude/vv/vvenv/bin/python"
VVLIB = "/home/claude/vv/voicevox_core-linux-x64-cpu-0.15.7"
CREDIT = "VOICEVOX:雀松朱司／中部つるぎ／小夜SAYO"

def sh(cmd, **kw):
    print("$", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT, **kw)

def validate(script):
    assert script.get("title") and script.get("lines"), "script.json needs title and lines"
    for i, ln in enumerate(script["lines"]):
        assert ln["c"] in ("mimei", "hasu", "yomi"), f"line {i}: unknown speaker {ln['c']}"
        assert ln.get("bgm", "normal") in ("normal", "ominous", "ending"), f"line {i}: bad bgm tag"
        assert 1 <= len(ln["t"]) <= 160, f"line {i}: text length {len(ln['t'])} (keep each line <=140 chars)"
    share = {}
    for ln in script["lines"]:
        share[ln["c"]] = share.get(ln["c"], 0) + len(ln["t"])
    tot = sum(share.values())
    print("speaker share:", {k: f"{v / tot:.0%}" for k, v in share.items()})

def thumbnail(script, dst):
    import render as R
    from PIL import Image, ImageDraw
    img = R.background(); d = ImageDraw.Draw(img); R.masthead(d)
    p = R.portraits["mimei"]
    p = p.resize((int(p.width * 1.15), int(p.height * 1.15)), Image.LANCZOS)
    img.paste(p, (R.W - p.width - 120, R.H - p.height + 60), p)
    d = ImageDraw.Draw(img)
    d.text((110, 250), script.get("category", "未明ダイブ"), font=R.F(R.SANS, 40), fill=R.SEAL)
    tf = R.F(R.SERIF, 150); y = 320
    for ln in R.wrap(script["title"], tf, 1150, d)[:2]:
        d.text((110, y), ln, font=tf, fill=R.INK); y += 180
    hook = script.get("thumb_text") or script.get("subtitle", "")
    for ln in R.wrap(hook, R.F(R.SERIF, 54), 1150, d)[:2]:
        d.text((110, y + 20), ln, font=R.F(R.SERIF, 54), fill=R.ACCENT); y += 72
    img.convert("RGB").save(dst, quality=92)

def description(script, sources, dst):
    import render as R
    lines = [script["title"], "", script.get("subtitle", ""), ""]
    if script.get("summary"): lines += [script["summary"], ""]
    lines += ["■ 出典・参考", *[f"・{s}" for s in sources], "",
              "■ 出演", "ミメイ／ハス／ヨミ（未明新聞）", "",
              "■ チャンネル", f"{R.CHANNEL} {R.CHANNEL_URL}", "", "■ 音声", CREDIT, "",
              "※本動画の音声はAI音声合成、キャラクターの動きはプログラムによる自動生成です。",
              "※内容は公開情報をもとに構成しています。事実関係は出典をご確認ください。", "",
              "#都市伝説 #未解決事件 #オカルト #未明新聞 #ゆっくり解説"]
    open(dst, "w", encoding="utf-8").write("\n".join(lines))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", default=os.path.join(ROOT, "script.json"))
    ap.add_argument("--out-name", default=None)
    a = ap.parse_args()
    script = json.load(open(a.script, encoding="utf-8"))
    validate(script)
    name = a.out_name or f"mimei_{script.get('id', 'ep')}_{datetime.date.today():%Y%m%d}"
    if a.script != os.path.join(ROOT, "script.json"):
        shutil.copy(a.script, os.path.join(ROOT, "script.json"))
    env = dict(os.environ, LD_LIBRARY_PATH=VVLIB)
    sh([VVPY, "-I", "tts.py"], env=env)
    sh([sys.executable, "render_anim.py"])
    outdir = os.path.join(ROOT, "out", name); os.makedirs(outdir, exist_ok=True)
    shutil.move(os.path.join(ROOT, "out", "mimei_merry_v2.mp4"), os.path.join(outdir, f"{name}.mp4"))
    thumbnail(script, os.path.join(outdir, f"{name}_thumb.jpg"))
    description(script, script.get("sources", []), os.path.join(outdir, f"{name}_description.txt"))
    shutil.copy(os.path.join(ROOT, "script.json"), os.path.join(outdir, "script.json"))
    sh([sys.executable, "render_short.py", "--out", os.path.join(outdir, f"{name}_short.mp4")])   # vertical <=60s cut
    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                          os.path.join(outdir, f"{name}.mp4")], capture_output=True, text=True).stdout.strip()
    print(json.dumps({"outdir": outdir, "mp4": f"{name}.mp4", "duration_s": round(float(dur), 1)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
