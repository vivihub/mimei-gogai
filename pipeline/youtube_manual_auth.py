#!/usr/bin/env python3
"""YouTube OAuth by copy-paste (no browser here, no local listener needed).

Lets the channel owner pick a *brand account* channel (the device flow often skips the chooser and
grabs the account's default channel).

  python youtube_manual_auth.py url --client client_secret.json
      → open the printed URL, choose the channel (「聞かせて、怪異放送。」), allow.
        The browser then tries to open http://localhost:8765/?code=...  and fails — that's expected.
        Copy that whole address from the address bar.
  python youtube_manual_auth.py exchange --client client_secret.json --code "<pasted address or code>"
      → writes youtube_oauth.json

Scope: youtube.upload (videos.insert + thumbnails.set).  Needs an OAuth client of type 「デスクトップ アプリ」.
"""
import argparse, json, sys, urllib.parse, urllib.request, urllib.error

SCOPE = "https://www.googleapis.com/auth/youtube.upload"
REDIRECT = "http://localhost:8765/"
AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN = "https://oauth2.googleapis.com/token"

def client(path):
    c = json.load(open(path)); c = c.get("installed") or c.get("web") or c
    return c["client_id"], c["client_secret"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["url", "exchange"])
    ap.add_argument("--client", required=True)
    ap.add_argument("--code", help="exchange: the redirected localhost URL, or just the code value")
    ap.add_argument("--out", default="youtube_oauth.json")
    a = ap.parse_args()
    cid, csec = client(a.client)
    if a.cmd == "url":
        q = {"client_id": cid, "redirect_uri": REDIRECT, "response_type": "code", "scope": SCOPE,
             "access_type": "offline", "prompt": "consent select_account", "include_granted_scopes": "true"}
        print(AUTH + "?" + urllib.parse.urlencode(q)); return
    code = a.code.strip()
    if "code=" in code:
        code = urllib.parse.parse_qs(urllib.parse.urlparse(code).query)["code"][0]
    data = urllib.parse.urlencode({"code": code, "client_id": cid, "client_secret": csec,
                                   "redirect_uri": REDIRECT, "grant_type": "authorization_code"}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(TOKEN, data), timeout=30) as r:
            tok = json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"token exchange failed: {e.read().decode()}")
    if "refresh_token" not in tok: sys.exit(f"no refresh_token in response: {list(tok)}")
    json.dump({"client_id": cid, "client_secret": csec, "refresh_token": tok["refresh_token"],
               "token_uri": TOKEN, "scopes": [SCOPE]}, open(a.out, "w"), indent=1)
    print(f"wrote {a.out}")

if __name__ == "__main__":
    main()
