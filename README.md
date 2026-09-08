# 未明新聞 号外

YouTube チャンネル「[未明シアター](https://www.youtube.com/@mimei_theater)」の動画を、新聞をまとった三人のキャラクター（号外・ホゴ・ヨミ）がランダムにおすすめしてくれるファン制作の非公式アプリです。

- `index.html` 1ファイルで動作します（画像・動画データはすべて埋め込み済み）
- 公開は GitHub Pages（Settings → Pages → Branch: `main` / `/ (root)`）

## 動画データの更新

`index.html` 内の `const VIDEOS = [...]` を編集すると作品一覧を更新できます。各要素は
`{id: 動画ID, t: タイトル, d: 尺, v: 視聴数, a: 公開時期, c: カテゴリ}` で、
カテゴリは `short` / `one` / `file` / `dive` / `omnibus` のいずれかです。
