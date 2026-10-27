#!/usr/bin/env python
"""One-shot build: script.json -> voices -> animated MP4 + thumbnail + description.

    python pipeline.py [--script path/to/script.json] [--out-name NAME]

Outputs to out/<NAME>/ : NAME.mp4, NAME_thumb.jpg, NAME_description.txt, script.json (copy).
The script must already exist (written by the Claude session from research). Fails loudly.
"""
import argparse, json, os, shutil, subprocess, sys, datetime
ROOT = os.path.dirname(os.path.abspath(__file__))
import glob as _glob
VV = os.environ.get("MIMEI_VV", "/home/claude/vv")              # VOICEVOX 一式の置き場（Mac mini は ~/mimei/vv）
VVPY = os.path.join(VV, "vvenv", "bin", "python")
VVLIB = (sorted(_glob.glob(os.path.join(VV, "voicevox_core-*-0.15.7"))) or [os.path.join(VV, "voicevox_core-linux-x64-cpu-0.15.7")])[0]
CREDIT = "VOICEVOX:雀松朱司／中部つるぎ／小夜SAYO"
THUMB_HOOK = "#FFD35C"   # サムネ・ショート冒頭テロップの「問い」の色（紫背景に対して最も目立つ暖色）

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

def hook_lines(hook, font, width, d):
    """thumb_text を最大2行に。「／」か改行があればそこで折る（語の途中で折れるのを避ける）。"""
    import render as R
    if "／" in hook or "\n" in hook:
        return [x.strip() for x in hook.replace("\n", "／").split("／") if x.strip()][:2]
    return R.wrap(hook, font, width, d)[:2]

def thumbnail(script, dst):
    import render as R
    from PIL import Image, ImageDraw
    # 背景: 最初の場面絵があればそれを暗くして敷く（CTR対策: 話の情景が見える）
    first = next((ln.get("scene") for ln in script["lines"] if ln.get("scene")), None)
    img = R.scene_dim(first, 0.5) if first and first in R.SCENES else R.background()
    d = ImageDraw.Draw(img); R.masthead(d)
    # 三人を右側に（ハス・ヨミは奥で小さく暗め、ミメイが手前で大きく）
    from PIL import ImageEnhance, ImageFilter
    def put(k, scale, xc, dim=1.0):
        p = R.portraits[k]
        p = p.resize((int(p.width * scale), int(p.height * scale)), Image.LANCZOS)
        if dim < 1.0:
            p = ImageEnhance.Brightness(p).enhance(dim); p = ImageEnhance.Color(p).enhance(0.6)
        sh = Image.new("RGBA", p.size, (0, 0, 0, 0)); sh.paste((0, 0, 0, 150), (0, 0), p.split()[3])
        sh = sh.filter(ImageFilter.GaussianBlur(20))
        x, y = xc - p.width // 2, R.H - p.height + 40
        img.paste(sh, (x + 12, y + 24), sh); img.paste(p, (x, y), p)
    put("hasu", 0.9, 1230, 0.62); put("yomi", 0.95, 1440, 0.75); put("mimei", 1.12, R.W - 270)
    d = ImageDraw.Draw(img)
    # CTR対策: 「問い」(thumb_text) を最大サイズ・高コントラスト色で主役に、題名は上に小さく添える
    d.text((110, 230), R.LABEL, font=R.F(R.SANS, 36), fill=R.SEAL)
    tf = R.F(R.SERIF, 84); y = 290
    for ln in R.wrap(script["title"], tf, 1000, d)[:1]:
        d.text((110, y), ln, font=tf, fill=R.INK); y += 120
    hook = script.get("thumb_text") or script.get("subtitle", "")
    hf = R.F(R.SERIF, 100); y += 30
    lines = hook_lines(hook, hf, 880, d)
    for ln in lines:
        d.text((114, y + 4), ln, font=hf, fill="#000000")       # 落ち影
        d.text((110, y), ln, font=hf, fill=THUMB_HOOK); y += int(hf.size * 1.18)
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
    # 場面絵: episodes/scenes/<id>/*.jpg → scenes/ （render.py が読む）。無ければ舞台のみで描く
    sdir = os.path.join(ROOT, "scenes"); shutil.rmtree(sdir, ignore_errors=True); os.makedirs(sdir)
    src = os.path.join(os.path.dirname(os.path.abspath(a.script)), "scenes", script.get("id", ""))
    if os.path.isdir(src):
        for fn in os.listdir(src):
            if fn.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".mp4")): shutil.copy(os.path.join(src, fn), sdir)
        shutil.rmtree(os.path.join(ROOT, "out", "clipframes"), ignore_errors=True)   # 前回のクリップ展開を捨てる
        print("scenes:", sorted(os.listdir(sdir)), flush=True)
    used = {ln.get("scene") for ln in script["lines"] if ln.get("scene")}
    missing = sorted(k for k in used if not any(f.startswith(k + ".") for f in os.listdir(sdir)))
    if missing: print("warn: scene images missing (fallback to studio):", missing, flush=True)
    env = dict(os.environ, LD_LIBRARY_PATH=VVLIB, DYLD_LIBRARY_PATH=VVLIB)   # Linux / macOS
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
