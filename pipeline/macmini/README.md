# Mac mini で全自動制作を回す（定期タスクの実行元をクラウドから Mac mini へ）

クラウドの定期タスク（Cowork）で起きていた問題 — GitHub に push できず topics.json の記録が落ちる／場面クリップを Mac の bot に頼む回り道／1回の Bash が10分で切れる — を、Mac mini 上の Claude Code（headless）で同じ手順書を回すことで解消する。

## 構成
- `install.sh` … 1回だけ。リポジトリ clone → `setup_mac.sh` → claude CLI → Canva MCP 登録 → launchd 登録（毎日 08:52）
- `setup_mac.sh` … 冪等。Homebrew（ffmpeg / python@3.12 / Noto CJK JP フォント）、venv `~/mimei/vv/vvenv`、VOICEVOX core 0.15.7（osx-arm64）、pyopenjtalk
- `run.sh` … launchd から起動。main の先頭に揃える → setup 確認 → `caffeinate` 付きで `claude -p "$(cat PROMPT.md)" --dangerously-skip-permissions …` → 報告を macOS 通知
- `PROMPT.md` … 手順書（クラウド版の定期タスクの prompt を Mac mini 向けに書き換えたもの）

## 置き場（`~/mimei/`）
```
~/mimei/vv/                 VOICEVOX core・venv・辞書パス（MIMEI_VV）
~/mimei/secrets/youtube_oauth.json   YouTube 投稿用（Drive の youtube_oauth.json をコピー）
~/mimei/secrets/runway_api_key.txt   任意。Runway API を直接使う場合のみ（API クレジットが別途消費される）
~/mimei/secrets/env                  任意。SLACK_WEBHOOK_URL / MIMEI_MODEL / RUNWAYML_API_SECRET など（run.sh が読む）
~/mimei/logs/                        autopilot-<日時>.log, pipeline-<id>.log
~/mimei/reports/<日付>_<id>.md       報告（1行目が通知に出る）
~/mimei/out/<日付>_<id>/             本編・ショート・サムネ・説明文
```

## 1回だけの手作業（install.sh の最後にも出る）
1. `claude` を起動してログイン（Max プラン推奨。API キー運用なら `~/mimei/secrets/env` に `ANTHROPIC_API_KEY=`）
2. `claude` → `/mcp` → canva → Authenticate（ブラウザで Canva にログイン）
3. GitHub の push 権限（`gh auth login` か osxkeychain で一度 push）
4. `youtube_oauth.json` を `~/mimei/secrets/` に置く
5. 場面クリップ: Runway API キーを置くか、codex を入れて Runway 連携を有効にする（clipbot と同じ。年額プランのクレジットを使う）
6. スリープしない設定（システム設定 > エネルギー）
7. 試運転 `bash pipeline/macmini/run.sh` → `~/mimei/reports/` と `~/mimei/out/` を確認
8. 軌道に乗ったら Cowork の定期タスクを停止（二重制作を防ぐ）。MacBook Air の clipbot も不要になる（`launchctl unload ~/Library/LaunchAgents/jp.mimei.clipbot.plist`）

## コード側の変更（クラウドでもそのまま動く）
- `pipeline.py` / `tts.py`: VOICEVOX の場所を `MIMEI_VV`（既定 `/home/claude/vv`）で指定。core ディレクトリは `voicevox_core-*-0.15.7` を自動検出。`DYLD_LIBRARY_PATH` も渡す
- `render.py`: フォントを環境変数（`MIMEI_FONT_SERIF` / `MIMEI_FONT_SANS`）→ Linux の .ttc → macOS の `~/Library/Fonts/NotoSerifCJKjp-Bold.otf` / `NotoSansCJKjp-Regular.otf` の順で探す。`.ttc` の face index を 2（簡体字）から 0（日本語）に修正
- `gen_scene_video.py`: キーファイルを `RUNWAY_KEY_FILE` で指定可
- `upload_youtube.py`: 従来どおり `YT_OAUTH_JSON`

## 起動時刻の変更
`MIMEI_HOUR=20 MIMEI_MIN=30 bash pipeline/macmini/install.sh`（plist を書き直して再登録）
