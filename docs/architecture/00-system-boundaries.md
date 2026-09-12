# システム境界

> **文書ステータス: 履歴資料。** v0.4の設計を実装境界へ整理した文書で、現行APIの契約ではありません。現在の参照先は[ドキュメントの位置付け](../documentation-status.md)を確認してください。

## 目的

Rhinestone は異なる公的データ provider と既存 OSS の間にある知識の断絶を埋めます。アクセス方法を決定する知識を所有し、データ処理自体は外部 OSS に委譲します。

## 所有権

| 所有者 | 対象 |
| --- | --- |
| Rhinestone | Configの解釈、Source、Metadata、AccessPlan、Resource、Provenance、提供元／形式／アクセス方法の知識 |
| Rhinestoneの構成要素 | Source Adapter、Resolver、Search Coordinator、Execution Adapter Selector、Execution Adapter、各Registry |
| 利用者 | 外部ライブラリ、バージョン、アプリケーション固有の処理 |
| 既存OSS | ファイル解析、GIS入出力、ラスタ／ベクター処理、形式変換、分析 |

## アクセス境界

Source Adapter は provider との通信を所有し、Source を返します。Resolver は Source の候補から Resource と AccessPlan を決めます。Execution Adapter は Resource を外部 OSS 向けに翻訳し、Dependency Registry から利用者所有の runtime を取得します。

Resolver と Selector は、通常の解決で provider metadata やデータ本体へ I/O を行ってはなりません（MUST NOT）。Execution Adapter は Resource 候補を選択してはなりません（MUST NOT）。

## 検索境界

Search Coordinator は検索 Capability を持つ Source Adapter に公式 API 経由で問い合わせます。中央 index は必須としません。SearchResult は直接実行せず、Config に変換して通常のアクセス境界へ渡します。

## 不変条件

- Config は実行により変化しない。
- provider 固有 Reference は Source Adapter 内部に留まる。
- Source は解釈済み情報と raw metadata を保持する。
- Metadata と Provenance は Resource まで失われない。
- 暗黙の format 変換、URL 推測、silent fallback を行わない。
- Core では HTML scraping を行わない。
- 同じ入力と Capability から同じ AccessPlan を得る。
- runtime dependency は Core の所有物ではない。
