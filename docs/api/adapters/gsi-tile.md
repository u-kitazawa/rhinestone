# GSIタイル

国土地理院タイルは、組み込みの \`sources.GSI\` が提供する静的サービス定義として
扱います。

[StaticAdapter](static.md) · source id: \`gsi\`

## 設定

\`\`\`python
from rhinestone import Config

Config("gsi", {"id": "std"})
Config("gsi", {"id": "pale"})
\`\`\`

定義にはHTTPS URL、XYZ、CRS、format、media type、zoom範囲、tile size、帰属表示、
利用条件URL、仕様確認日が含まれます。定義はリポジトリでレビュー・管理され、実行時
に国土地理院へメタデータ取得を行いません。

選択済みResourceをGDALで開く場合は、既存の \`GdalAdapter\` がXYZ定義をGDALの
TMS設定へ翻訳します。
