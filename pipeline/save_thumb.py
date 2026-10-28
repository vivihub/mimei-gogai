#!/usr/bin/env python3
"""手作りサムネ（ChatGPT 等で作った画像）を episodes/thumbs/<id>.jpg に保存する（1280x720・JPEG・2MB以下に正規化）。

  python3 save_thumb.py <episode_id> <URL_or_path>

ここに置いた画像は pipeline.py / upload_youtube.py が自動サムネより優先して使う（自動サムネは <name>_thumb_auto.jpg に残る）。
投稿後に差し替えるときは: python3 upload_youtube.py --dir out/<name> --thumb-only
"""
import os, sys, subprocess, io
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
W, H = 1280, 720
MAX_BYTES = 2 * 1024 * 1024   # YouTube custom thumbnail limit

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

def save_jpeg(im, dst):
    for q in (92, 88, 84, 80, 75, 70):
        im.save(dst, "JPEG", quality=q, optimize=True)
        if os.path.getsize(dst) <= MAX_BYTES: return q
    return 70

def custom_thumb_path(ep):
    """episodes/thumbs/<id>.(jpg|jpeg|png|webp) があればそのパス、無ければ None。"""
    d = os.path.join(ROOT, "episodes", "thumbs")
    for ext in ("jpg", "jpeg", "png", "webp"):
        p = os.path.join(d, f"{ep}.{ext}")
        if os.path.exists(p): return p
    return None

def main():
    if len(sys.argv) != 3: print(__doc__); sys.exit(1)
    ep, src = sys.argv[1], sys.argv[2]
    outdir = os.path.join(ROOT, "episodes", "thumbs"); os.makedirs(outdir, exist_ok=True)
    dst = os.path.join(outdir, f"{ep}.jpg")
    q = save_jpeg(normalize(fetch(src)), dst)
    print(f"saved {dst} ({os.path.getsize(dst)} bytes, q={q})")

if __name__ == "__main__":
    main()
