#!/usr/bin/env bash
# 未明新聞パイプライン — macOS (Apple Silicon) 用の冪等セットアップ。Mac mini で1回だけ実行（失敗したら再実行してよい）。
#   bash pipeline/macmini/setup_mac.sh
# 入れるもの: Homebrew ffmpeg / python / Noto CJK フォント, venv (~/mimei/vv/vvenv), VOICEVOX core 0.15.7 (osx-arm64, 約1.2GB),
#             pyopenjtalk(+辞書), pillow/numpy, google-api-python-client, runwayml
# 置き場: $MIMEI_VV（既定 ~/mimei/vv）。pipeline.py / tts.py はこの環境変数で場所を知る（run.sh が渡す）。
set -euo pipefail
VV="${MIMEI_VV:-$HOME/mimei/vv}"
VER=0.15.7
CORE="$VV/voicevox_core-osx-arm64-cpu-$VER"
B="https://github.com/VOICEVOX/voicevox_core/releases/download/$VER"
WHL_NAME="voicevox_core-$VER+cpu-cp38-abi3-macosx_11_0_arm64.whl"

[ "$(uname -s)" = "Darwin" ] || { echo "this script is for macOS"; exit 1; }
[ "$(uname -m)" = "arm64" ] || { echo "Apple Silicon (arm64) only"; exit 1; }
command -v brew >/dev/null || { echo "Homebrew missing: https://brew.sh"; exit 1; }
eval "$(brew shellenv)"

# --- Homebrew: ffmpeg, python, fonts --------------------------------------------------------------
brew list ffmpeg >/dev/null 2>&1 || brew install ffmpeg
brew list python@3.12 >/dev/null 2>&1 || brew install python@3.12
PY="$(brew --prefix python@3.12)/bin/python3.12"
# Noto CJK (JP の .otf。render.py が ~/Library/Fonts/NotoSerifCJKjp-Bold.otf / NotoSansCJKjp-Regular.otf を拾う)
brew list --cask font-noto-serif-cjk-jp >/dev/null 2>&1 || brew install --cask font-noto-serif-cjk-jp
brew list --cask font-noto-sans-cjk-jp  >/dev/null 2>&1 || brew install --cask font-noto-sans-cjk-jp
[ -f "$HOME/Library/Fonts/NotoSerifCJKjp-Bold.otf" ] || { echo "NotoSerifCJKjp-Bold.otf missing"; exit 1; }
[ -f "$HOME/Library/Fonts/NotoSansCJKjp-Regular.otf" ] || { echo "NotoSansCJKjp-Regular.otf missing"; exit 1; }

# --- venv（システムの python には入れない）--------------------------------------------------------
mkdir -p "$VV"
[ -x "$VV/vvenv/bin/python" ] || "$PY" -m venv "$VV/vvenv"
VPY="$VV/vvenv/bin/python"; VPIP="$VV/vvenv/bin/pip"
"$VPIP" install -q --upgrade pip
"$VPY" -c "import PIL, numpy" 2>/dev/null || "$VPIP" install -q pillow numpy
"$VPY" -c "import googleapiclient, google.oauth2" 2>/dev/null || "$VPIP" install -q google-api-python-client google-auth
"$VPY" -c "import runwayml" 2>/dev/null || "$VPIP" install -q runwayml
if ! "$VPY" -c "import pyopenjtalk" 2>/dev/null; then
  brew list cmake >/dev/null 2>&1 || brew install cmake     # wheel が無い Python では源からビルドされる
  "$VPIP" install -q pyopenjtalk
fi
"$VPY" - <<'EOF'
import pyopenjtalk, os
pyopenjtalk.tts("テスト")  # 初回に辞書 (open_jtalk_dic_utf_8-1.11) を DL
print(os.path.join(os.path.dirname(pyopenjtalk.__file__), "open_jtalk_dic_utf_8-1.11"))
EOF
DIC=$("$VPY" -c "import pyopenjtalk,os;print(os.path.join(os.path.dirname(pyopenjtalk.__file__),'open_jtalk_dic_utf_8-1.11'))")
echo "$DIC" > "$VV/dic_path.txt"

# --- VOICEVOX core (osx-arm64) ----------------------------------------------------------------------
if [ ! -f "$CORE/libvoicevox_core.dylib" ]; then
  echo "downloading VOICEVOX core (≈1.2GB)…"
  curl -L --retry 5 --retry-all-errors -C - -o "$VV/core.zip" "$B/voicevox_core-osx-arm64-cpu-$VER.zip"
  (cd "$VV" && unzip -q -o core.zip && rm -f core.zip)
fi
if ! (cd "$CORE" && "$VPY" -c "import voicevox_core" 2>/dev/null); then
  WHL="$VV/$WHL_NAME"
  "$VPY" -c "import zipfile,sys;zipfile.ZipFile(sys.argv[1]).testzip()" "$WHL" 2>/dev/null || \
    curl -L --retry 5 --retry-all-errors -C - -o "$WHL" "$B/$WHL_NAME"
  "$VPIP" install -q "$WHL" "pydantic<2" numpy
fi
PKG=$("$VPY" -c "import voicevox_core,os;print(os.path.dirname(voicevox_core.__file__))")
cp -n "$CORE"/libonnxruntime*.dylib "$PKG/" 2>/dev/null || true
cp -n "$CORE"/libvoicevox_core.dylib "$PKG/" 2>/dev/null || true
# Gatekeeper の隔離属性を外す（DL した dylib がブロックされるのを防ぐ）
xattr -dr com.apple.quarantine "$CORE" "$PKG" 2>/dev/null || true

# --- 動作確認（1行だけ合成）-------------------------------------------------------------------------
(cd "$CORE" && DYLD_LIBRARY_PATH="$CORE" "$VPY" - <<EOF
from voicevox_core import VoicevoxCore
c = VoicevoxCore(open_jtalk_dict_dir=open("$VV/dic_path.txt").read().strip())
c.load_model(52); q = c.audio_query("セットアップ完了", 52); w = c.synthesis(q, 52)
print("voicevox ok", len(w), "bytes")
EOF
)
command -v ffmpeg >/dev/null && echo "ffmpeg ok"
echo "setup ok  (MIMEI_VV=$VV)"
