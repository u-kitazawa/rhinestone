# Rhinestone 実装仕様

このディレクトリでは、[`spec_v2.md`](../spec_v2.md) の目標を、実装およびテスト可能な要件として具体化する。`spec_v2.md` は引き続きプロダクトとアーキテクチャのビジョンを示す。ここにある文書は、v0.x の実装詳細に関する信頼できる唯一の情報源である。

## 読む順序

1. [スコープと設計判断](01-scope-and-decisions.md)
2. [ドメインモデル](02-domain-model.md)
3. [パイプラインと Port](03-pipeline-and-ports.md)
4. [設定仕様](04-config-contract.md)
5. [CKAN 垂直スライス](05-ckan-vertical-slice.md)
6. [検証とエラー](06-validation-and-errors.md)
7. [公開 API とパッケージ構成](07-public-api.md)
8. [テスト戦略](08-testing.md)

## 規範を表す用語

**MUST（必須）**、**MUST NOT（禁止）**、**SHOULD（推奨）**、**MAY（任意）** は、この順に厳格さが下がる要件を表す。例は仕様を説明するものであり、暗黙に要件を追加するものではない。

これらの文書と `spec_v2.md` が矛盾する場合、実装前に文書上で矛盾を解消しなければならない（MUST）。実装側で、どちらの規則が意図されたかを推測してはならない（MUST NOT）。

## 初期リリースの範囲

最初の垂直スライスは意図的に狭くする。

```text
CKAN resource ID
  -> CKAN resource_show metadata
  -> GeoPackage file access plan
  -> vector.read loader binding
  -> loaded data
```

Direct Resource は、プロバイダーに依存しない Core の小規模な比較対象としてのみ含める。e-Stat、OGC API、STAC、キャッシュ、YAML の解析、追加フォーマットは、最初のスライスが仕様を満たした後に対応する。

## 文書の状態

これらの仕様は、対応する仕様適合テストと実装が存在するまでは**提案段階**である。未解決の設計課題は[スコープと設計判断](01-scope-and-decisions.md)にまとめる。コードは、未解決の課題が特定の結論になることに依存してはならない（MUST NOT）。
