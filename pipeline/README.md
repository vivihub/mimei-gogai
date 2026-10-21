# 未明新聞 動画自動生成パイプライン

ミメイ／ハス／ヨミによる解説動画を、台本JSONから全自動でMP4化する。

## 使い方
```bash
bash pipeline/setup.sh                      # 初回のみ（VOICEVOX core 約1.2GBをDL）
python pipeline/pipeline.py --script pipeline/episodes/hachishaku.json
# → pipeline/out/<name>/ に MP4・サムネJPG・説明文TXT・script.json
```

## 台本フォーマット `episodes/*.json`
- `id, title, subtitle, thumb_text, category, summary, sources[]`
- `lines[]`: `{"c": "mimei|hasu|yomi", "bgm": "normal|ominous|ending", "t": "台詞（140字以内）"}`
- ミメイ（MC）7〜8割、ヨミ＝質問役、ハス＝不穏な一言。冒頭は挨拶なしでフックから。
- 行に `"chapter": "章タイトル"` を付けると、その行の前に2秒の章カードが入る（10分尺は5〜6章・60〜75行。手本: `episodes/hachishaku_long.json`）

## 構成
`tts.py`（VOICEVOX）→ `render.py`（静止フレーム・voice.wav）→ `mix_bgm.py`（bgm/ の normal/ominous/ending を場面切替・ダッキング）→ `render_anim.py`（口パク・まばたき・30fps）→ `pipeline.py`（サムネ・説明文）

## 声（VOICEVOX）
ミメイ=雀松朱司(52) / ハス=中部つるぎ ヒソヒソ(96) / ヨミ=小夜SAYO(46)。動画説明文にクレジット必須。

## YouTube 自動投稿（チャンネル「聞かせて、怪異放送。」）
```bash
python pipeline/upload_youtube.py --dir pipeline/out/<name>            # youtube.json の既定（public・当日20時JST予約公開）
python pipeline/upload_youtube.py --dir pipeline/out/<name> --privacy unlisted --publish-at none
```
- 設定は `youtube.json`（privacy / publish_hour_jst / tags / title_format）。マストヘッドとエンドカードのチャンネル名は `render.py` の `CHANNEL`。
- 認証は `youtube_oauth.json`（refresh token）。**初回のみ手元のPCで** `python youtube_auth_setup.py client_secret.json` を実行して作り、Google Drive の「未明新聞_自動生成動画」フォルダに置く。定期実行はそこから `/home/claude/yt_oauth.json` に取り出して使う。git には入れない（.gitignore 済み）。
- 結果は `out/<name>/youtube.json`（video_id, url, publish_at）。

## ネタ管理
`topics.json` の `queue` から順に消化し、作ったら `done` へ移す。
