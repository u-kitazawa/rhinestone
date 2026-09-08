# e-Statで人口統計表を探す

e-Statの検索結果から人口統計表を選び、Rhinestoneで表のmetadataと統計サービスへの解決情報を取得します。これはAPI / identifier型の例です。

## 必要なもの

- RhinestoneとPython 3.10以上
- e-Stat APIのアプリケーションID
- e-Stat APIへのnetwork access

アプリケーションIDは[e-Stat API](https://www.e-stat.go.jp/api/)で取得してください。secretはSourceや検索結果に保存せず、Credential factoryから渡します。

```console
python -m pip install rhinestone
export RHINESTONE_ESTAT_APP_ID="your-application-id"
export RHINESTONE_ESTAT_RESULT_INDEX="0"
```

## 検索して表を選ぶ

```python
import os

from rhinestone import configure, sources

app_id = os.environ["RHINESTONE_ESTAT_APP_ID"]
app = configure(
    sources=(sources.ESTAT,),
    credentials={"estat": lambda: app_id},
)

results = app.search(text="人口", limit=10)
if not results:
    raise RuntimeError("e-Statの検索結果がありません")

for index, result in enumerate(results):
    print(f"[{index}] {result.title}")

selected = results[int(os.environ["RHINESTONE_ESTAT_RESULT_INDEX"])]
resource = app.resolve(selected)
```

`selected`は検索結果に含まれるe-Stat固有の`statsDataId`を保持しています。利用者が表示内容を確認してから選択するため、Rhinestoneがタイトルや提供元から統計表を推測することはありません。

## 解決結果を確認する

```python
print("title:", resource.metadata.title)
print("provider:", resource.provenance.provider)
print("stats data id:", resource.provenance.dataset_identifier)
print("service URI:", resource.uri)
print("access plan:", resource.access_plan.kind)
```

現行のe-Stat Source Adapterは、統計表のmetadataと`getStatsData`用のservice-query Resourceまでを担当します。統計値を表形式で取得するbuilt-in Execution Adapterはまだないため、この例のRhinestone側の責務はここで終わります。`resource.open(...)`で未対応のRuntimeを推測して呼び出すことはありません。

Credential、network、e-Stat側の`statsDataId`とデータ公開状態は利用者と提供元の責務です。APIの応答形式や表の入れ替えにより、検索結果の順番は変わる可能性があります。

詳細は[e-Stat Source Adapter](../api/adapters/estat.md)、[対応状況](../compatibility.md)、[Credential](../configuration.md#credential)を参照してください。
