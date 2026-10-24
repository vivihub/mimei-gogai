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

## 場面絵と動き（2026-10-24〜）
10分間ほぼ静止だった画面に、台本に合った「場面絵」とテロップを入れる。
- `episodes/scenes/<id>/<key>.jpg`（1920x1080）を置き、台本の行に `"scene": "<key>"` を付けると、その行以降の背景がその絵になる（ゆっくり7%ズーム＋横ドリフト、話者は右下に小さく表示）。`"scene": ""` で舞台（三人）に戻る。章の最初の行に付けると章カードもその絵になる。画像が無いキーは警告を出して舞台にフォールバック。
- 行に `"telop": "23時14分"`（10字以内）を付けると、黄色の大テロップがポップインする（場面絵モードは左上110px、舞台モードは右下72px）。日付・数字・固有名詞に、6〜16行に付ける。連続する行には付けない。
- 台本の `scenes` に key→プロンプト（英語）を記録する。手本: `episodes/kisaragi.json`（hook, ch1〜ch5。まとめ章と結論再掲は舞台）。
- サムネは最初の場面絵を暗くして背景に敷く。ショートも場面絵を中央に使う。
- 生成手順（定期タスクが Canva コネクタで実行）:
  1. 各 scene: `generate-image`（prompt = 下のスタイル接頭辞 + 場面の説明, aspectRatio LANDSCAPE_16_9）→ `get-generate-image-job` で SUCCESS まで待ち、media id を控える
  2. 場面絵ボード design `DAHY617vOcg` を `read-design`（open_transaction）→ `edit-design` で scene 数ぶん `add_page`(1920x1080, keep_open) → `read-design`（transaction_id, 末尾ページ）で page id → `edit-design` で各ページに `insert_fill`(top0 left0 1920x1080) → `finalize: commit`
  3. `export-design`（jpg, pages=[追加したページ番号], width 1920, height 1080）→ URL を `python3 save_scenes.py <id> hook=URL ch1=URL ...` で保存
  - スタイル接頭辞: "Dark moody illustration in an anime-adjacent ink-and-wash style, deep purple-black night palette with faint cream and amber highlights, cinematic 16:9, atmospheric. No text, no letters, no readable signs, no faces (silhouettes at most), no gore."
  - 実在の人物・被害者を描かない。場所・物・空気を描く。

## 場面クリップ（Runway image-to-video、2026-10-24〜）
場面絵をそのまま 10 秒の動画にして、静止画ズームの代わりに背景で動かす（霧・光のゆらぎ・ゆっくりしたカメラ寄り）。
- `python3 gen_scene_video.py <id>` が `episodes/scenes/<id>/<key>.jpg` → `<key>.mp4`（gen4_turbo・1280x720・10秒）を作る。既にある mp4 はスキップ（`--force` で作り直し）。
- API キー: 環境変数 `RUNWAYML_API_SECRET`、無ければ `/home/claude/runway_api_key.txt`（Drive「未明新聞_自動生成動画」の `runway_api_key.txt` から取り出す）。キーが無い／失敗した場面は静止画ズームに自動フォールバック。
- 描画: `render.clip_frame()` が半速（10秒→20秒）・ピンポン再生でループの継ぎ目を消す。ショートも同じクリップを使う（`render_short.py` は毎フレーム描画に変更）。
- コスト: 5 クレジット/秒（1 クレジット = $0.01）→ 10 秒 1 本 $0.50、6 場面で約 $3/エピソード。
- mp4 は git に入れない（`.gitignore`）。定期タスクは毎回生成する。

## 構成
`tts.py`（VOICEVOX）→ `render_short.py`（冒頭〜「先に結論。」でショート版）／ `render.py`（静止フレーム・voice.wav・場面絵/テロップ）→ `mix_bgm.py`（bgm/ の normal/ominous/ending を場面切替・ダッキング）→ `render_anim.py`（口パク・まばたき・場面絵ズーム・テロップ・30fps）→ `pipeline.py`（サムネ・説明文）／ `save_scenes.py`（場面絵の保存）

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
