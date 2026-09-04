# Core データモデル

Core は次のデータ／モデルを扱います。provider や外部ライブラリ固有の型を共通モデルへ漏らしてはなりません（MUST NOT）。

## Config

利用したいデータを宣言します。Source Adapter の選択に必要な provider 固有設定は保持しますが、HTTP クライアントや GDAL option などの実行詳細は原則として含めません。

Config は実行によって暗黙に変化してはなりません（MUST NOT）。

## Source

Source Adapter が外部 provider を解釈した結果です。

```text
Source
├ Metadata
├ Resource candidates
├ Capability information
├ Provenance
└ source-specific raw metadata
```

Source は巨大な共通 Metadata schema を目指しません。必要最小限の共通項目と provider 固有の raw metadata をともに保持します。

## Metadata

Metadata は title、description、publisher、license、updated time、resource identifier、format、media type、CRS、source URL、API endpoint、query parameter など、取得・解決過程で確定した知識を表します。

共通項目へ過度に正規化せず、元の Metadata を欠落なく参照できる構造にします。一度確定した情報を後続処理の都合で破棄してはなりません（MUST NOT）。

## AccessPlan

Resource へのアクセス方法を表し、実際の OSS への依存は持ちません。配信形態に応じて、少なくとも次のような具象化を許容します。

```text
FileAccessPlan
RemoteDatasetPlan
ServiceQueryPlan
```

## Resource

解決済みで利用可能なデータ資源です。

```text
Resource
├ uri
├ format
├ media_type
├ Metadata
├ Provenance
├ AccessPlan
├ Source
└ optional local_path
```

Resource を単なる URI に縮退させてはなりません（MUST NOT）。

## Provenance

provider、dataset/resource identifier、API endpoint、original URL、query parameter、retrieved time、checksum、Adapter とその version、raw metadata など、取得・解決経路を表します。

## SearchQuery と SearchResult

SearchQuery の共通条件は `text`、`bbox`、`time`、`limit` など必要最小限にします。Source Adapter は未対応の検索条件を黙って無視してはなりません（MUST NOT）。

SearchResult は title、description、Adapter/source type、provider 固有 Config、Metadata、Provenance を保持します。データ取得時には Config に変換し、通常の検証・解決フローへ渡します。
