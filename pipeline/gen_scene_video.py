#!/usr/bin/env python3
"""場面絵（episodes/scenes/<id>/<key>.jpg）を Runway の image-to-video で 10 秒クリップ（<key>.mp4）にする。

  python3 gen_scene_video.py <episode_id> [--keys hook,ch1] [--duration 10] [--model gen4_turbo] [--force]

API キー: 環境変数 RUNWAYML_API_SECRET、無ければ /home/claude/runway_api_key.txt（Drive「未明新聞_自動生成動画」から取り出す）。
キーが無い・失敗した場面はスキップし、render.py が静止画ズームにフォールバックする。mp4 は git に入れない（.gitignore 済み）。
コスト目安: gen4_turbo は 5 クレジット/秒（10 秒 = 50 クレジット ≒ $0.50）。
"""
import argparse, base64, io, json, os, subprocess, sys, time

ROOT = os.path.dirname(os.path.abspath(__file__))
KEY_FILE = "/home/claude/runway_api_key.txt"
MOTION = ("Clear, smooth, continuous motion: a slow camera push-in or lateral drift, thick mist rolling through, clouds "
          "moving across the sky, light sources flickering and casting moving shadows, trees and grass swaying, water "
          "rippling, loose paper or leaves drifting. Keep the composition, colors and every object as in the image. "
          "No new objects, no people appearing, no text, no camera cuts, no violent shaking.")
# 台本の "motion": {"hook": "...", ...} に場面ごとの動きの指示（英語）があれば MOTION の前に足す（例: headlights sweeping
# across the tunnel wall, a door slowly opening, fog creeping along the road）。無ければ MOTION だけ。

def api_key():
    k = os.environ.get("RUNWAYML_API_SECRET")
    if not k and os.path.exists(KEY_FILE):
        k = open(KEY_FILE).read().strip()
    return k or None

def data_uri(path, max_w=1280):
    from PIL import Image
    im = Image.open(path).convert("RGB")
    if im.width > max_w:
        im = im.resize((max_w, int(im.height * max_w / im.width)), Image.LANCZOS)
    buf = io.BytesIO(); im.save(buf, "JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

def download(url, dst):
    subprocess.run(["curl", "-sSL", "--max-time", "300", "-o", dst, url], check=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode"); ap.add_argument("--keys", default=None)
    ap.add_argument("--duration", type=int, default=10, choices=[5, 10])
    ap.add_argument("--model", default="gen4_turbo"); ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    key = api_key()
    if not key:
        print("runway: no API key (RUNWAYML_API_SECRET / runway_api_key.txt) — skipping, stills will be used", file=sys.stderr)
        sys.exit(0)
    from runwayml import RunwayML, TaskFailedError
    client = RunwayML(api_key=key)
    sdir = os.path.join(ROOT, "episodes", "scenes", a.episode)
    ep_json = os.path.join(ROOT, "episodes", f"{a.episode}.json")
    ep = json.load(open(ep_json, encoding="utf-8")) if os.path.exists(ep_json) else {}
    prompts, motions = ep.get("scenes", {}), ep.get("motion", {})
    keys = a.keys.split(",") if a.keys else sorted(os.path.splitext(f)[0] for f in os.listdir(sdir) if f.lower().endswith(".jpg"))
    ok, failed = [], []
    for k in keys:
        jpg, mp4 = os.path.join(sdir, f"{k}.jpg"), os.path.join(sdir, f"{k}.mp4")
        if not os.path.exists(jpg): failed.append((k, "no jpg")); continue
        if os.path.exists(mp4) and not a.force: ok.append(k); print(k, "exists"); continue
        prompt = " ".join(x for x in (prompts.get(k, ""), motions.get(k, ""), MOTION) if x).strip()
        t0 = time.time()
        try:
            task = client.image_to_video.create(model=a.model, prompt_image=data_uri(jpg), prompt_text=prompt[:1000],
                                                ratio="1280:720", duration=a.duration).wait_for_task_output()
            url = task.output[0]
            download(url, mp4)
            print(f"{k}: ok ({time.time() - t0:.0f}s, {os.path.getsize(mp4) // 1024} KB)", flush=True); ok.append(k)
        except TaskFailedError as e:
            failed.append((k, f"task failed: {getattr(e, 'task_details', e)}")); print(k, "FAILED", e, file=sys.stderr)
        except Exception as e:
            failed.append((k, repr(e)[:200])); print(k, "ERROR", repr(e)[:200], file=sys.stderr)
    print(json.dumps({"ok": ok, "failed": failed}, ensure_ascii=False))

if __name__ == "__main__":
    main()
