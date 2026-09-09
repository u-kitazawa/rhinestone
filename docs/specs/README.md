# Rhinestone 実装仕様

このディレクトリは、[Rhinestone 仕様書](../spec_v4.md)を実装可能・検証可能な単位へ整理した補助文書です。設計仕様がアーキテクチャ、責務境界、不変条件の唯一の規範であり、内容が矛盾する場合は設計仕様を優先します。

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
