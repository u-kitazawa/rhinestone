# アプリケーションを構成する

Rhinestone は `configure()` で作った `app` を入口に使います。`app` は global state を
使わないため、テストや複数の provider を扱うプログラムでも、必要な Adapter だけを
明示して構成できます。

## 最小構成

既知の URI を解決するだけなら、ネットワーク library も GIS library も不要です。

```python
from rhinestone import configure
from rhinestone.adapters import DirectAdapter

app = configure(
    dependencies={},
    source_adapters=(DirectAdapter(),),
    execution_adapters=(),
)
```

この `app` で `source_type="direct"` の Config を解決できます。登録していない
`source_type` を使うと `UnsupportedSourceError` になります。

## HTTP を使う Adapter を登録する

CKAN、STAC、e-Stat などは、HTTP GET の結果を JSON object として返す callback を
受け取ります。Rhinestone は HTTP client を決めないため、既存の client をそのまま
使えます。たとえば標準ライブラリだけで書く場合は次のとおりです。

```python
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def get_json(url, params, headers=None):
    query = urlencode(params)
    request = Request(
        f"{url}?{query}" if query else url,
        headers=headers or {},
    )
    with urlopen(request, timeout=30) as response:
        return json.load(response)
```

認証を使わない場合、Adapter は `get_json(url, params)` として callback を呼びます。
`api_token` または `api_key` を Adapter に渡す場合は、上のように第 3 引数の headers
も受け取れる callback にしてください。

```python
from rhinestone import configure
from rhinestone.adapters import CkanAdapter

app = configure(
    dependencies={},
    source_adapters=(
        CkanAdapter(
            get_json=get_json,
            endpoint="https://www.geospatial.jp/ckan",
        ),
    ),
    execution_adapters=(),
)
```

endpoint はカタログの API を提供する URL を指定します。HTML の配布ページではなく、
provider が公開する API endpoint を使ってください。

## データを開く runtime を登録する

Rhinestone は GDAL、Rasterio、pyogrio を依存に含めません。使う runtime を返す
factory と、その runtime に変換する Execution Adapter を両方登録します。

```python
import rasterio

from rhinestone.adapters.execution import RasterioAdapter

app = configure(
    dependencies={"rasterio": lambda: rasterio},
    source_adapters=(DirectAdapter(),),
    execution_adapters=(RasterioAdapter(),),
)
```

factory は `resource.open()` の時点まで実行されません。そのため、検索・metadata の
解決だけを行うプログラムに Rasterio や GDAL をインストールする必要はありません。

## secret を渡す

ODPT の consumer key のように、open 時にだけ必要な secret は `credentials` に
factory として登録します。Config には secret そのものではなく logical name を書きます。

```python
import os
import requests

from rhinestone.adapters import OdptAdapter
from rhinestone.adapters.execution import JsonServiceAdapter

app = configure(
    dependencies={"json-service": lambda: requests},
    source_adapters=(OdptAdapter(),),
    execution_adapters=(JsonServiceAdapter(OdptAdapter.prepare_request, "odpt"),),
    credentials={"odpt": lambda: os.environ["ODPT_CONSUMER_KEY"]},
)
```

`credentials` の factory が返す値は空でない文字列でなければなりません。環境変数や
secret manager を読む処理をここに置き、値を Config、metadata、Provenance に保存しない
でください。

次は、[データを検索する](search.md)か、[Resource を解決して開く](resolve-and-open.md)
へ進んでください。
