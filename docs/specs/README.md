# Rhinestone 実装仕様

> **文書ステータス: 履歴資料。** v0.4の設計を実装境界へ整理した文書で、現行APIの契約ではありません。現在の参照先は[ドキュメントの位置付け](../documentation-status.md)を確認してください。

このディレクトリは、[Rhinestone仕様書v0.4](../spec_v4.md)を実装可能・検証可能な単位へ整理した当時の補助文書です。

## 読む順序

1. [スコープと設計原則](01-scope-and-decisions.md)
2. [Core データモデル](02-domain-model.md)
3. [パイプラインとコンポーネント](03-pipeline-and-ports.md)
4. [Config 契約](04-config-contract.md)
5. [Source Adapter 契約](05-source-adapters.md)
6. [信頼性とエラー](06-validation-and-errors.md)
7. [利用インターフェース](07-public-api.md)
8. [テスト戦略](08-testing.md)

## 規範用語

**MUST（必須）**、**MUST NOT（禁止）**、**SHOULD（推奨）**、**MAY（任意）**を規範用語として用います。コード例と型名は概念的な契約を示し、実装済みの公開 API を意味しません。

## 仕様化の単位

新しい対応は、処理エンジンの再実装ではなく、配信元・Resource・アクセス方式・既存 OSS への接続知識を追加する垂直スライスとして設計します。代表 Fixture、期待する Source・AccessPlan・Resource、実行 Adapter の翻訳結果、失敗条件を同じ単位で定義します。
