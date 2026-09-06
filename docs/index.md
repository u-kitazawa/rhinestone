# Rhinestone documentation

Rhinestone は、日本の公的・地理空間データを
**検索し、利用可能な Resource へ解決し、既存のライブラリで利用するための Python ライブラリ**です。

データ提供元ごとに異なる検索 API、データ構造、配布形式、アクセス方法を Rhinestone が解釈します。

利用者は、提供元ごとの仕様を個別に実装する代わりに、

**検索 → 選択 → Resource の解決 → データを開く**

という共通した流れでデータを扱えます。

## まずは使ってみる

たとえば、「河川」に関するデータを探す場合です。

```python
from rhinestone import SearchQuery

results = app.search(
    SearchQuery(text="河川")
)
```

`search()` は、登録されている検索対応のデータ提供元を検索します。

検索結果から使いたいデータを選びます。

```python
result = results["ckan"][0]

print(result.title)
print(result.description)
```

選んだ検索結果は、そのまま Resource の解決へ渡せます。

```python
resource = app.resolve(
    result.to_config()
)

print(resource.uri)
print(resource.format)
```

そして、必要な Execution Adapter が登録されていれば、その Resource をそのまま開けます。

```python
with resource.open() as data:
    ...
```

つまり、Rhinestone では、

**探したデータを、実際に利用できる Resource まで同じ流れの中でつなげられます。**

検索 API のレスポンスから provider 固有の ID を取り出したり、
配布ページのリンクを解析したり、
どのファイルを使うべきか利用側で判断したりする処理を、
毎回アプリケーションに書く必要はありません。

Rhinestone が提供元の仕様を解釈し、
検索結果を Resource の解決までつなぎます。

## Rhinestone でできること

### 複数のデータ提供元を検索する

`SearchQuery` を使って、検索に対応した Source Adapter を横断的に検索できます。

```python
results = app.search(
    SearchQuery(
        text="標高",
        bbox=(139.5, 35.5, 140.0, 36.0),
        limit=10,
    )
)
```

検索条件には、キーワードのほか、Adapter が対応していれば空間範囲や時間範囲も指定できます。

利用できる条件は次のとおりです。

- `text`
- `bbox`
- `time`
- `limit`

検索 API やレスポンス形式の違いは Source Adapter が処理します。

### 検索結果からそのまま解決できる

検索結果は `SearchResult` として返されます。

`SearchResult` は表示用の検索結果ではなく、
通常の Resource 解決へ接続できる情報を保持しています。

```python
config = result.to_config()
resource = app.resolve(config)
```

利用者が検索結果から provider 固有の識別子を取り出して、
改めて `Config` を組み立てる必要はありません。

### 既知のデータを直接解決する

検索を使わず、利用したいデータがすでに決まっている場合は、
`Config` から直接 Resource を解決できます。

```python
resource = app.resolve(config)
```

検索から始める場合も、直接指定する場合も、
最終的には同じ Resource 解決フローを利用します。

### 複数の Resource から利用するものを決める

公的データでは、ひとつのデータセットに複数の配布形式やアクセス方法が存在することがあります。

Rhinestone は Source Adapter が取得した候補を解釈し、
利用する Resource と AccessPlan を決定します。

解決された Resource からは、たとえば次の情報を取得できます。

```python
print(resource.uri)
print(resource.format)
print(resource.media_type)
print(resource.metadata)
print(resource.provenance)
print(resource.access_plan)
```

単なる URL ではなく、
その Resource が何であり、どこから得られ、どうアクセスするのかを保持します。

### 既存のライブラリでデータを開く

Rhinestone 自身は GIS の読み込み、変換、解析を再実装しません。

Resource を解決した後は、
登録された Execution Adapter を通して既存のライブラリへ渡します。

```python
with resource.open() as data:
    ...
```

使用する Adapter を明示することもできます。

```python
with resource.open(adapter="rasterio") as dataset:
    ...
```

どのライブラリを利用するかは、利用者の環境に合わせて選択できます。

### データの出所を追跡する

Resource には `Metadata` と `Provenance` が保持されます。

```python
print(resource.metadata)
print(resource.provenance)
```

これにより、

- どの provider から取得したか
- どの dataset / resource を利用したか
- 元の URL や API endpoint
- どの Adapter が解決したか

といった情報を、Resource と一緒に扱えます。

### 実行環境を固定しない

GDAL、Rasterio、pyogrio などの実行ライブラリは、
Rhinestone の必須依存ではありません。

利用者が必要な runtime を登録します。

```python
app = configure(
    dependencies={
        "rasterio": lambda: rasterio,
    },
)
```

依存は遅延評価されるため、
検索や Resource の解決だけを行う場合には読み込まれません。

既存の GIS 環境を維持したまま、
必要な実行環境だけを供給できます。

## Rhinestone の役割

Rhinestone が担当するのは、
**データを見つけ、利用可能な形まで導くこと**です。

具体的には、

- データを検索する
- provider 固有の検索結果を解釈する
- データセットや Resource の候補を取得する
- 利用可能な Resource を決定する
- 適切なアクセス方法を決定する
- 既存の実行ライブラリへ接続する

ところまでを扱います。

一方で、

- GIS データの読み込み処理そのもの
- 座標変換
- データ加工
- 空間解析
- レンダリング

は既存のライブラリへ任せます。

Rhinestone は GIS ライブラリを置き換えるものではなく、
**公的・地理空間データと既存の GIS エコシステムをつなぐ層**です。

## インストール

Rhinestone は Python 3.10 以上に対応します。

```console
pip install rhinestone
```

データを実際に開く場合は、
利用する Execution Adapter に対応したライブラリを別途インストールしてください。

たとえば Rasterio を利用する場合は、
Rhinestone とは別に Rasterio を環境へ導入します。

アプリケーションでは、provider設定と利用するdependencyを登録します。Adapterは
Rhinestoneが構成します。

```python
from rhinestone import ProviderConfig, configure

app = configure(
    providers={"catalog": ProviderConfig("ckan", {"endpoint": "..."})},
    dependencies={...},
)
```

詳しい構成方法は [Getting started](getting-started.md) を参照してください。

## 次に読む

Rhinestone の基本的な使い方から始める場合は
[Getting started](getting-started.md) を参照してください。

provider構成、HTTP callback、secret の渡し方は
[アプリケーションを構成する](configuration.md) を参照してください。

検索結果を選ぶ流れは [データを検索する](search.md)、Resource を確認して runtime で
開く流れは [Resource を解決して開く](resolve-and-open.md) を参照してください。

利用可能な provider、format、Execution Adapter は
[対応状況](compatibility.md) にまとめています。

実際の公的データを使った環境変数ベースの例は、リポジトリ checkout の
`examples/README.md` から確認できます。

公開されているモデル、メソッド、Adapter、エラーの詳細は
[API リファレンス](api.md) を参照してください。

provider ごとの設定と endpoint は [Source Adapter](api/source-adapters.md)、
runtime ごとの利用方法は [Execution Adapter](api/execution-adapters.md) を参照してください。
