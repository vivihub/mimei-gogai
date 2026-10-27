#!/usr/bin/env bash
# 未明新聞 自動制作を Mac mini に入れる（1回だけ実行。冪等）
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/vivihub/mimei-gogai/main/pipeline/macmini/install.sh)"
# やること: ~/github/mimei-gogai を用意 → setup_mac.sh（VOICEVOX 等）→ claude CLI 確認 → Canva MCP 登録 →
#           launchd（毎日 08:52 JST に run.sh）を登録。最後に、人手で1回だけ必要な作業を表示する。
# やめたいとき: launchctl unload ~/Library/LaunchAgents/jp.mimei.autopilot.plist
set -e
REPO="$HOME/github/mimei-gogai"
MH="$HOME/mimei"
PLIST="$HOME/Library/LaunchAgents/jp.mimei.autopilot.plist"
HOUR="${MIMEI_HOUR:-8}"; MIN="${MIMEI_MIN:-52}"     # 起動時刻（Mac のローカル時刻 = JST 想定）

mkdir -p "$HOME/github" "$HOME/Library/LaunchAgents" "$MH/secrets" "$MH/logs" "$MH/reports" "$MH/out"
if [ -d "$REPO/.git" ]; then
  (cd "$REPO" && git fetch -q origin main && git checkout -q -B main origin/main)
else
  git clone -q https://github.com/vivihub/mimei-gogai "$REPO"
fi
chmod +x "$REPO"/pipeline/macmini/*.sh

# 1) Homebrew / VOICEVOX / フォント / venv
bash "$REPO/pipeline/macmini/setup_mac.sh"

# 2) Claude Code CLI
eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null)" || true
export PATH="$HOME/.local/bin:$HOME/.claude/local/bin:$PATH"
if ! command -v claude >/dev/null; then
  echo "claude CLI が無いのでインストールします（native installer）"
  curl -fsSL https://claude.ai/install.sh | bash
  export PATH="$HOME/.local/bin:$PATH"
fi
command -v claude >/dev/null || { echo "claude CLI のインストールに失敗。https://code.claude.com/docs/en/setup を参照"; exit 1; }

# 3) Canva MCP（場面絵の生成に使う。初回はブラウザで Canva にログインが必要）
if ! claude mcp list 2>/dev/null | grep -q '^canva'; then
  claude mcp add --scope user --transport http canva https://mcp.canva.com/mcp || true
fi

# 4) launchd（毎日 HOUR:MIN に run.sh）
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>jp.mimei.autopilot</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$REPO/pipeline/macmini/run.sh</string></array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>$HOUR</integer><key>Minute</key><integer>$MIN</integer></dict>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>$MH/logs/launchd.out</string>
  <key>StandardErrorPath</key><string>$MH/logs/launchd.err</string>
  <key>EnvironmentVariables</key><dict><key>HOME</key><string>$HOME</string><key>LANG</key><string>ja_JP.UTF-8</string></dict>
</dict></plist>
EOF
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "=========================================================="
echo "設定完了。毎日 ${HOUR}:${MIN} に $REPO/pipeline/macmini/run.sh が動きます。"
echo "残りは人手で1回だけ（済んだものは飛ばしてOK）:"
echo "  [1] Claude Code にログイン:        claude   （ブラウザで認証して終了。Max プラン推奨）"
echo "  [2] Canva MCP の認証:               claude  → /mcp → canva → Authenticate（ブラウザでログイン）"
echo "  [3] GitHub への push 権限:          gh auth login  または  git config --global credential.helper osxkeychain で一度 push"
echo "  [4] YouTube の OAuth:               Drive『未明新聞_自動生成動画』の youtube_oauth.json を $MH/secrets/youtube_oauth.json に置く"
echo "  [5] 場面クリップ（任意）:           Runway API を使うなら $MH/secrets/runway_api_key.txt、"
echo "                                      年額プランのクレジットで作るなら codex を入れて Runway 連携を有効に（clipbot と同じ）"
echo "  [6] スリープさせない:               システム設定 > エネルギー で『ディスプレイがオフでもスリープしない』"
echo "  [7] 試運転:                         bash $REPO/pipeline/macmini/run.sh   （ログ: $MH/logs/）"
echo "  [8] 軌道に乗ったら、Cowork 側の定期タスクを停止（二重制作を防ぐ）"
echo "=========================================================="
