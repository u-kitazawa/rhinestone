# Adapter拡張用fixture

公式のデータ構造を最小限に再現した合成例です。実際のデータセットのスナップショットや、
スキーマ適合性を完全に検証するサンプルではありません。`fixture`を含む識別子は、実際のサービスへ送信してはいけません。

- `plateau.json`: CKAN Action APIのpackage応答。参考:
  https://front.geospatial.jp/wp-content/uploads/2022/03/gic-api.pdf
- `catalog.ttl`: DCAT Dataset/Distribution。ファイルとして開いてはいけない、accessURLだけを持つランディング
  ページも含みます。https://www.w3.org/TR/vocab-dcat-3/
- `city.gml`: GMLのフットプリントを持つCityGML 2.0 Building:
  https://schemas.opengis.net/citygml/2.0/
- `basic.xml`: 国土地理院の建物面基本項目の形状構造:
  https://service.gsi.go.jp/kiban/app/help/
- `odpt.json`: ODPT駅応答の語彙と配列形式:
  https://developer.odpt.org/documents

適合テストでは、Source、候補、AccessPlan、open結果を明示的に検証します。GMLサンプルは読み込み機能との
互換性を確認するもので、PLATEAUや基盤地図情報の完全な検証ではありません。
