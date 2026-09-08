# Rhinestone コンポーネント仕様

> **文書ステータス: 履歴資料。** v0.4の設計を実装境界へ整理した文書で、現行APIの契約ではありません。現在の参照先は[ドキュメントの位置付け](../documentation-status.md)を確認してください。

このディレクトリは、[Rhinestone仕様書v0.4](../spec_v4.md)のモデルとコンポーネントを実装境界へ整理した当時の補助文書です。

## 表記

データ／モデルは通常表記、処理コンポーネントは `［］` で表します。

```text
Config, Source, Metadata, AccessPlan, Resource
［Source Adapter］, ［Resolver］, ［Execution Adapter］
```

**MUST（必須）**、**MUST NOT（禁止）**、**SHOULD（推奨）**、**MAY（任意）**を規範用語として使用します。

## 読む順序

| 順序 | 文書 | 内容 |
| ---: | --- | --- |
| 1 | [システム境界](00-system-boundaries.md) | 所有権、パイプライン、不変条件 |
| 2 | [Core データ層](01-domain-layer.md) | Config、Source、Resource 等のモデル |
| 3 | [調整コンポーネント](02-application-layer.md) | Resolver、Search Coordinator、Selector |
| 4 | [Registry と依存境界](03-ports-layer.md) | Adapter Registry、Dependency Registry |
| 5 | [Adapter 層](04-adapters-layer.md) | Source Adapter、Execution Adapter |
| 6 | [Interface / Composition 層](05-interface-composition-layer.md) | 利用インターフェース、構成、公開失敗 |

## 中心パイプライン

```text
Config
  -> ［Source Adapter］
  -> Source
  -> ［Resolver］
  -> AccessPlan
  -> Resource
  -> ［Execution Adapter Selector］
  -> ［Execution Adapter］
  -> user-provided dependency
  -> Data
```

検索は別の入口を持ちますが、SearchResult を Config に変換してこのパイプラインへ合流します。

## 変更規則

- 新しい種類は provider、Resource、access specification、外部 OSS の接続知識を含む垂直スライスで実証する（MUST）。
- 配信元固有の知識を Core データや Resolver へ持ち込まない（MUST NOT）。
- 外部 OSS 固有の知識を Source Adapter へ持ち込まない（MUST NOT）。
- 入力、出力、副作用、失敗型、知識の保持方法を定義する（MUST）。
- 外部 Adapter API は、複数実装で反復可能な契約が確認されるまで公開しない（MUST NOT）。
