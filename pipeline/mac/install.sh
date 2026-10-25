#!/usr/bin/env bash
# 未明新聞 場面クリップ bot を Mac に入れる（1回だけ実行）
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/vivihub/mimei-gogai/main/pipeline/mac/install.sh)"
# やること: ~/github/mimei-gogai を用意 → 5分おきに clipbot.sh を動かす launchd を登録。
# やめたいとき: launchctl unload ~/Library/LaunchAgents/jp.mimei.clipbot.plist
set -e
REPO="$HOME/github/mimei-gogai"
PLIST="$HOME/Library/LaunchAgents/jp.mimei.clipbot.plist"

mkdir -p "$HOME/github" "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
if [ -d "$REPO/.git" ]; then
  (cd "$REPO" && git fetch -q origin main && git checkout -q -B main origin/main)
else
  git clone -q https://github.com/vivihub/mimei-gogai "$REPO"
fi
chmod +x "$REPO/pipeline/mac/clipbot.sh"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>jp.mimei.clipbot</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$REPO/pipeline/mac/clipbot.sh</string></array>
  <key>StartInterval</key><integer>300</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/mimei-clipbot.out</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/mimei-clipbot.err</string>
</dict></plist>
EOF
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "----------------------------------------"
echo "設定完了: $REPO"
if command -v codex >/dev/null; then echo "codex: $(command -v codex)"; else echo "注意: codex が見つかりません（PATH: $PATH）"; fi
if command -v ffprobe >/dev/null; then echo "ffprobe: OK"; else echo "注意: ffmpeg が無いので mp4 の検品は省略されます（brew install ffmpeg で入ります）"; fi
echo "ログ: ~/github/mimei-clipbot.log"
