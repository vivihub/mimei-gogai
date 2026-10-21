#!/usr/bin/env python3
"""One-time OAuth setup for YouTube uploads — run this ON YOUR OWN PC (it opens a browser).

  1. Google Cloud Console → プロジェクト作成 → 「YouTube Data API v3」を有効化
  2. 認証情報 → OAuth クライアント ID → 種類「デスクトップ アプリ」→ JSON をダウンロード
     （OAuth 同意画面が「テスト」の場合は、テストユーザーにチャンネルの Google アカウントを追加）
  3. pip install google-auth-oauthlib
  4. python youtube_auth_setup.py client_secret_XXXX.json
     → ブラウザで「聞かせて、怪異放送。」を持つアカウントを選んで許可
     → youtube_oauth.json ができる
  5. youtube_oauth.json を Google Drive の「未明新聞_自動生成動画」フォルダに置く（git には絶対に入れない）

The refresh token in youtube_oauth.json lets the pipeline upload without a browser.
If the OAuth consent screen stays in "Testing", Google expires refresh tokens after 7 days —
publish the consent screen (審査不要: youtube.upload だけなら「公開」にして「確認を省略」で可) to keep it alive.
"""
import json, sys
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python youtube_auth_setup.py client_secret.json")
    flow = InstalledAppFlow.from_client_secrets_file(sys.argv[1], SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    if not creds.refresh_token:
        sys.exit("no refresh token returned — revoke the app at https://myaccount.google.com/permissions and run again")
    out = {"client_id": creds.client_id, "client_secret": creds.client_secret,
           "refresh_token": creds.refresh_token, "token_uri": creds.token_uri, "scopes": SCOPES}
    json.dump(out, open("youtube_oauth.json", "w"), indent=1)
    print("wrote youtube_oauth.json — upload it to the Drive folder 未明新聞_自動生成動画 (never commit it)")

if __name__ == "__main__":
    main()
