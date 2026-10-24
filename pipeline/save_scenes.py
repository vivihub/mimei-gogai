#!/usr/bin/env python3
"""場面絵を episodes/scenes/<id>/<key>.jpg に保存する（1920x1080 に正規化）。

  python3 save_scenes.py <episode_id> key=URL_or_path [key=URL_or_path ...]

URL は Canva export-design が返す一時ダウンロードURL（有効期限あり）でも、ローカルのファイルパスでもよい。
"""
import os, sys, subprocess, io
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
W, H = 1920, 1080

def fetch(src):
    if src.startswith("http"):
        return subprocess.run(["curl", "-sSL", "--max-time", "120", src], check=True, capture_output=True).stdout
    return open(src, "rb").read()

def normalize(data):
    im = Image.open(io.BytesIO(data)).convert("RGB")
    s = max(W / im.width, H / im.height)
    im = im.resize((int(im.width * s + 0.5), int(im.height * s + 0.5)), Image.LANCZOS)
    x0, y0 = (im.width - W) // 2, (im.height - H) // 2
    return im.crop((x0, y0, x0 + W, y0 + H))

def main():
    if len(sys.argv) < 3: print(__doc__); sys.exit(1)
    ep = sys.argv[1]; outdir = os.path.join(ROOT, "episodes", "scenes", ep); os.makedirs(outdir, exist_ok=True)
    for arg in sys.argv[2:]:
        key, src = arg.split("=", 1)
        try:
            normalize(fetch(src)).save(os.path.join(outdir, f"{key}.jpg"), quality=90)
            print("saved", key)
        except Exception as e:
            print("FAILED", key, e, file=sys.stderr)
    print("scenes:", sorted(os.listdir(outdir)))

if __name__ == "__main__":
    main()
