# EstatGisAdapter（e-Stat統計GISアダプター）

`EstatGisAdapter` は、利用者が用意した e-Stat Statistics GIS の配布物インデックスから、
明示された配布物を一般的な GIS `Resource` として解決します。

[Source Adapter 一覧](../source-adapters.md) · source type: `estat-gis`

## 方針

e-Stat の公開画面は配布物のダウンロード UI です。Rhinestone はその HTML を scraping
せず、URL や配布物を推測しません。アプリケーションが公式情報から作成した、固定された
機械可読インデックスを `Provider.settings["distributions"]` に渡します。

インデックスの dataset identity と distribution identity は URL と別に保持されます。
ZIP 配布物は `archive="zip"` と安全な相対 `entry_point` を明示します。

## 設定例

```python
from rhinestone import Config, Provider, configure

app = configure(
    sources=(
        Provider(
            "estat",
            "estat-gis",
            {
                "distributions": [
                    {
                        "distribution_id": "census-2020-tokyo-gml",
                        "dataset_id": "census-2020",
                        "boundary_kind": "municipality",
                        "survey_year": 2020,
                        "level": "municipality",
                        "region_code": "13",
                        "format": "GML",
                        "uri": "https://www.e-stat.go.jp/gis/download/example.gml",
                        "title": "国勢調査 2020 東京都",
                    }
                ]
            },
        ),
    )
)

resource = app.resolve(
    Config(
        "estat",
        {
            "dataset_id": "census-2020",
            "survey_year": 2020,
            "level": "municipality",
            "region_code": "13",
            "format": "gml",
        },
    )
)
```

利用できる selector は `distribution_id`、`dataset_id`、`boundary_kind`、
`survey_year`、`time`、`time_kind="survey_year"`、`level`、`region_code`、`format` です。
複数候補が残る場合は Resolver が曖昧さとして扱います。`time` を指定すると共有 Time
Knowledge Adapter で解決し、統計調査年として候補を絞ります。

`search()` は渡されたインデックス内の `text` と `limit` だけを扱います。検索条件を
追加して推測による discovery を行うことはありません。
