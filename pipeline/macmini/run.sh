#!/usr/bin/env bash
# 未明新聞 自動制作 — Mac mini 用ランナー（launchd が毎日 08:52 JST に起動。手動: bash pipeline/macmini/run.sh）
# やること: リポジトリを main の先頭に揃える → セットアップ確認 → Claude Code を headless で起動し PROMPT.md を実行
#           （ネタ選定〜台本〜場面絵〜動画〜YouTube 投稿〜git push〜報告まで Claude 側が行う）
# ログ: ~/mimei/logs/autopilot-<日時>.log ／ 報告: ~/mimei/reports/ ／ 動画: ~/github/mimei-gogai/pipeline/out/
set -u
REPO="${MIMEI_REPO:-$HOME/github/mimei-gogai}"
MH="${MIMEI_HOME:-$HOME/mimei}"
export MIMEI_VV="${MIMEI_VV:-$MH/vv}"
export YT_OAUTH_JSON="${YT_OAUTH_JSON:-$MH/secrets/youtube_oauth.json}"
export RUNWAY_KEY_FILE="${RUNWAY_KEY_FILE:-$MH/secrets/runway_api_key.txt}"
export MIMEI_REPORT_DIR="$MH/reports"
LOCK="$MH/.autopilot.lock"
STAMP="$(date '+%Y%m%d-%H%M')"
LOG="$MH/logs/autopilot-$STAMP.log"
mkdir -p "$MH/logs" "$MH/reports" "$MH/secrets" "$MH/out"
# 秘密情報は env ファイルでも渡せる（RUNWAYML_API_SECRET / SLACK_WEBHOOK_URL / ANTHROPIC_API_KEY / MIMEI_MODEL など）
[ -f "$MH/secrets/env" ] && set -a && . "$MH/secrets/env" && set +a

# PATH: Homebrew, venv(python3=venv の python), claude / codex (npm global, nvm)
eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv 2>/dev/null)" || true
NODEBIN="$(ls -d "$HOME/.nvm/versions/node"/*/bin 2>/dev/null | tail -1)"
export PATH="$MIMEI_VV/vvenv/bin:$HOME/.local/bin:$HOME/.claude/local/bin:${NODEBIN:+$NODEBIN:}/opt/homebrew/bin:/usr/local/bin:$PATH"
export LANG=ja_JP.UTF-8 LC_ALL=ja_JP.UTF-8

log() { printf '%s %s\n' "$(date '+%F %T')" "$*" | tee -a "$LOG"; }
notify() { osascript -e "display notification \"$2\" with title \"未明新聞 autopilot\" subtitle \"$1\"" 2>/dev/null || true; }

# 多重起動防止（ロックが3時間より古い＝前回クラッシュなら無視）
if [ -d "$LOCK" ]; then
  if [ -n "$(find "$LOCK" -mmin +180 2>/dev/null)" ]; then rm -rf "$LOCK"; else log "another run holds the lock; skip"; exit 0; fi
fi
mkdir "$LOCK" || exit 0
trap 'rm -rf "$LOCK"' EXIT

log "run start (pid $$) repo=$REPO vv=$MIMEI_VV"
[ -d "$REPO/.git" ] || { log "repo not found: $REPO (run install.sh first)"; notify "失敗" "リポジトリが無い"; exit 1; }
command -v claude >/dev/null || { log "claude CLI not found in PATH=$PATH"; notify "失敗" "claude CLI が無い"; exit 1; }
cd "$REPO" || exit 1

# main の先頭に揃える（未コミットの変更があれば退避しておく）
git fetch -q origin main 2>>"$LOG" || log "WARN: fetch failed (offline?) — continue with local main"
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then git stash push -q -m "autopilot-$STAMP" 2>>"$LOG" && log "stashed local changes"; fi
git checkout -q -B main origin/main 2>>"$LOG" || git checkout -q main

# 環境（冪等。2回目以降は数秒）
bash pipeline/macmini/setup_mac.sh >>"$LOG" 2>&1 || { log "setup_mac.sh failed (see log)"; notify "失敗" "setup_mac.sh が失敗"; exit 1; }

# Claude Code を headless で実行。PROMPT.md が手順書。スリープ抑止は caffeinate で（最大4時間）。
PROMPT="$(cat pipeline/macmini/PROMPT.md)"
OPTS=(--dangerously-skip-permissions --max-turns "${MIMEI_MAX_TURNS:-600}" --output-format text --no-session-persistence)
[ -n "${MIMEI_MODEL:-}" ] && OPTS+=(--model "$MIMEI_MODEL")
claude --help 2>/dev/null | grep -q -- '--permission-prompts' && OPTS+=(--permission-prompts none)   # v2.1.259+
log "claude start (model=${MIMEI_MODEL:-default}, $(claude --version 2>/dev/null | head -1))"
caffeinate -dims -t 14400 claude -p "$PROMPT" "${OPTS[@]}" >>"$LOG" 2>&1
RC=$?
log "claude exit $RC"
# 報告ファイルの末尾を通知に
R="$(ls -t "$MH/reports"/*.md 2>/dev/null | head -1)"
if [ -n "$R" ] && [ -n "$(find "$R" -mmin -300)" ]; then
  notify "完了" "$(head -c 180 "$R" | tr '\n' ' ')"
else
  notify "終了 (rc=$RC)" "報告ファイルが見当たりません。ログ: $LOG"
fi
exit $RC
