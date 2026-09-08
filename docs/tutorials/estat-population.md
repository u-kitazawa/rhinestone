# e-Statで人口統計表を探し、Resourceへ解決する

e-Statでは、検索結果に含まれる `statsDataId` を使って統計表のmetadataを解決します。
ここでは、検索結果を表示してから一件を選び、`Resource`まで到達します。

## 準備

1. [e-Stat API](https://www.e-stat.go.jp/api/)でapplication IDを取得します。
2. Rhinestoneをインストールします。

```console
python -m pip install rhinestone
export RHINESTONE_ESTAT_APP_ID="your-application-id"
export RHINESTONE_ESTAT_QUERY="人口"
```

application IDはコードや `Config` に直接書かず、credential factoryから渡します。

## 検索して解決する

```python
import os

from rhinestone import configure, sources

app_id = os.environ["RHINESTONE_ESTAT_APP_ID"]
app = configure(
    sources=(sources.ESTAT,),
    credentials={"estat": lambda: app_id},
)

results = app.search(
    text=os.environ.get("RHINESTONE_ESTAT_QUERY", "人口"),
    limit=10,
)
if not results:
    raise RuntimeError("e-Stat search returned no results")

for index, result in enumerate(results):
    print(f"[{index}] {result.title}")
    print("    statsDataId:", result.provenance.dataset_identifier)

selected_index = int(os.environ.get("RHINESTONE_ESTAT_RESULT_INDEX", "0"))
selected = results[selected_index]
resource = app.resolve(selected)

print("title:", resource.metadata.title)
print("statsDataId:", resource.provenance.dataset_identifier)
print("service URI:", resource.uri)
print("access plan:", resource.access_plan)
```

`app.resolve(selected)`の内部では、検索結果が保持している `statsDataId` を使って
e-Statの `getMetaInfo` を呼び出します。これにより、検索、結果選択、識別子の解決、
metadataとprovenanceを持つResourceの生成までをRhinestoneが担当します。

## この例の境界

現行のe-Stat Adapterは統計表metadataと `getStatsData` 用のservice-query Resourceを
解決しますが、統計値をDataFrameなどへ変換するExecution Adapterは提供していません。
したがって、この例の完了点は `Resource` です。統計値の取得や集計を続ける場合は、
Resourceのprovenanceにある識別子とproviderの公式仕様を確認し、利用する統計処理系へ
明示的に渡してください。

- 必須: ネットワーク接続、e-Stat application ID
- 変更される値: 検索結果、`statsDataId`、metadata
- Rhinestoneの責務: e-Stat APIの検索・metadata解釈・識別子からResourceへの解決
- provider / 利用者の責務: API利用条件、統計値の取得・解析、データの解釈

認証情報の扱いは[アプリケーションを構成する](../configuration.md)、e-Stat固有の制限は
[e-Stat Adapter](../api/adapters/estat.md)を参照してください。
