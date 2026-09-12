# DirectAdapter（直接指定アダプター）

`DirectAdapter` は、完全に記述された単一 Resource を解決します。

[Source Adapter 一覧](../source-adapters.md) · source type: `direct`

## 設定

| 項目 | 必須 | 説明 |
| --- | --- | --- |
| `uri` | はい | Resource URI |
| `format` | はい | 明示する形式 |
| `media_type` | いいえ | media type |
| `archive`, `encoding`, `layer`, `subdataset`, `metadata` | いいえ | Resource の追加属性 |

URL、形式、runtime は推測しません。

## 最小例

```python
from rhinestone import Config, configure
app = configure()
resource = app.resolve(
    Config("direct", {"uri": "https://example.invalid/data.geojson", "format": "geojson"})
)
```

実在するデータを開くには、対応するruntime dependencyも登録します。手順は
[Resource を解決して開く](../../resolve-and-open.md)を参照してください。
