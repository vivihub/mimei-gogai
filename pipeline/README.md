# 未明新聞 動画自動生成パイプライン

ミメイ／ハス／ヨミによる解説動画を、台本JSONから全自動でMP4化する。

## 使い方
```bash
bash pipeline/setup.sh                      # 初回のみ（VOICEVOX core 約1.2GBをDL）
python pipeline/pipeline.py --script pipeline/episodes/hachishaku.json
# → pipeline/out/<name>/ に MP4・ショート版 <name>_short.mp4（縦1080x1920・60秒以内）・サムネJPG・説明文TXT・script.json
```

## 台本フォーマット `episodes/*.json`
- `id, title, subtitle, thumb_text, category, summary, sources[]`
- `lines[]`: `{"c": "mimei|hasu|yomi", "bgm": "normal|ominous|ending", "t": "台詞（140字以内）"}`
- ミメイ（MC）7〜8割、ヨミ＝質問役、ハス＝不穏な一言。冒頭は挨拶なしでフックから。
- 行に `"chapter": "章タイトル"` を付けると、その行の前に2秒の章カードが入る（10分尺は5〜6章・60〜75行。手本: `episodes/hachishaku_long.json`）

## 冒頭・サムネの設計ルール（2026-10-24 アナリティクス反映）
過去28日の実績: 本編 CTR 1.46%・平均視聴 33秒（11分尺）、ショートの視聴継続 14.5%。離脱点は「先に結論」の手前（38秒目）だった。
- **冒頭20秒で結論まで**: フック2行（合計70字以内≒12秒、1行目は20字以内の短文）→ ハス一言（任意）→「先に結論。」。自己紹介「未明新聞のミメイです…」は結論の**後**に1行40字以内。タイトルカードは1.5秒。
- **thumb_text は「問い」**: 16字以内の疑問形か違和感の一文（例「なぜ23時14分に／書けたのか？」）。サムネでは題名より大きく黄色（`THUMB_HOOK`）で主役になり、ショートでは冒頭1.6秒に画面中央の大テロップとして重なる（`render_short.PUNCH_DUR`）。「／」で改行位置を指定（1行8字以内。YouTubeタイトルや見出しでは「／」は自動で除去）。
- **subtitle は30字以内**: YouTubeタイトルは `【カテゴリ】題名｜subtitle` になるので、結論を短く言い切る。

## 構成
`tts.py`（VOICEVOX）→ `render_short.py`（冒頭〜「先に結論。」でショート版）／ `render.py`（静止フレーム・voice.wav）→ `mix_bgm.py`（bgm/ の normal/ominous/ending を場面切替・ダッキング）→ `render_anim.py`（口パク・まばたき・30fps）→ `pipeline.py`（サムネ・説明文）

## 声（VOICEVOX）
ミメイ=雀松朱司(52) / ハス=中部つるぎ ヒソヒソ(96) / ヨミ=小夜SAYO(46)。動画説明文にクレジット必須。

## YouTube 自動投稿（チャンネル「聞かせて、怪異放送。」）
```bash
python pipeline/upload_youtube.py --dir pipeline/out/<name>            # youtube.json の既定（public・当日20時JST予約公開）
python pipeline/upload_youtube.py --dir pipeline/out/<name> --privacy unlisted --publish-at none
python pipeline/upload_youtube.py --dir pipeline/out/<name> --short        # ショート版（本編URLを説明文に自動挿入）
python pipeline/upload_youtube.py --dir pipeline/out/<name> --thumb-only   # サムネだけ再設定
```
- 設定は `youtube.json`（privacy / publish_hour_jst / tags / title_format）。マストヘッドとエンドカードのチャンネル名は `render.py` の `CHANNEL`。
- 認証は `youtube_oauth.json`（refresh token）。初回のみ作る。ブラウザ無し環境なら `python youtube_device_auth.py --client client_secret.json`（OAuth クライアント種別「テレビと制限付き入力デバイス」。URL とコードが出るのでスマホで承認）、手元のPCなら `python youtube_auth_setup.py client_secret.json`（種別「デスクトップ アプリ」）。できたファイルをGoogle Drive の「未明新聞_自動生成動画」フォルダに置く。定期実行はそこから `/home/claude/yt_oauth.json` に取り出して使う。git には入れない（.gitignore 済み）。
- 結果は `out/<name>/youtube.json`（video_id, url, publish_at）。

## ネタ管理
`topics.json` の `queue` から順に消化し、作ったら `done` へ移す。
