# Rhinestone コンポーネント仕様

## 位置づけ

このディレクトリは、[`spec_v2.md`](../spec_v2.md) が定める設計思想と不変条件を、実装可能なコンポーネント境界へ分解した仕様である。特定の配信元、サービス、ファイル形式、外部ライブラリごとの仕様ではない。新しい種類を追加するときも、まずここで定める抽象的な責務へ割り当て、既存の境界で表現できないことが実例によって確認されるまで新しい階層を設けない。

`spec_v2.md` がアーキテクチャと不変条件の信頼できる唯一の情報源であり、このディレクトリはその詳細化である。両者が矛盾する場合は実装で解釈せず、文書上の矛盾を先に解消しなければならない（MUST）。

## 規範用語

**MUST（必須）**、**MUST NOT（禁止）**、**SHOULD（推奨）**、**MAY（任意）**を規範用語として用いる。コード例と型名は契約を説明するための概念表現であり、モジュール名や実装方式を固定しない。

## 階層と読む順序

| 順序 | 階層 | 文書 | 主なコンポーネント |
| ---: | --- | --- | --- |
| 1 | 全体 | [システム境界](00-system-boundaries.md) | パイプライン、依存方向、I/O 所有権 |
| 2 | Domain | [ドメイン層](01-domain-layer.md) | DataReference、SourceMetadata、Capability、AccessPlan |
| 3 | Application | [アプリケーション層](02-application-layer.md) | Config Parser、Reference Factory、Resolver、Executor、Application |
| 4 | Ports | [ポート層](03-ports-layer.md) | Metadata Adapter、Transport、Loader、Registry 契約 |
| 5 | Adapters | [アダプター層](04-adapters-layer.md) | Source Adapter、Transport Adapter、Loader Adapter |
| 6 | Interface / Composition | [インターフェース・構成層](05-interface-composition-layer.md) | Public API、既定 Application、エラー公開境界 |

ファイルは実装技術や種類ではなく階層ごとに分ける。同じ契約を満たす実装を追加するたびに、種類別のアーキテクチャ文書を増やしてはならない（MUST NOT）。種類固有のプロトコル詳細が必要な場合は、適合 Fixture と垂直スライス仕様に置き、ここでは共通契約への適合条件だけを扱う。

## 中心パイプライン

```text
Mapping
  -> Config
  -> DataReference
  -> SourceMetadata
  -> AccessPlan
  -> Execution
  -> Data
```

各矢印は明示されたコンポーネント境界である。後段は前段の Value Object を変更せず、新しい値を生成する。`plan()` は `Config` から `AccessPlan` までを、`execute()` は `AccessPlan` から `Data` までを担当し、`load()` は両者を順に合成する。

## 変更規則

- 公開 API や中心 Value Object を変更するときは、影響する階層仕様と適合テストを同じ変更で更新しなければならない（MUST）。
- コンポーネント追加は、入力、出力、副作用、失敗型、依存方向を定義しなければならない（MUST）。
- 配信元や外部 OSS の名前を Domain と Resolution Policy に持ち込んではならない（MUST NOT）。
- 新しい種類は `Config -> Reference -> Metadata -> Plan -> Data` の垂直スライスと、各境界の適合テストで実証することが望ましい（SHOULD）。
- 公開 Plugin API は、複数の実装で反復可能な契約が確認されるまで設計しない（MUST NOT）。v0.x では内部 Registry を構成境界として用いる。
