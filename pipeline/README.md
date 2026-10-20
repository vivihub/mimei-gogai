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

## 構成
`tts.py`（VOICEVOX）→ `render.py`（静止フレーム・voice.wav）→ `mix_bgm.py`（bgm/ の normal/ominous/ending を場面切替・ダッキング）→ `render_anim.py`（口パク・まばたき・30fps）→ `pipeline.py`（サムネ・説明文）

## 声（VOICEVOX）
ミメイ=雀松朱司(52) / ハス=中部つるぎ ヒソヒソ(96) / ヨミ=小夜SAYO(46)。動画説明文にクレジット必須。

## ネタ管理
`topics.json` の `queue` から順に消化し、作ったら `done` へ移す。
