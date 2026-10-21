#!/usr/bin/env python3
"""Upload one pipeline output folder to YouTube (channel: 聞かせて、怪異放送。).

  python upload_youtube.py --dir out/mimei_kuchisake_20261021 [--privacy public|unlisted|private]
                           [--publish-at 2026-10-21T20:00:00+09:00] [--oauth /path/youtube_oauth.json] [--dry-run]

Credentials: --oauth, else $YT_OAUTH_JSON, else /home/claude/yt_oauth.json  (made by youtube_auth_setup.py;
lives in the Drive folder 未明新聞_自動生成動画 — the scheduled run downloads it there, never from git).
Defaults for privacy / scheduled publish / tags come from youtube.json next to this file.
Prints a JSON line: {"video_id", "url", "privacy", "publish_at"}  and appends it to out/<name>/youtube.json.
"""
import argparse, datetime, json, os, sys, time

ROOT = os.path.dirname(os.path.abspath(__file__))
JST = datetime.timezone(datetime.timedelta(hours=9))

def load_creds(path):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    d = json.load(open(path))
    creds = Credentials(None, refresh_token=d["refresh_token"], token_uri=d.get("token_uri", "https://oauth2.googleapis.com/token"),
                        client_id=d["client_id"], client_secret=d["client_secret"], scopes=d.get("scopes"))
    creds.refresh(Request())
    return creds

def build_meta(outdir, cfg, privacy, publish_at):
    script = json.load(open(os.path.join(outdir, "script.json"), encoding="utf-8"))
    name = os.path.basename(outdir.rstrip("/"))
    desc_path = os.path.join(outdir, f"{name}_description.txt")
    description = open(desc_path, encoding="utf-8").read() if os.path.exists(desc_path) else script.get("summary", "")
    title = cfg.get("title_format", "{title}").format(category=script.get("category", "未明新聞"),
                                                      title=script["title"], subtitle=script.get("subtitle", ""))
    mx = cfg.get("title_max", 100)
    if len(title) > mx:  # YouTube hard limit is 100 chars; fall back to 【category】title
        title = f"【{script.get('category', '未明新聞')}】{script['title']}"[:mx]
    status = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}
    if publish_at:
        status["privacyStatus"] = "private"   # YouTube requires private + publishAt for scheduled publishing
        status["publishAt"] = publish_at.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = {"snippet": {"title": title, "description": description[:5000], "tags": cfg.get("tags", []),
                        "categoryId": cfg.get("category_id", "24"), "defaultLanguage": cfg.get("default_language", "ja"),
                        "defaultAudioLanguage": cfg.get("default_language", "ja")},
            "status": status}
    return body, os.path.join(outdir, f"{name}.mp4"), os.path.join(outdir, f"{name}_thumb.jpg")

def default_publish_at(cfg):
    h = cfg.get("publish_hour_jst")
    if h is None: return None
    now = datetime.datetime.now(JST)
    t = now.replace(hour=int(h), minute=0, second=0, microsecond=0)
    if t <= now + datetime.timedelta(minutes=15): t += datetime.timedelta(days=1)   # too close → tomorrow
    return t

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--privacy", choices=["public", "unlisted", "private"])
    ap.add_argument("--publish-at", help="ISO-8601 with tz, e.g. 2026-10-21T20:00:00+09:00; 'none' disables the youtube.json default")
    ap.add_argument("--oauth", default=os.environ.get("YT_OAUTH_JSON", "/home/claude/yt_oauth.json"))
    ap.add_argument("--dry-run", action="store_true", help="print the request body, upload nothing")
    a = ap.parse_args()

    cfg = json.load(open(os.path.join(ROOT, "youtube.json"), encoding="utf-8"))
    privacy = a.privacy or cfg.get("privacy", "private")
    if a.publish_at == "none": publish_at = None
    elif a.publish_at: publish_at = datetime.datetime.fromisoformat(a.publish_at)
    else: publish_at = default_publish_at(cfg)
    if publish_at and privacy != "public":
        publish_at = None   # scheduled publishing only makes sense for a public release

    body, mp4, thumb = build_meta(a.dir, cfg, privacy, publish_at)
    if not os.path.exists(mp4): sys.exit(f"mp4 not found: {mp4}")
    print(json.dumps({"title": body["snippet"]["title"], "status": body["status"], "mp4": mp4}, ensure_ascii=False))
    if a.dry_run: return
    if not os.path.exists(a.oauth): sys.exit(f"oauth file not found: {a.oauth} (run youtube_auth_setup.py on your PC, put youtube_oauth.json in Drive)")

    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    from googleapiclient.errors import HttpError
    yt = build("youtube", "v3", credentials=load_creds(a.oauth), cache_discovery=False)
    media = MediaFileUpload(mp4, mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp, retries = None, 0
    while resp is None:
        try:
            st, resp = req.next_chunk()
            if st: print(f"upload {st.progress() * 100:.0f}%", flush=True)
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504) and retries < 5:
                retries += 1; time.sleep(2 ** retries); continue
            raise
    vid = resp["id"]
    try:
        if os.path.exists(thumb):
            yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(thumb, mimetype="image/jpeg")).execute()
    except HttpError as e:   # thumbnails need a verified phone on the channel; don't fail the upload over it
        print(f"thumbnail not set: {e}", file=sys.stderr)
    result = {"video_id": vid, "url": f"https://youtu.be/{vid}", "privacy": body["status"]["privacyStatus"],
              "publish_at": body["status"].get("publishAt"), "title": body["snippet"]["title"],
              "uploaded_at": datetime.datetime.now(JST).isoformat(timespec="seconds")}
    json.dump(result, open(os.path.join(a.dir, "youtube.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(result, ensure_ascii=False))

if __name__ == "__main__":
    main()
