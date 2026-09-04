# 公開 API とパッケージ構成

## 最小限の公開 API

初期の Top-level API は次のとおり。

```python
from rhinestone import execute, load, parse_config, plan

config = parse_config(
    {
        "source": {
            "type": "ckan",
            "endpoint": "https://example.jp/api/3",
            "resource_id": "abcdef",
        }
    }
)

access_plan = plan(config)
data = execute(access_plan)
```

簡易形式：

```python
data = load(
    {
        "source": {
            "type": "direct",
            "uri": "https://example.jp/data.gpkg",
        },
        "data": {"format": "geopackage"},
    }
)
```

`plan()` と `load()` は、解析済み Config または Memory 上の Mapping を受け付ける。Path String は受け付けない。String を JSON、YAML、Local Path、URI のどれとして扱うかが曖昧になるためである。将来、明示的な File Boundary を提供する `load_config(path)` を追加できる。

`execute()` は `AccessPlan` だけを受け付ける。Config、Reference、生 URI は一切受け付けない。

## 高度な構成用 API

Dependency Injection を必要とするテストと Application は、`Application` Object を使用する。

```python
app = Application(
    reference_factories=...,
    metadata_adapters=...,
    capability_registry=...,
    loader_registry=...,
)

access_plan = app.plan(config)
data = app.execute(access_plan)
```

Constructor は明示的で、Process-global Registry を変更しない。公開されたサードパーティ向けの登録 Decorator と Entry Point は先送りする。

## 戻り値の仕様

- `parse_config()` は不変の Config を返す。
- `plan()` は不変の具象 `AccessPlan` を返し、Dataset の読み込みを行わない。
- `execute()` は Loader 固有の Object を変更せずに返す。
- `load()` は `execute(plan(config))` の戻り値をそのまま返す。

Rhinestone は、Capability をまたいで共通する DataFrame または地理空間データ型を保証しない。呼び出し元は Plan から、どの Capability と Binding が結果を生成するかを確認できる。

## 提案するパッケージ構成

```text
src/rhinestone/
├── __init__.py             # 選定された公開 Export
├── api.py                  # 既定の Application と簡易 Function
├── application.py          # オーケストレーション
├── config.py               # Config の解析と Reference Factory
├── errors.py               # 公開 Error 階層
├── domain/
│   ├── reference.py
│   ├── metadata.py
│   ├── capability.py
│   └── plan.py
├── resolution/
│   ├── formats.py          # Format / Media Type Policy
│   └── resolver.py
├── providers/
│   ├── direct.py
│   └── ckan.py
├── loaders/
│   └── pyogrio.py
└── transport/
    ├── base.py
    └── urllib.py
```

これは依存関係図であり、空の Module を作成する要件ではない。垂直スライスでは、実装済みの振る舞いを持つ File だけを追加することが望ましい（SHOULD）。

## API の安定性

v0.x の間、Top-level Function 名、Exception Class、Config の形、Capability Identifier、シリアライズされた Plan Field は互換性への影響を慎重に扱う。サードパーティによる拡張が明示的な目標になるまでは、内部 Registry Class と Provider Adapter Constructor を変更してもよい（MAY）。

既存の Placeholder `hello()` は、意図された API の一部ではない。最初の垂直スライスで生成プロジェクトのテストを置き換える際に削除してもよい（MAY）。
