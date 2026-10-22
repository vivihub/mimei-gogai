#!/usr/bin/env python3
"""YouTube OAuth without a local browser (Google "TV / limited-input device" flow).

Use this when the pipeline runs somewhere headless (the Claude cloud session): it prints a URL and a code,
the channel owner opens the URL on any phone/PC, enters the code and approves, and the refresh token lands
in youtube_oauth.json here. Needs an OAuth client of type 「テレビと制限付き入力デバイス」 (TVs and Limited Input
devices) from Google Cloud Console → 認証情報 (the "Desktop app" type does NOT work with this flow).

  python youtube_device_auth.py --client client_secret.json          # JSON downloaded from Cloud Console
  python youtube_device_auth.py --client-id ... --client-secret ...
  → prints  "https://www.google.com/device  code: ABCD-EFGH"  and waits (up to ~30 min)
  → writes youtube_oauth.json (keep it out of git; put it in the Drive folder 未明新聞_自動生成動画)

Scope: https://www.googleapis.com/auth/youtube (the device flow does not allow youtube.upload alone;
`youtube` covers videos.insert + thumbnails.set).
"""
import argparse, json, sys, time, urllib.parse, urllib.request, urllib.error

SCOPE = "https://www.googleapis.com/auth/youtube"
DEVICE = "https://oauth2.googleapis.com/device/code"
TOKEN = "https://oauth2.googleapis.com/token"

def post(url, data):
    req = urllib.request.Request(url, urllib.parse.urlencode(data).encode(), {"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read())
        except Exception: return e.code, {"error": str(e)}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--client", help="client_secret JSON from Cloud Console (installed/device type)")
    ap.add_argument("--client-id"); ap.add_argument("--client-secret")
    ap.add_argument("--out", default="youtube_oauth.json")
    ap.add_argument("--code-only", action="store_true", help="request the code, print it, save state to .device.json and exit")
    ap.add_argument("--resume", action="store_true", help="continue polling with the state saved by --code-only")
    a = ap.parse_args()
    if a.client:
        c = json.load(open(a.client)); c = c.get("installed") or c.get("web") or c
        cid, csec = c["client_id"], c["client_secret"]
    elif a.client_id and a.client_secret:
        cid, csec = a.client_id, a.client_secret
    elif a.resume:
        st = json.load(open(".device.json")); cid, csec = st["client_id"], st["client_secret"]
    else:
        sys.exit("give --client FILE or --client-id/--client-secret")

    if a.resume:
        st = json.load(open(".device.json")); dev = st["device"]
    else:
        code, dev = post(DEVICE, {"client_id": cid, "scope": SCOPE})
        if code != 200: sys.exit(f"device code request failed: {dev}")
        print(f"\n  開く: {dev['verification_url']}\n  コード: {dev['user_code']}\n  （有効期限 {dev['expires_in'] // 60} 分）\n", flush=True)
        if a.code_only:
            json.dump({"client_id": cid, "client_secret": csec, "device": dev, "t0": time.time()}, open(".device.json", "w"))
            return
    interval = dev.get("interval", 5); deadline = time.time() + dev.get("expires_in", 1800)
    while time.time() < deadline:
        time.sleep(interval)
        code, tok = post(TOKEN, {"client_id": cid, "client_secret": csec, "device_code": dev["device_code"],
                                 "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
        err = tok.get("error")
        if code == 200 and "refresh_token" in tok:
            json.dump({"client_id": cid, "client_secret": csec, "refresh_token": tok["refresh_token"],
                       "token_uri": TOKEN, "scopes": [SCOPE]}, open(a.out, "w"), indent=1)
            print(f"wrote {a.out}"); return
        if err == "authorization_pending": continue
        if err == "slow_down": interval += 5; continue
        sys.exit(f"auth failed: {tok}")
    sys.exit("code expired — run again")

if __name__ == "__main__":
    main()
