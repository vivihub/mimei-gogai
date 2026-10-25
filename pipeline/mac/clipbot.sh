#!/usr/bin/env bash
# 未明新聞 場面クリップ bot（Mac 常駐。launchd が5分おきに起動）
#
# 役割: GitHub の main に「pipeline/episodes/scenes/<id>/WANT_CLIPS」が置かれたら、
#       その場面絵 6 枚を Mac 上の Codex（Runway 連携）で 10 秒の mp4 にし、
#       ブランチ `clips` の clips/<id>/ に push する（完了印 DONE 付き）。
#       クラウド側の定期タスクは origin/clips を見て mp4 を取り込む。
# ログ: ~/github/mimei-clipbot.log
set -u
REPO="$HOME/github/mimei-gogai"
CLIPS_WT="$HOME/github/mimei-gogai-clips"   # clips ブランチ用 worktree
LOCK="$HOME/.mimei-clipbot.lock"
LOG="$HOME/github/mimei-clipbot.log"
CODEX_TIMEOUT=2400   # 秒（40分）
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$HOME/.nvm/versions/node/$(ls "$HOME/.nvm/versions/node" 2>/dev/null | tail -1)/bin:$PATH"

log() { printf '%s %s\n' "$(date '+%F %T')" "$*" >> "$LOG"; }
mkdir -p "$(dirname "$LOG")"

# 多重起動防止（ロックが古すぎる＝前回クラッシュなら無視）
if [ -d "$LOCK" ]; then
  if [ -n "$(find "$LOCK" -mmin +90 2>/dev/null)" ]; then rm -rf "$LOCK"; else exit 0; fi
fi
mkdir "$LOCK" || exit 0
trap 'rm -rf "$LOCK"' EXIT

[ -d "$REPO/.git" ] || { log "repo not found: $REPO"; exit 0; }
command -v codex >/dev/null || { log "codex not found in PATH"; exit 0; }

cd "$REPO" || exit 0
git fetch -q origin main 2>>"$LOG" || { log "fetch main failed"; exit 0; }
git checkout -q -B main origin/main 2>>"$LOG"

# clips ブランチの worktree を用意（無ければ orphan で作る）
if [ ! -d "$CLIPS_WT/.git" ] && [ ! -f "$CLIPS_WT/.git" ]; then
  if git ls-remote --exit-code --heads origin clips >/dev/null 2>&1; then
    git fetch -q origin clips && git worktree add -q "$CLIPS_WT" -B clips origin/clips 2>>"$LOG"
  else
    git worktree add -q --detach "$CLIPS_WT" 2>>"$LOG"
    (cd "$CLIPS_WT" && git checkout -q --orphan clips && git rm -rfq . >/dev/null 2>&1; mkdir -p clips && echo "scene clips (mp4) made on Mac by clipbot" > clips/README.md && git add clips && git commit -qm "init clips branch" && git push -q -u origin clips) 2>>"$LOG"
  fi
fi
cd "$CLIPS_WT" 2>/dev/null || { log "clips worktree missing"; exit 0; }
git fetch -q origin clips 2>>"$LOG" && git reset -q --hard origin/clips 2>>"$LOG"

for d in "$REPO"/pipeline/episodes/scenes/*/; do
  id="$(basename "$d")"
  [ -f "$d/WANT_CLIPS" ] || continue
  [ -f "$CLIPS_WT/clips/$id/DONE" ] && continue
  njpg=$(ls "$d"/*.jpg 2>/dev/null | wc -l | tr -d ' ')
  [ "$njpg" -ge 1 ] || { log "$id: no jpg yet"; continue; }
  log "$id: start ($njpg jpg)"

  PROMPT="pipeline/episodes/scenes/$id/ にある hook.jpg, ch1.jpg, ch2.jpg, ch3.jpg, ch4.jpg, ch5.jpg（1920x1080）を Runway の image-to-video（gen4_turbo）で各10秒・1280x720（ratio 1280:720）の mp4 にして、同じフォルダに同名（hook.mp4, ch1.mp4, …, ch5.mp4）で保存してください。プロンプトは pipeline/episodes/$id.json の \"scenes\"[key] の英文に、pipeline/gen_scene_video.py の MOTION 定数の文（Subtle, slow, continuous motion only … no fast movement.）を末尾に足したもの。Runway の API キーが環境変数 RUNWAYML_API_SECRET にあるなら pipeline ディレクトリで python3 gen_scene_video.py $id を実行するだけでよい（runwayml パッケージが無ければ pip3 install runwayml pillow）。無い場合は連携済みの Runway ツールで1枚ずつ生成してダウンロードする。6本できたら ls -la pipeline/episodes/scenes/$id/*.mp4 を出力して終了。git へのコミットや push はしない。"

  # codex 0.128+ では --full-auto が廃止。書き込みは作業フォルダ内のみ、承認なし、ネット許可（Runway 呼び出しと mp4 DL に必要）
  ( cd "$REPO" && codex exec --sandbox workspace-write -c 'sandbox_workspace_write.network_access=true' -c 'approval_policy="never"' "$PROMPT" ) >> "$LOG" 2>&1 &
  cpid=$!
  waited=0; crc=0
  while kill -0 "$cpid" 2>/dev/null; do
    sleep 20; waited=$((waited+20))
    if [ "$waited" -ge "$CODEX_TIMEOUT" ]; then log "$id: codex timeout, using what exists"; kill "$cpid" 2>/dev/null; break; fi
  done
  wait "$cpid" 2>/dev/null; crc=$?
  log "$id: codex exited with $crc after ${waited}s"
  if [ "$crc" -ne 0 ] && [ "$waited" -lt 120 ]; then
    n=$(( $(cat "$CLIPS_WT/clips/$id/ATTEMPTS" 2>/dev/null || echo 0) + 1 )); mkdir -p "$CLIPS_WT/clips/$id"; echo "$n" > "$CLIPS_WT/clips/$id/ATTEMPTS"
    if [ "$n" -lt 3 ]; then log "$id: codex failed quickly (attempt $n/3). Will retry next run"; continue; fi
    log "$id: codex failed 3 times, giving up (DONE with no clips)"
  fi

  # 検品してから clips ブランチへ
  mkdir -p "$CLIPS_WT/clips/$id"
  ok=""
  for k in hook ch1 ch2 ch3 ch4 ch5; do
    f="$d/$k.mp4"
    [ -s "$f" ] || continue
    if command -v ffprobe >/dev/null; then
      dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f" 2>/dev/null | cut -d. -f1)
      [ -n "$dur" ] && [ "$dur" -ge 4 ] || { log "$id: $k.mp4 broken, skipped"; continue; }
    fi
    cp -f "$f" "$CLIPS_WT/clips/$id/$k.mp4" && ok="$ok $k"
  done
  echo "${ok# }" > "$CLIPS_WT/clips/$id/DONE"
  date '+%F %T' >> "$CLIPS_WT/clips/$id/DONE"
  (cd "$CLIPS_WT" && git add "clips/$id" && git commit -qm "clips: $id (${ok# })" && git push -q origin clips) >> "$LOG" 2>&1 \
    && log "$id: pushed clips [${ok# }]" || log "$id: push failed"
done
