# CKAN GeoPackage 垂直スライス

## Request の仕様

次の Reference に対して、

```text
endpoint = https://example.jp/api/3
resource_id = abc def
```

Adapter は HTTP GET を1回実行する。

```text
https://example.jp/api/3/action/resource_show?id=abc%20def
```

設定された Endpoint に CKAN Protocol の Path を正確に追加して使用する。Redirect 処理、Timeout、Header は注入された HTTP Transport の責務である。既定の Transport は有限の Timeout を設定し、User-Agent で Client を識別しなければならない（MUST）。

Adapter は `package_show`、`package_search` の呼び出し、HTML のスクレイピング、Resource URI への HEAD Request、Resource Byte のダウンロードを行ってはならない（MUST NOT）。

## 成功レスポンス

代表的な CKAN Response：

```json
{
  "help": "https://example.jp/api/3/action/help_show?name=resource_show",
  "success": true,
  "result": {
    "id": "abc def",
    "name": "Administrative areas",
    "url": "https://data.example.jp/areas.gpkg",
    "format": "GPKG",
    "mimetype": "application/geopackage+sqlite"
  }
}
```

正規 Metadata への対応は次のとおり。

```text
SourceMetadata.identifier = result.id
SourceMetadata.title = result.name
SourceMetadata.authority = configured endpoint
SourceMetadata.license = absent
SourceMetadata.resources[0].identifier = result.id
SourceMetadata.resources[0].uri = result.url
SourceMetadata.resources[0].format = result.format
SourceMetadata.resources[0].media_type = result.mimetype
SourceMetadata.raw = complete decoded response object
```

Resource Level の `resource_show` からは、Package の License Data を確実に取得できない。Adapter は License を埋めることだけを目的とした2回目の Package Request を実行してはならず（MUST NOT）、このスライスでは License を未設定のままにする。

返された `result.id` は Request した ID と一致しなければならない（MUST）。不一致は不正な Metadata であり、新たな Resource の選択ではない。

## Response の検証

Adapter は、Boolean の `success` と Object の `result` を持つ JSON Object だけを受け付ける。

- `success: false` の場合は `MetadataUnavailable` を送出し、CKAN Error Object を安全な診断 Context として保持する。
- Envelope Field が欠けている、または不正な場合は `MetadataInvalid` を送出する。
- `id` または `url` が欠けている、空である、または String でない場合は `MetadataInvalid` を送出する。
- Resource URL が不正、または HTTP(S) でない場合は `MetadataInvalid` を送出する。
- Transport の失敗または不正な JSON の場合は、元の Exception を Cause として保持して `MetadataUnavailable` を送出する。

## Format Policy

初期 Resolver は、次の明示的な Alias を大文字と小文字を区別せずに認識する。

| Provider Format | 正規 Format | Capability |
| --- | --- | --- |
| `GPKG` | `geopackage` | `vector.read` |
| `GeoPackage` | `geopackage` | `vector.read` |
| `geopackage` | `geopackage` | `vector.read` |

`format` が存在しない場合、Media Type が `application/geopackage+sqlite` と完全に一致すれば、正規 Format の決定に使用してもよい（MAY）。認識済みの Format と Media Type が競合する場合は `MetadataInvalid` を送出する。認識できない値の場合は `UnsupportedFormat` を送出する。明らかに見える場合でも URI の接尾辞は無視する。

## 期待される Plan

利用可能な Binding `(pyogrio, vector.read, priority=100)` がある場合、代表的な Metadata は次のように解決される。

```text
FileAccessPlan
  uri = https://data.example.jp/areas.gpkg
  format = geopackage
  capability = vector.read
  loader.identifier = pyogrio
  source_identifier = abc def
```

`vector.read` の Binding が提示されていない場合、解決処理は `CapabilityUnavailable` を送出する。解決処理で、検出のために pyogrio を Import してはならない（MUST NOT）。

## pyogrio Loader の実行仕様

初期 Loader は `pyogrio.read_dataframe(plan.uri)` に処理を委譲し、その結果を変更せずに返す。Temporary File へのダウンロード、Layer の選択、CRS の変換、Column の正規化、Geometry の検証は行わない。

Import に失敗した場合は `CapabilityUnavailable` を送出する。解決済み URI の読み込み中に送出された Exception は、元の Exception を Cause として保持した `ResourceUnavailable` に変換する。
