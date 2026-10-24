#!/usr/bin/env bash
# Idempotent environment setup for the 未明新聞 pipeline (Linux x64, CPU).
# Installs: pyopenjtalk (+dictionary), VOICEVOX core 0.15.7 in a venv, ffmpeg check, fonts check.
set -euo pipefail
VV=/home/claude/vv
CORE=$VV/voicevox_core-linux-x64-cpu-0.15.7
B=https://github.com/VOICEVOX/voicevox_core/releases/download/0.15.7

command -v ffmpeg >/dev/null || { echo "ffmpeg missing"; exit 1; }
# NOTE: no `grep -q` here — under pipefail it exits early and fc-list dies with SIGPIPE (rc 141), a false "missing".
fc-list | grep "Noto Serif CJK" >/dev/null || { echo "Noto CJK fonts missing"; exit 1; }
python3 -c "import PIL, numpy" 2>/dev/null || pip install --break-system-packages -q pillow numpy
python3 -c "import googleapiclient, google.oauth2" 2>/dev/null || pip install --break-system-packages -q google-api-python-client google-auth  # upload_youtube.py
python3 -c "import runwayml" 2>/dev/null || pip install --break-system-packages -q runwayml  # gen_scene_video.py

if ! python3 -c "import pyopenjtalk" 2>/dev/null; then
  pip install --break-system-packages -q pyopenjtalk
fi
python3 - <<'EOF'
import pyopenjtalk, os
pyopenjtalk.tts("テスト")  # triggers dictionary download on first run
print(os.path.join(os.path.dirname(pyopenjtalk.__file__), "open_jtalk_dic_utf_8-1.11"))
EOF
DIC=$(python3 -c "import pyopenjtalk,os;print(os.path.join(os.path.dirname(pyopenjtalk.__file__),'open_jtalk_dic_utf_8-1.11'))")
mkdir -p $VV; echo "$DIC" > $VV/dic_path.txt

if [ ! -f "$CORE/libvoicevox_core.so" ]; then
  echo "downloading VOICEVOX core (≈1.2GB)…"
  curl -sL -o $VV/core.zip "$B/voicevox_core-linux-x64-cpu-0.15.7.zip"
  (cd $VV && unzip -q -o core.zip && rm -f core.zip)
fi
# check the import, not the venv dir: an interrupted first run leaves the venv without the wheel installed
if ! (cd "$CORE" 2>/dev/null && "$VV/vvenv/bin/python" -c "import voicevox_core" 2>/dev/null); then
  [ -x "$VV/vvenv/bin/python" ] || python3 -m venv --system-site-packages $VV/vvenv
  WHL="$VV/voicevox_core-0.15.7+cpu-cp38-abi3-linux_x86_64.whl"
  # resume + retry: the 1.2GB transfer gets cut off through the proxy, leaving a truncated (non-zip) file
  python3 -c "import zipfile,sys;zipfile.ZipFile(sys.argv[1]).testzip()" "$WHL" 2>/dev/null || \
    curl -sL -C - --retry 5 --retry-all-errors -o "$WHL" "$B/voicevox_core-0.15.7+cpu-cp38-abi3-linux_x86_64.whl"
  $VV/vvenv/bin/pip install -q "$VV/voicevox_core-0.15.7+cpu-cp38-abi3-linux_x86_64.whl" "pydantic<2" numpy
fi
PKG=$($VV/vvenv/bin/python -c "import voicevox_core,os;print(os.path.dirname(voicevox_core.__file__))" 2>/dev/null || echo $VV/vvenv/lib/python3*/site-packages/voicevox_core)
cp -n $CORE/libonnxruntime.so.1.13.1 $PKG/ 2>/dev/null || true
echo "setup ok"
